"""Synthetic throughput simulator."""

from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from labflow_core.lims.manifests import write_csv_rows
from labflow_core.throughput.metrics import ThroughputComparison, ThroughputMetrics


class ThroughputScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    containers: int = Field(gt=0)
    samples_per_container: int = Field(default=95, gt=0)
    human_prep_time_min_per_batch: float = Field(default=10.0, ge=0)
    robot_run_time_min_per_container: float = Field(default=3.0, gt=0)
    post_robot_time_min_per_batch: float = Field(default=8.0, ge=0)
    lims_overhead_time_min_per_batch: float = Field(default=5.0, ge=0)
    containers_per_batch: int = Field(gt=0)

    @model_validator(mode="after")
    def robot_runtime_in_supported_range(self) -> ThroughputScenario:
        if not 2.0 <= self.robot_run_time_min_per_container <= 4.0:
            msg = "robot_run_time_min_per_container must be between 2 and 4 minutes."
            raise ValueError(msg)
        return self


def baseline_one_container_scenario(*, containers: int) -> ThroughputScenario:
    return ThroughputScenario(containers=containers, containers_per_batch=1)


def optimized_three_container_scenario(*, containers: int) -> ThroughputScenario:
    return ThroughputScenario(containers=containers, containers_per_batch=3)


def simulate_throughput(scenario: ThroughputScenario) -> ThroughputMetrics:
    batches = math.ceil(scenario.containers / scenario.containers_per_batch)
    elapsed = 0.0
    robot_busy = 0.0
    containers_remaining = scenario.containers
    for _ in range(batches):
        containers_in_batch = min(scenario.containers_per_batch, containers_remaining)
        containers_remaining -= containers_in_batch
        batch_robot_busy = containers_in_batch * scenario.robot_run_time_min_per_container
        robot_busy += batch_robot_busy
        elapsed += (
            scenario.lims_overhead_time_min_per_batch
            + scenario.human_prep_time_min_per_batch
            + batch_robot_busy
            + scenario.post_robot_time_min_per_batch
        )
    total_samples = scenario.containers * scenario.samples_per_container
    samples_per_hour = total_samples / (elapsed / 60.0)
    robot_idle = elapsed - robot_busy
    utilization = robot_busy / elapsed * 100.0
    return ThroughputMetrics(
        total_elapsed_time_min=round(elapsed, 4),
        total_samples=total_samples,
        samples_per_hour=round(samples_per_hour, 4),
        robot_busy_time_min=round(robot_busy, 4),
        robot_idle_time_min=round(robot_idle, 4),
        robot_utilization_percent=round(utilization, 4),
    )


def compare_scenarios(
    baseline: ThroughputScenario,
    optimized: ThroughputScenario,
) -> ThroughputComparison:
    baseline_metrics = simulate_throughput(baseline)
    optimized_metrics = simulate_throughput(optimized)
    return ThroughputComparison(
        baseline=baseline_metrics,
        optimized=optimized_metrics,
        throughput_multiplier=round(
            optimized_metrics.samples_per_hour / baseline_metrics.samples_per_hour,
            4,
        ),
    )


def compare_default_batching(*, containers: int) -> ThroughputComparison:
    return compare_scenarios(
        baseline_one_container_scenario(containers=containers),
        optimized_three_container_scenario(containers=containers),
    )


def write_throughput_outputs(comparison: ThroughputComparison, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "throughput_summary.json").write_text(
        json.dumps(comparison.to_json_dict(), indent=2, sort_keys=True) + "\n"
    )
    write_csv_rows(
        out_dir / "throughput_summary.csv",
        [
            "scenario",
            "total_elapsed_time_min",
            "total_samples",
            "samples_per_hour",
            "robot_busy_time_min",
            "robot_idle_time_min",
            "robot_utilization_percent",
        ],
        [
            {"scenario": "baseline", **comparison.baseline.model_dump()},
            {"scenario": "optimized", **comparison.optimized.model_dump()},
        ],
    )
