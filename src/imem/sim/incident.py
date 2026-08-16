from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .faults import FAULTS, FaultSpec
from .signals import SIGNALS

# --- service catalog -----------------------------------------------------------

SEED_SERVICES = [
    "checkout-api",
    "user-profile",
    "inventory-svc",
    "notification-worker",
    "search-gateway",
]

EVAL_SERVICES = [
    "billing-api",
    "cart-svc",
    "recommendation-edge",
    "shipping-orchestrator",
]

# Templates deliberately overlap in wording across fault classes: the alert text
# alone should not give the answer away.
DURATIONS = ["3m", "5m", "8m", "12m", "15m"]


@dataclass
class Incident:
    incident_id: str
    service: str
    alert_text: str
    observed_at: datetime
    observations: dict[str, float | str]
    # Ground truth. The agent must never read this; only the simulator and the
    # oracle responder are allowed to.
    _fault_class: str = field(repr=False)

    def visible(self) -> dict:
        """Exactly what the agent gets at page time."""
        return {
            "incident_id": self.incident_id,
            "service": self.service,
            "alert_text": self.alert_text,
            "observed_at": self.observed_at.isoformat(),
        }


class IncidentGenerator:
    def __init__(self, seed: int = 0, noise: float = 0.15):
        self.rng = random.Random(seed)
        self.noise = noise
        self._counter = 0

    # -- observations ----------------------------------------------------------

    def _observe(self, fault: FaultSpec) -> dict[str, float | str]:
        """Signal readings with multiplicative noise, so checks aren't exact."""
        out: dict[str, float | str] = {}
        for name, spec in SIGNALS.items():
            if spec.categorical:
                out[name] = fault.categorical_values.get(name, "none")
                continue
            value = spec.render(fault.effect_for(name))
            jitter = self.rng.gauss(1.0, self.noise)
            value *= max(jitter, 0.4)
            if spec.ceiling is not None:
                value = min(value, spec.ceiling)
            out[name] = round(value, 4)
        return out

    # -- alert text ------------------------------------------------------------

    def _alert_text(self, fault: FaultSpec, service: str) -> str:
        template = self.rng.choice(fault.alert_templates)
        return template.format(
            service=service,
            threshold=self.rng.choice([200, 300, 500, 800]),
            duration=self.rng.choice(DURATIONS),
        )

    # -- public ----------------------------------------------------------------

    def make(
        self,
        fault_class: str,
        service: str,
        observed_at: datetime | None = None,
    ) -> Incident:
        fault = FAULTS[fault_class]
        self._counter += 1
        return Incident(
            incident_id=f"INC-{self._counter:04d}",
            service=service,
            alert_text=self._alert_text(fault, service),
            observed_at=observed_at or datetime.now(timezone.utc),
            observations=self._observe(fault),
            _fault_class=fault_class,
        )

    def batch(
        self,
        services: list[str],
        n: int,
        fault_classes: list[str] | None = None,
        start: datetime | None = None,
    ) -> list[Incident]:
        """n incidents, fault classes and services sampled uniformly."""
        classes = fault_classes or list(FAULTS)
        t = start or datetime.now(timezone.utc) - timedelta(days=30)
        out = []
        for _ in range(n):
            t += timedelta(hours=self.rng.uniform(2, 20))
            out.append(
                self.make(
                    fault_class=self.rng.choice(classes),
                    service=self.rng.choice(services),
                    observed_at=t,
                )
            )
        return out

    def seed_set(self, n: int = 40) -> list[Incident]:
        """Incidents used to populate memory."""
        return self.batch(SEED_SERVICES, n)

    def eval_set(self, n: int = 25) -> list[Incident]:
        """Held-out incidents: same fault classes, unseen services."""
        return self.batch(EVAL_SERVICES, n)