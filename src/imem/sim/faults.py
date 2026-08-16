"""Fault catalog. This module is the signal matrix, written as code.

Anything not listed in `signal_effects` defaults to Effect.FLAT — so each spec
only declares what it actually distorts.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from .signals import SIGNALS, Effect

@dataclass(frozen=True)
class FaultSpec:
    fault_class: str
    summary: str
    signal_effects: dict[str, Effect]
    alert_templates: list[str]
    # Signals that most cleanly separate this fault from its usual confusions.
    discriminating_signals: list[str] = field(default_factory=list)
    # Categorical overrides, e.g. {"dep.error.type": "timeout"}
    categorical_values: dict[str, str] = field(default_factory=dict)

    def effect_for(self, signal: str) -> Effect:
        return self.signal_effects.get(signal, Effect.FLAT)

    def observe(self) -> dict[str, float | str]:
        """Materialize a full reading across every registered signal."""
        out: dict[str, float | str] = {}
        for name, spec in SIGNALS.items():
            if spec.categorical:
                out[name] = self.categorical_values.get(name, "none")
            else:
                out[name] = round(spec.render(self.effect_for(name)), 4)
        return out


FAULTS: dict[str, FaultSpec] = {}


def _register(spec: FaultSpec) -> None:
    FAULTS[spec.fault_class] = spec


_register(
    FaultSpec(
        fault_class="db_pool_exhaustion",
        summary="Requests queue waiting for a database connection; the DB itself is idle.",
        signal_effects={
            "latency.p99": Effect.UP_STRONG,
            "error.rate": Effect.UP,
            "throughput.rps": Effect.DOWN,
            "request.inflight": Effect.UP_STRONG,
            "app.thread.active": Effect.UP,      # threads blocked waiting on a connection
            "db.pool.active": Effect.SATURATE,   # <-- the tell
            "db.query.p99": Effect.FLAT,         # queries themselves are fine
            "db.cpu": Effect.DOWN,               # DB is starved of work
        },
        alert_templates=[
            "{service} p99 latency above {threshold}ms for {duration}",
            "{service}: request queue depth climbing, responses degraded",
            "Elevated response times on {service} — SLO burn rate high",
        ],
        discriminating_signals=["db.pool.active", "db.cpu"],
    )
)

_register(
    FaultSpec(
        fault_class="thread_pool_saturation",
        summary="Application worker threads are all busy; requests queue before reaching the DB.",
        signal_effects={
            "latency.p99": Effect.UP_STRONG,
            "error.rate": Effect.UP,             # rejections, not timeouts
            "throughput.rps": Effect.DOWN,
            "request.inflight": Effect.UP_STRONG,
            "app.thread.active": Effect.SATURATE,  # <-- the tell
            "db.pool.active": Effect.DOWN,         # nobody is getting far enough to use one
            "db.cpu": Effect.DOWN,
        },
        alert_templates=[
            "{service} p99 latency above {threshold}ms for {duration}",
            "{service} rejecting requests — capacity alarm",
            "Response time regression on {service}, throughput dropping",
        ],
        discriminating_signals=["app.thread.active", "db.pool.active"],
    )
)

_register(
    FaultSpec(
        fault_class="slow_query_regression",
        summary="A query plan degraded; individual queries got slower and the DB is working hard.",
        signal_effects={
            "latency.p99": Effect.UP_STRONG,
            "throughput.rps": Effect.DOWN,
            "request.inflight": Effect.UP,
            "app.thread.active": Effect.UP,
            "db.pool.active": Effect.UP,
            "db.query.p99": Effect.UP_STRONG,     # <-- the tell
            "db.rows.scanned": Effect.UP_STRONG,  # <-- the tell
            "db.cpu": Effect.UP_STRONG,           # opposite direction from pool exhaustion
        },
        alert_templates=[
            "{service} p99 latency above {threshold}ms for {duration}",
            "{service} database response time degraded",
            "Slow endpoint detected on {service} — {duration} sustained",
        ],
        discriminating_signals=["db.query.p99", "db.cpu", "db.rows.scanned"],
    )
)

_register(
    FaultSpec(
        fault_class="downstream_latency",
        summary="An upstream dependency got slow; this service is just waiting on it.",
        signal_effects={
            "latency.p99": Effect.UP_STRONG,
            "error.rate": Effect.UP,
            "throughput.rps": Effect.DOWN,
            "request.inflight": Effect.UP_STRONG,
            "app.thread.active": Effect.UP,
            "dep.latency.p99": Effect.UP_STRONG,  # <-- the tell
        },
        categorical_values={"dep.error.type": "timeout"},
        alert_templates=[
            "{service} p99 latency above {threshold}ms for {duration}",
            "{service} timeout rate elevated",
            "{service} SLO breach — sustained latency regression",
        ],
        discriminating_signals=["dep.latency.p99", "dep.error.type"],
    )
)

_register(
    FaultSpec(
        fault_class="traffic_spike",
        summary="Not a fault: real demand went up and the system is handling more work.",
        signal_effects={
            "latency.p99": Effect.UP,
            "throughput.rps": Effect.UP_STRONG,   # <-- the tell: UP, not DOWN
            "request.inflight": Effect.UP,
            "app.thread.active": Effect.UP,
            "app.heap.used": Effect.UP,
            "db.pool.active": Effect.UP,
            "db.cpu": Effect.UP,
            "upstream.rps": Effect.UP_STRONG,     # <-- the tell
        },
        alert_templates=[
            "{service} p99 latency above {threshold}ms for {duration}",
            "{service} resource utilization high",
            "{service} approaching capacity limits",
        ],
        discriminating_signals=["throughput.rps", "upstream.rps"],
    )
)


# --- confusion pairs: what memory is actually supposed to help with -------------

CONFUSION_PAIRS: list[tuple[str, str]] = [
    ("db_pool_exhaustion", "thread_pool_saturation"),
    ("db_pool_exhaustion", "slow_query_regression"),
    ("downstream_latency", "db_pool_exhaustion"),
    ("traffic_spike", "thread_pool_saturation"),
]


def separating_signals(a: str, b: str) -> list[str]:
    """Signals whose effect differs between two fault classes."""
    fa, fb = FAULTS[a], FAULTS[b]
    out = []
    for name, spec in SIGNALS.items():
        if spec.categorical:
            if fa.categorical_values.get(name, "none") != fb.categorical_values.get(name, "none"):
                out.append(name)
        elif fa.effect_for(name) is not fb.effect_for(name):
            out.append(name)
    return out