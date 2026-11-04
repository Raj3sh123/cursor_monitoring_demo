import os

import pytest

from collector import (
    METRICS_COMMAND,
    collect_metrics,
    cpu_percent,
    is_alert,
    parse_metrics_output,
    parse_ports,
)


SAMPLE = """\
cpu  100 0 50 850 0 0 0 0
cpu  200 0 100 1700 0 0 0 0
---MEM---
MemTotal:       2048000 kB
MemFree:         248000 kB
MemAvailable:   1024000 kB
---NET---
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000 1 0 0 0 0 0 0 2000 1 0 0 0 0 0 0
  eth0: 4096 2 0 0 0 0 0 0 8192 2 0 0 0 0 0 0
---PORTS---
tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:*
tcp LISTEN 0 128 [::]:80 [::]:*
udp UNCONN 0 0 0.0.0.0:68 0.0.0.0:*
"""


def test_cpu_percent_ignores_idle_time():
    assert cpu_percent("cpu  100 0 0 900 0 0 0 0", "cpu  150 0 50 1800 0 0 0 0") == 10.0


def test_parse_sample_output():
    parsed = parse_metrics_output(SAMPLE)
    assert parsed["ok"] is True
    assert parsed["cpu_percent"] == 15.0
    assert parsed["mem_percent"] == 50.0
    assert parsed["network"][1]["iface"] == "eth0"
    assert parsed["network"][1]["rx_bytes"] == 4096
    ports = {(row["proto"], row["port"]) for row in parsed["ports"]}
    assert ("tcp", 22) in ports
    assert ("tcp", 80) in ports
    assert ("udp", 68) in ports


def test_port_strips_interface_zone():
    text = "udp UNCONN 0 0 127.0.0.53%lo:53 0.0.0.0:*\n"
    assert parse_ports(text) == [{"proto": "udp", "address": "127.0.0.53", "port": 53}]


def test_parse_netstat_ports():
    text = """\
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State
tcp        0      0 127.0.0.1:5000          0.0.0.0:*               LISTEN
"""
    assert parse_ports(text) == [{"proto": "tcp", "address": "127.0.0.1", "port": 5000}]


def test_alert_thresholds_are_exclusive():
    assert is_alert(80, 85) is False
    assert is_alert(80.1, 10) is True
    assert is_alert(10, 85.1) is True


def test_metrics_command_is_fixed():
    assert "/proc/stat" in METRICS_COMMAND
    assert "{" not in METRICS_COMMAND
    assert "%s" not in METRICS_COMMAND
    assert "password" not in METRICS_COMMAND.lower()


def test_collect_rejects_bad_ip_without_ssh(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("SSH client should not be created")

    monkeypatch.setattr("collector.paramiko.SSHClient", explode)
    result = collect_metrics("not-an-ip")
    assert result["ok"] is False


def test_collect_reports_missing_ssh_user(monkeypatch):
    monkeypatch.delenv("SSH_USER", raising=False)
    monkeypatch.delenv("SSH_KEY_PATH", raising=False)
    monkeypatch.delenv("SSH_PASSWORD", raising=False)
    result = collect_metrics("127.0.0.1")
    assert result == {"ok": False, "error": "SSH_USER is not set."}


def test_collect_uses_fixed_command(monkeypatch, tmp_path):
    key_path = tmp_path / "demo_key"
    key_path.write_text("not-a-real-key\n", encoding="utf-8")
    monkeypatch.setenv("SSH_USER", "monitor")
    monkeypatch.setenv("SSH_KEY_PATH", str(key_path))
    monkeypatch.delenv("SSH_PASSWORD", raising=False)
    seen = {}

    class FakeStdout:
        def read(self):
            return SAMPLE.encode()

        class channel:
            @staticmethod
            def recv_exit_status():
                return 0

    class FakeClient:
        def load_system_host_keys(self):
            return None

        def set_missing_host_key_policy(self, _policy):
            return None

        def connect(self, **kwargs):
            seen["hostname"] = kwargs["hostname"]
            seen["username"] = kwargs["username"]
            assert kwargs["look_for_keys"] is False
            assert kwargs["allow_agent"] is False
            assert "password" not in kwargs

        def exec_command(self, command, timeout=None):
            seen["command"] = command
            return None, FakeStdout(), FakeStdout()

        def close(self):
            return None

    monkeypatch.setattr("collector.paramiko.SSHClient", FakeClient)
    result = collect_metrics("127.0.0.1")
    assert result["ok"] is True
    assert seen["command"] == METRICS_COMMAND
    assert seen["hostname"] == "127.0.0.1"
    assert "127.0.0.1" not in seen["command"]


def test_parse_local_proc_files():
    stat_path = "/proc/stat"
    mem_path = "/proc/meminfo"
    net_path = "/proc/net/dev"
    if not all(os.path.exists(path) for path in (stat_path, mem_path, net_path)):
        pytest.skip("procfs is not available")
    cpu = open(stat_path, encoding="utf-8").readline()
    output = (
        cpu
        + cpu
        + "---MEM---\n"
        + open(mem_path, encoding="utf-8").read()
        + "---NET---\n"
        + open(net_path, encoding="utf-8").read()
        + "---PORTS---\n"
    )
    parsed = parse_metrics_output(output)
    assert parsed["ok"] is True
    assert 0 <= parsed["cpu_percent"] <= 100
    assert parsed["mem_total"] > 0
