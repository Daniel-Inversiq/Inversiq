from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SurfaceType = Literal[
    "wall",
    "ceiling",
    "wood",
    "window_frame",
    "door",
    "stairs",
    "facade",
    "trim",
    "metal",
    "unknown",
]

DamageType = Literal[
    "crack",
    "peeling_paint",
    "moisture_stain",
    "mold",
    "wood_rot_possible",
    "stain",
    "none",
    "unknown",
]

EnvironmentType = Literal["indoor", "outdoor", "unknown"]
ComplexityLevel = Literal["low", "medium", "high", "unknown"]
SeverityLevel = Literal["low", "medium", "high"]
StorageKind = Literal["s3", "local"]
VisionSource = Literal["openai", "fallback"]


class _VisionBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PhotoQualityInput(_VisionBaseModel):
    sharpness_score: float = Field(ge=0.0, le=1.0)
    resolution_score: float = Field(ge=0.0, le=1.0)
    exposure_score: float = Field(ge=0.0, le=1.0)
    usability_score: float = Field(ge=0.0, le=1.0)
    blur_detected: bool = False
    too_dark: bool = False
    too_bright: bool = False
    obstructed: bool = False


class VisionStepInput(_VisionBaseModel):
    lead_id: str
    photo_id: str
    image_url: str
    storage_kind: StorageKind
    mime_type: str = "image/jpeg"
    photo_quality: PhotoQualityInput
    requested_tasks: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class DetectedSurface(_VisionBaseModel):
    type: SurfaceType
    confidence: float = Field(ge=0.0, le=1.0)
    approximate_coverage: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class DetectedDamage(_VisionBaseModel):
    type: DamageType
    confidence: float = Field(ge=0.0, le=1.0)
    severity: SeverityLevel | None = None
    notes: str | None = None


class VisionPhotoPrediction(_VisionBaseModel):
    lead_id: str
    photo_id: str
    photo_is_usable: bool
    photo_usability_score: float = Field(ge=0.0, le=1.0)
    photo_usability_reasons: list[str] = Field(default_factory=list)
    environment: EnvironmentType = "unknown"
    environment_confidence: float = Field(ge=0.0, le=1.0)
    surfaces: list[DetectedSurface] = Field(default_factory=list)
    damages: list[DetectedDamage] = Field(default_factory=list)
    complexity: ComplexityLevel = "unknown"
    complexity_confidence: float = Field(ge=0.0, le=1.0)
    quote_relevance_score: float = Field(ge=0.0, le=1.0)
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    review_flags: list[str] = Field(default_factory=list)
    summary: str
    model_name: str
    model_latency_ms: int = Field(ge=0)
    prompt_version: str


class VisionExecutionResult(_VisionBaseModel):
    source: VisionSource
    prediction: VisionPhotoPrediction
    raw_response: dict[str, Any] | None = None
    error: str | None = None


class LeadVisionAggregate(_VisionBaseModel):
    lead_id: str
    environment: EnvironmentType = "unknown"
    environment_confidence: float = Field(ge=0.0, le=1.0)
    dominant_surfaces: list[DetectedSurface] = Field(default_factory=list)
    damages: list[DetectedDamage] = Field(default_factory=list)
    overall_complexity: ComplexityLevel = "unknown"
    overall_complexity_confidence: float = Field(ge=0.0, le=1.0)
    coverage_score: float = Field(ge=0.0, le=1.0)
    evidence_score: float = Field(ge=0.0, le=1.0)
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    decision: Literal["ACCEPTED", "ACCEPTED_WITH_WARNING", "NEEDS_REVIEW"] = "ACCEPTED"
    decision_reasons: list[str] = Field(default_factory=list)
    warning_reasons: list[str] = Field(default_factory=list)
    decision_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    quality_metrics: dict[str, float] = Field(default_factory=dict)
