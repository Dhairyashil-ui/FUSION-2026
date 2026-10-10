"""FUSION 2026 - Job Execution API Routes (Part 3 End-to-End Workflow)."""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.schemas.query_schema import QueryUnderstanding
from app.services.job_manager import job_manager, ExecutionJobRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Execution Pipeline Jobs"])


class JobStartRequest(BaseModel):
    """Payload to start a GeoAI execution job."""
    understanding: QueryUnderstanding = Field(..., description="5-field canonical query understanding")
    plan_id: Optional[str] = Field(default=None, description="Optional approved plan ID")


@router.post(
    "/execute",
    status_code=status.HTTP_200_OK,
    summary="Start an end-to-end GeoAI execution job when user approves plan"
)
async def start_job_execution(payload: JobStartRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Creates an execution session, assigns a unique job ID,
    and runs the 8-stage execution pipeline in the background.
    """
    try:
        job = job_manager.create_job(payload.understanding)
        background_tasks.add_task(job_manager.run_job_execution, job.job_id)
        return {"job_id": job.job_id, "status": "running"}

    except Exception as exc:
        logger.error(f"Error executing job: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job execution failed: {str(exc)}"
        )


@router.get(
    "/{job_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Poll live progress status of a running execution job"
)
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Returns live 8-stage execution progress for a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )
    return job.model_dump()
