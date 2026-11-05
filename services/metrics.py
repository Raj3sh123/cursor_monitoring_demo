"""Collect metrics and store samples. No HTTP and no display formatting."""

import json

import collector
import db


def record_server_metrics(database: str, server: dict, collect_metrics=None) -> dict:
    """Return stored samples and a public error message for one server."""
    collect = collector.collect_metrics if collect_metrics is None else collect_metrics
    result = collect(server["ip"])
    if result["ok"]:
        db.add_sample(
            database,
            server["id"],
            result["cpu_percent"],
            result["mem_used"],
            result["mem_total"],
            json.dumps(result["network"]),
            json.dumps(result["ports"]),
        )
    return {
        "error": None if result["ok"] else result["error"],
        "samples": db.list_samples(database, server["id"]),
    }
