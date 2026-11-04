"""Collect Linux metrics over SSH.

The remote command is a fixed string. Server name and IP are never inserted
into the shell command.
"""

import ipaddress
import os
import socket

import paramiko

CPU_ALERT_PERCENT = 80
MEMORY_ALERT_PERCENT = 85

# Fixed remote command. Do not format user input into this string.
METRICS_COMMAND = (
    "grep '^cpu ' /proc/stat; sleep 0.4; grep '^cpu ' /proc/stat; "
    "echo '---MEM---'; cat /proc/meminfo; "
    "echo '---NET---'; cat /proc/net/dev; "
    "echo '---PORTS---'; ss -H -lntu 2>/dev/null || netstat -lntu"
)


def is_valid_ip(value):
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def is_alert(cpu_percent, memory_percent):
    cpu_high = cpu_percent is not None and cpu_percent > CPU_ALERT_PERCENT
    memory_high = memory_percent is not None and memory_percent > MEMORY_ALERT_PERCENT
    return cpu_high or memory_high


def _fail(message):
    return {"ok": False, "error": message}


def _public_error(exc):
    text = " ".join(str(exc).split())
    for secret in (os.environ.get("SSH_PASSWORD") or "", os.environ.get("SSH_KEY_PATH") or ""):
        if secret:
            text = text.replace(secret, "[redacted]")
    if not text:
        return "SSH connection failed."
    return f"SSH connection failed: {text[:180]}"


def cpu_percent(first_line, second_line):
    first = _cpu_times(first_line)
    second = _cpu_times(second_line)
    total_delta = sum(second) - sum(first)
    idle_delta = _idle(second) - _idle(first)
    if total_delta <= 0:
        return 0.0
    used = (total_delta - idle_delta) / total_delta * 100
    return round(min(100.0, max(0.0, used)), 1)


def _cpu_times(line):
    parts = line.split()
    if len(parts) < 5 or parts[0] != "cpu":
        raise ValueError("unexpected cpu line")
    return [int(part) for part in parts[1:]]


def _idle(times):
    idle = times[3]
    if len(times) > 4:
        idle += times[4]
    return idle


def parse_meminfo(text):
    values = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        values[key] = int(rest.strip().split()[0])
    total_kb = values["MemTotal"]
    if "MemAvailable" in values:
        available_kb = values["MemAvailable"]
    else:
        available_kb = values["MemFree"]
    used_kb = max(0, total_kb - available_kb)
    percent = round(used_kb / total_kb * 100, 1) if total_kb else 0.0
    return {
        "mem_total": total_kb * 1024,
        "mem_available": available_kb * 1024,
        "mem_used": used_kb * 1024,
        "mem_percent": percent,
    }


def parse_netdev(text):
    rows = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        if not iface or iface.startswith("Inter") or iface == "face":
            continue
        parts = rest.split()
        if len(parts) < 9:
            continue
        rows.append(
            {
                "iface": iface,
                "rx_bytes": int(parts[0]),
                "tx_bytes": int(parts[8]),
            }
        )
    return rows


def parse_ports(text):
    ports = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("Active ", "Proto", "Netid")):
            continue
        parts = line.split()
        proto = parts[0].lower()
        if proto not in ("tcp", "udp", "tcp6", "udp6"):
            continue
        if len(parts) >= 5 and parts[1] in ("LISTEN", "UNCONN"):
            local = parts[4]
        elif len(parts) >= 4:
            local = parts[3]
        else:
            continue
        address, port = _split_host_port(local)
        if port is None:
            continue
        ports.append({"proto": proto, "address": address, "port": port})
    return ports


def _split_host_port(value):
    if value.startswith("["):
        host, separator, port = value.rpartition("]:")
        if separator:
            host = host + "]"
    else:
        host, separator, port = value.rpartition(":")
    if not separator or not port.isdigit():
        return value, None
    host = host.split("%", 1)[0]
    return host, int(port)


def parse_metrics_output(output):
    try:
        cpu_part, rest = output.split("---MEM---", 1)
        mem_part, rest = rest.split("---NET---", 1)
        net_part, port_part = rest.split("---PORTS---", 1)
    except ValueError:
        return _fail("Could not read metrics from the host.")
    cpu_lines = [line.strip() for line in cpu_part.splitlines() if line.strip().startswith("cpu ")]
    if len(cpu_lines) < 2:
        return _fail("Could not read CPU usage from the host.")
    try:
        memory = parse_meminfo(mem_part)
        parsed = {
            "ok": True,
            "error": None,
            "cpu_percent": cpu_percent(cpu_lines[0], cpu_lines[1]),
            "network": parse_netdev(net_part),
            "ports": parse_ports(port_part),
        }
        parsed.update(memory)
    except (ValueError, KeyError, IndexError):
        return _fail("Could not read metrics from the host.")
    return parsed


def collect_metrics(ip):
    if not is_valid_ip(ip):
        return _fail("Enter a valid IP address.")

    user = os.environ.get("SSH_USER", "").strip()
    key_path = os.environ.get("SSH_KEY_PATH", "").strip()
    password = os.environ.get("SSH_PASSWORD", "")
    if not user:
        return _fail("SSH_USER is not set.")
    if not key_path and not password:
        return _fail("Set SSH_KEY_PATH or SSH_PASSWORD.")
    if key_path and not os.path.isfile(key_path):
        return _fail("SSH key file was not found.")

    client = paramiko.SSHClient()
    try:
        client.load_system_host_keys()
        # Local demo: accept the host key on connect. Do not send user text to the shell.
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {
            "hostname": ip,
            "port": 22,
            "username": user,
            "timeout": 8,
            "auth_timeout": 8,
            "banner_timeout": 8,
            "allow_agent": False,
            "look_for_keys": False,
        }
        if key_path:
            connect_kwargs["key_filename"] = key_path
        else:
            connect_kwargs["password"] = password
        client.connect(**connect_kwargs)
        _stdin, stdout, _stderr = client.exec_command(METRICS_COMMAND, timeout=15)
        output = stdout.read().decode("utf-8", "replace")
        stdout.channel.recv_exit_status()
        return parse_metrics_output(output)
    except paramiko.AuthenticationException:
        return _fail("SSH authentication failed.")
    except (paramiko.SSHException, OSError, socket.timeout) as exc:
        return _fail(_public_error(exc))
    finally:
        client.close()
