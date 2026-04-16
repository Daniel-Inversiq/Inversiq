# inversiq/engine/config.py
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class StepConfig:
    id: str
    use: str
    with_: Dict[str, Any]
    on_fail: str = "STOP"           # STOP | CONTINUE (meestal STOP)
    on_needs_review: str = "STOP"   # STOP | CONTINUE


@dataclass
class EngineConfig:
    vertical_id: str
    rules_path: str
    template_path: str
    steps: List[StepConfig]
    version: str = "1.0"
    defaults: Optional[Dict[str, Any]] = None

    def config_hash(self) -> str:
        """Return a 12-char SHA-256 prefix over the pipeline step definitions.

        The hash covers the ordered list of (step_id, step_use) pairs — enough
        to detect any change in *which steps run and in what order*.  It does
        not cover ``with_`` params, rules, or templates (those change frequently
        and would make the hash too volatile for useful equality checks).

        Two PipelineRuns with identical ``config_hash`` values used the same
        pipeline structure.  Different hashes mean the structure differed even
        if ``engine_version`` is the same.
        """
        canonical = json.dumps(
            [{"id": s.id, "use": s.use} for s in self.steps],
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def load_engine_config(raw: Dict[str, Any]) -> EngineConfig:
    steps = []
    for s in raw["pipeline"]["steps"]:
        steps.append(
            StepConfig(
                id=s["id"],
                use=s["use"],
                with_=s.get("with", {}),
                on_fail=s.get("on_fail", "STOP"),
                on_needs_review=s.get("on_needs_review", "STOP"),
            )
        )

    return EngineConfig(
        vertical_id=raw["vertical_id"],
        rules_path=raw["assets"]["rules"],
        template_path=raw["assets"]["template"],
        steps=steps,
        version=raw.get("version", "1.0"),
        defaults=raw.get("defaults"),
    )
