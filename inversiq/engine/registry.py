# inversiq/engine/registry.py
from __future__ import annotations
from typing import Callable, Dict, Optional
from .context import PipelineState, StepResult
from .config import StepConfig

StepFn = Callable[[PipelineState, StepConfig, dict], StepResult]


class StepRegistry:
    def __init__(self) -> None:
        self._steps: Dict[str, StepFn] = {}

    def register(self, key: str, fn: StepFn) -> None:
        if key in self._steps:
            raise ValueError(f"Step already registered: {key}")
        self._steps[key] = fn

    def get(self, key: str) -> StepFn:
        try:
            return self._steps[key]
        except KeyError:
            raise KeyError(f"Unknown step '{key}'. Registered: {sorted(self._steps.keys())}")

    def peek(self, key: str) -> "Optional[StepFn]":
        """Return the step function for *key*, or None if not registered.

        Used by the runner to read ``__step_contract__`` before creating the
        step run row — without raising on misconfigured pipelines (``get``
        inside the try block handles the error path).
        """
        return self._steps.get(key)
