"""Throughput metric models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ThroughputMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_elapsed_time_min: float
    total_samples: int
    samples_per_hour: float
    robot_busy_time_min: float
    robot_idle_time_min: float
    robot_utilization_percent: float


class ThroughputComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline: ThroughputMetrics
    optimized: ThroughputMetrics
    throughput_multiplier: float = Field(gt=0)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline.model_dump(),
            "optimized": self.optimized.model_dump(),
            "throughput_multiplier": self.throughput_multiplier,
        }
