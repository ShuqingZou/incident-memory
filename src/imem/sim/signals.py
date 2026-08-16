"""Signal registry: what the agent can observe, and how faults distort it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random

from imem.sim.traffic import diurnal

class Effect(Enum):
    """How a fault distorts one signal, relative to its healthy baseline."""
    
    FLAT = "flat"
    UP = "up"
    UP_STRONG = "up_strong"
    DOWN = "down"
    DOWN_STRONG = "down_strong"
    SATURATE = "saturate"

    @property
    def multiplier(self) -> float:
        return {
            Effect.FLAT: 1.0,
                Effect.UP: 1.8,
                Effect.UP_STRONG: 5.0,
                Effect.DOWN: 0.6,
                Effect.DOWN_STRONG: 0.25,
                Effect.SATURATE: 1.0,
        }[self]

class Layer(Enum):
    EDGE = "edge"
    APP = "app"
    DB = "db"
    CACHE = "cache"
    DEP = "dep"
    META = "meta"

@dataclass(frozen=True)
class SignalSpec:
    name: str
    layer: Layer
    baseline: float
    unit: str
    ceiling: float | None = None
    categorical: bool = False
    spread: float = 0.25
    diurnal_sensitive: bool = False

    def render(self, effect, severity=1.0, hour=14.0, rng=None):
        rng = rng or random.Random()
        if effect is Effect.SATURATE:
            if self.ceiling is None:
                raise ValueError(f"{self.name} has no ceiling; SATURATE is meaningless")
            return self.ceiling * rng.uniform(0.90, 1.0)

        base = self.baseline
        if self.diurnal_sensitive:
            base *= diurnal(hour)

        mult = 1.0 + (effect.multiplier - 1.0) * severity
        value = base * mult * rng.lognormvariate(0, self.spread)

        if self.ceiling is not None:
            value = min(value, self.ceiling)
        return value


SIGNALS: dict[str, SignalSpec] = {
    s.name: s
    for s in [
        # --- edge ---
        SignalSpec("latency.p99", Layer.EDGE, baseline=120.0, unit="ms",
           spread=0.25, diurnal_sensitive=True),
        SignalSpec("error.rate", Layer.EDGE, baseline=0.002, unit="ratio",
                ceiling=1.0, spread=0.45),
        SignalSpec("throughput.rps", Layer.EDGE, baseline=850.0, unit="rps",
                spread=0.12, diurnal_sensitive=True),
        # --- app ---
        SignalSpec("app.thread.active", Layer.APP, baseline=60.0, unit="count",
                ceiling=200.0, spread=0.18, diurnal_sensitive=True),
        SignalSpec("app.heap.used", Layer.APP, baseline=0.45, unit="ratio",
                ceiling=1.0, spread=0.12),

        # --- db ---
        SignalSpec("db.pool.active", Layer.DB, baseline=18.0, unit="count",
                ceiling=50.0, spread=0.15, diurnal_sensitive=True),
        SignalSpec("db.query.p99", Layer.DB, baseline=25.0, unit="ms",
                spread=0.30),
        SignalSpec("db.rows.scanned", Layer.DB, baseline=1200.0, unit="rows",
                spread=0.35),
        SignalSpec("db.cpu", Layer.DB, baseline=0.35, unit="ratio",
                ceiling=1.0, spread=0.20, diurnal_sensitive=True),

        # --- cache ---
        SignalSpec("cache.hit.rate", Layer.CACHE, baseline=0.94, unit="ratio",
                ceiling=1.0, spread=0.04),

        # --- dependency ---
        SignalSpec("dep.latency.p99", Layer.DEP, baseline=45.0, unit="ms",
                spread=0.28, diurnal_sensitive=True),
        SignalSpec("dep.error.type", Layer.DEP, baseline=0.0, unit="enum",
                categorical=True),

        # --- meta ---
        SignalSpec("deploy.recent", Layer.META, baseline=0.0, unit="bool",
                ceiling=1.0, spread=0.0),
        SignalSpec("upstream.rps", Layer.EDGE, baseline=860.0, unit="rps",
                spread=0.12, diurnal_sensitive=True),
    ]
}