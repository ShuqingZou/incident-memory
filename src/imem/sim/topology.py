"""The pretend production system our agent triages."""

SERVICES = {
    "gateway":   {"tier": "edge",  "capacity": 1200, "base_latency_ms": 15},
    "checkout":  {"tier": "core",  "capacity": 400,  "base_latency_ms": 60},
    "payments":  {"tier": "core",  "capacity": 250,  "base_latency_ms": 90},
    "inventory": {"tier": "core",  "capacity": 300,  "base_latency_ms": 40},
    "ledger":    {"tier": "batch", "capacity": 150,  "base_latency_ms": 120},
    "cache":     {"tier": "core",  "capacity": 2000, "base_latency_ms": 3},
}

# who calls whom
CALLS = {
    "gateway":   ["checkout"],
    "checkout":  ["payments", "inventory"],
    "payments":  ["ledger"],
    "inventory": ["cache"],
    "ledger":    [],
    "cache":     [],
}

INSTANCES = ["i-01", "i-02", "i-03"]

METRICS = [
    "request_rate",
    "latency_p99",
    "error_rate",
    "db_conn_wait_ms",
    "cpu_steal_pct",
    "tls_handshake_errors",
]


def downstream_of(svc: str) -> list[str]:
    return CALLS.get(svc, [])


def callers_of(svc: str) -> list[str]:
    return [s for s, d in CALLS.items() if svc in d]
