"""Unit & integration test suite for JobManager and /api/jobs execution routes."""

import pytest
from app.schemas.query_schema import (
    QueryUnderstanding,
    WhatSchema,
    WhereSchema,
    WhenSchema,
    TargetSchema,
    MeasurementSchema,
    OutputFormatSchema,
)
from app.services.job_manager import job_manager
from app.services.query_planner import query_planner


@pytest.fixture
def sample_understanding():
    return QueryUnderstanding(
        what=WhatSchema(value="open drainage channel detection and building proximity analysis", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Pune", confidence=1.0, provided_by_user=True),
        when=WhenSchema(value="2024", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["open drainage channels", "buildings"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="filter by distance using 200 metres threshold", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["interactive map", "GeoJSON", "CSV"], confidence=1.0, provided_by_user=True)
    )


def test_job_manager_creation_and_8_stages(sample_understanding):
    plan = query_planner.generate_plan(sample_understanding)
    job = job_manager.create_job(sample_understanding, plan)

    assert job.job_id.startswith("job_")
    assert len(job.stages) == 8
    assert job.stages[0].name == "Preparing execution"
    assert job.stages[7].name == "Displaying final results"


def test_job_manager_run_execution(sample_understanding):
    job = job_manager.create_job(sample_understanding)
    executed_job = job_manager.run_job_execution(job.job_id)

    assert executed_job.status == "completed"
    assert executed_job.overall_progress_pct == 100
    assert executed_job.payload is not None
    assert executed_job.payload.deliverable.title is not None
    assert executed_job.payload.deliverable.geojson_export is not None
