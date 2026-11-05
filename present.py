"""Turn stored samples into the objects the pages and metrics API return."""

import csv
import io
import json
from datetime import datetime

from collector import is_alert

REFRESH_MS = 5000


def server_row(row: dict) -> dict:
    mem_percent = memory_percent(row.get("mem_used"), row.get("mem_total"))
    cpu = row.get("cpu_percent")
    if row.get("collected_at") is None:
        status = "No data"
    elif is_alert(cpu, mem_percent):
        status = "Alert"
    else:
        status = "OK"
    return {
        "id": row["id"],
        "name": row["name"],
        "ip": row["ip"],
        "cpu_display": format_percent(cpu),
        "mem_display": format_percent(mem_percent),
        "status": status,
    }


def present(server: dict, error: str | None, samples: list[dict]) -> dict:
    latest = samples[-1] if samples else None
    previous = samples[-2] if len(samples) > 1 else None
    cpu = latest["cpu_percent"] if latest else None
    mem_percent = memory_percent(
        latest["mem_used"] if latest else None,
        latest["mem_total"] if latest else None,
    )
    network = network_rows(latest, previous)
    ports = json.loads(latest["ports_json"]) if latest and latest["ports_json"] else []
    alert = bool(latest) and is_alert(cpu, mem_percent)
    if error:
        status = "Error"
    elif latest is None:
        status = "No data"
    elif alert:
        status = "Alert"
    else:
        status = "OK"
    return {
        "ok": error is None and latest is not None,
        "error": error,
        "server": {"id": server["id"], "name": server["name"], "ip": server["ip"]},
        "collected_at": display_time(latest["collected_at"]) if latest else None,
        "cpu_percent": cpu,
        "cpu_display": format_percent(cpu),
        "memory": {
            "percent": mem_percent,
            "percent_display": format_percent(mem_percent),
            "used_display": format_bytes(latest["mem_used"]) if latest else "—",
            "total_display": format_bytes(latest["mem_total"]) if latest else "—",
            "available_display": format_bytes(available_bytes(latest)) if latest else "—",
        },
        "network": network,
        "ports": ports,
        "alert": alert,
        "status": status,
        "history": history(samples),
        "refresh_ms": REFRESH_MS,
    }


def available_bytes(sample: dict | None) -> int | None:
    if not sample or sample["mem_total"] is None or sample["mem_used"] is None:
        return None
    return max(0, sample["mem_total"] - sample["mem_used"])


def network_rows(latest: dict | None, previous: dict | None) -> list[dict]:
    if not latest or not latest["network_json"]:
        return []
    current = json.loads(latest["network_json"])
    prior = json.loads(previous["network_json"]) if previous and previous["network_json"] else []
    prior_by_iface = {row["iface"]: row for row in prior}
    seconds = seconds_between(
        previous["collected_at"] if previous else None,
        latest["collected_at"],
    )
    rows = []
    for row in current:
        rx_rate = None
        tx_rate = None
        old = prior_by_iface.get(row["iface"])
        if old and seconds > 0:
            rx_rate = max(0, (row["rx_bytes"] - old["rx_bytes"]) / seconds)
            tx_rate = max(0, (row["tx_bytes"] - old["tx_bytes"]) / seconds)
        rows.append(
            {
                "iface": row["iface"],
                "rx_display": format_bytes(row["rx_bytes"]),
                "tx_display": format_bytes(row["tx_bytes"]),
                "rx_rate_display": format_rate(rx_rate),
                "tx_rate_display": format_rate(tx_rate),
            }
        )
    return rows


def history(samples: list[dict]) -> dict:
    labels = []
    cpu = []
    memory = []
    for sample in samples:
        stamp = sample["collected_at"]
        labels.append(stamp[11:19] if len(stamp) >= 19 else stamp)
        cpu.append(sample["cpu_percent"])
        memory.append(memory_percent(sample["mem_used"], sample["mem_total"]))
    return {"labels": labels, "cpu": cpu, "memory": memory}


def seconds_between(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    except ValueError:
        return 0
    return delta.total_seconds()


def memory_percent(used, total):
    if used is None or not total:
        return None
    return round(used / total * 100, 1)


def status_class(status: str) -> str:
    if status == "Alert":
        return "text-bg-danger"
    if status == "OK":
        return "text-bg-success"
    if status == "Error":
        return "text-bg-warning"
    return "text-bg-secondary"


def format_percent(value) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}%"


def format_bytes(value) -> str:
    if value is None:
        return "—"
    number = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if number < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(number)} {unit}"
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{number:.1f} TB"


def format_rate(value) -> str:
    if value is None:
        return "—"
    return f"{format_bytes(value)}/s"


def samples_to_csv(samples: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "collected_at",
            "cpu_percent",
            "mem_used_bytes",
            "mem_total_bytes",
            "mem_percent",
            "network",
            "ports",
        ]
    )
    for sample in samples:
        writer.writerow(
            [
                sample["collected_at"],
                sample["cpu_percent"],
                sample["mem_used"],
                sample["mem_total"],
                memory_percent(sample["mem_used"], sample["mem_total"]),
                sample["network_json"],
                sample["ports_json"],
            ]
        )
    return buffer.getvalue()


def display_time(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("T", " ")[:19] + " UTC"
