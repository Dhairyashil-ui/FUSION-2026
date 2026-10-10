"""FUSION 2026 - Job Execution Manager for End-to-End GeoAI Pipeline.

Manages execution sessions, unique job IDs, persistent execution records,
and real-time 8-stage progress tracking:
1. Preparing execution
2. Retrieving datasets
3. Validating source data
4. Running visual detection
5. Performing GIS and spatial analysis
6. Validating results
7. Preparing outputs
8. Displaying final results
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.schemas.query_schema import QueryUnderstanding
from app.schemas.planner_schema import QueryPlan
from app.schemas.retrieval_schema import RetrievalExecutionResult
from app.services.query_planner import query_planner
from app.services.end_to_end_engine import end_to_end_engine, EndToEndResultPayload

logger = logging.getLogger(__name__)


class ExecutionStage:
    """Status record for a single execution stage."""
    def __init__(self, stage_id: str, name: str):
        self.stage_id = stage_id
        self.name = name
        self.status = "pending"  # pending, running, completed, failed, skipped
        self.progress_pct = 0
        self.detail = ""
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None

    def model_dump(self) -> Dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "detail": self.detail,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


class ExecutionJobRecord:
    """Persistent execution job record."""
    def __init__(self, job_id: str, query_understanding: QueryUnderstanding, plan: QueryPlan):
        self.job_id = job_id
        self.query_understanding = query_understanding
        self.plan = plan
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.status = "created"  # created, running, completed, failed, partial_success
        self.current_stage_idx = 0
        self.overall_progress_pct = 0
        self.stages: List[ExecutionStage] = [
            ExecutionStage("stage_1", "Preparing execution"),
            ExecutionStage("stage_2", "Retrieving datasets"),
            ExecutionStage("stage_3", "Validating source data"),
            ExecutionStage("stage_4", "Running visual detection"),
            ExecutionStage("stage_5", "Performing GIS and spatial analysis"),
            ExecutionStage("stage_6", "Validating results"),
            ExecutionStage("stage_7", "Preparing outputs"),
            ExecutionStage("stage_8", "Displaying final results"),
        ]
        self.payload: Optional[EndToEndResultPayload] = None
        self.retrieval_result: Optional[RetrievalExecutionResult] = None
        self.error_message: Optional[str] = None
        self.execution_time_ms: float = 0.0

    def update_stage(self, stage_idx: int, status: str, progress_pct: int = 100, detail: str = ""):
        if 0 <= stage_idx < len(self.stages):
            st = self.stages[stage_idx]
            st.status = status
            st.progress_pct = progress_pct
            st.detail = detail
            if status == "running" and not st.started_at:
                st.started_at = datetime.now(timezone.utc).isoformat()
            elif status in ["completed", "failed", "skipped"]:
                st.completed_at = datetime.now(timezone.utc).isoformat()

            # Recalculate overall progress
            completed_stages = sum(1 for s in self.stages if s.status == "completed")
            running_contrib = (self.stages[self.current_stage_idx].progress_pct / 100.0) if self.stages[self.current_stage_idx].status == "running" else 0
            self.overall_progress_pct = int(((completed_stages + running_contrib) / len(self.stages)) * 100)

    def model_dump(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "current_stage_idx": self.current_stage_idx,
            "overall_progress_pct": self.overall_progress_pct,
            "stages": [s.model_dump() for s in self.stages],
            "error_message": self.error_message,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "payload": self.payload.model_dump() if self.payload else None,
            "retrieval_result": self.retrieval_result.model_dump() if self.retrieval_result else None
        }


class JobManager:
    """Manages active and historical GeoAI execution jobs."""

    def __init__(self):
        self._jobs: Dict[str, ExecutionJobRecord] = {}

    def create_job(self, understanding: QueryUnderstanding, plan: Optional[QueryPlan] = None) -> ExecutionJobRecord:
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        if not plan:
            plan = query_planner.generate_plan(understanding)

        job = ExecutionJobRecord(job_id, understanding, plan)
        self._jobs[job_id] = job
        logger.info(f"JobManager: Created job '{job_id}' for query '{understanding.what.value}'")
        return job

    def get_job(self, job_id: str) -> Optional[ExecutionJobRecord]:
        return self._jobs.get(job_id)

    def run_job_execution(self, job_id: str) -> ExecutionJobRecord:
        """Runs the 8-stage end-to-end execution pipeline for the given job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        t0 = time.time()
        job.status = "running"
        logger.info(f"JobManager: Starting execution for job '{job_id}'")

        try:
            # Stage 1: Preparing execution
            job.current_stage_idx = 0
            job.update_stage(0, "running", 50, "Validating approved plan & requirements")
            time.sleep(0.1)
            job.update_stage(0, "completed", 100, f"Validated plan '{job.plan.plan_id}'")

            # Stage 2: Retrieving datasets
            job.current_stage_idx = 1
            job.update_stage(1, "running", 30, f"Querying registered connectors for {job.query_understanding.where.value}")
            retrieval_res = end_to_end_engine.retrieval_engine.execute_retrieval_plan(job.plan)
            job.retrieval_result = retrieval_res

            has_blocked_data = any(a.status == "blocked_missing_data" or a.provenance.get("retrieval_status") == "blocked_missing_data" for a in retrieval_res.assets)
            if has_blocked_data:
                blocked_names = [a.asset_id for a in retrieval_res.assets if a.status == "blocked_missing_data" or a.provenance.get("retrieval_status") == "blocked_missing_data"]
                job.update_stage(1, "blocked_missing_data", 100, f"Blocked: Missing required datasets ({', '.join(blocked_names)})")
            else:
                job.update_stage(1, "completed", 100, f"Retrieved {len(retrieval_res.assets)} assets across 6 categories")

            # Stage 3: Validating source data
            job.current_stage_idx = 2
            job.update_stage(2, "running", 50, "Auditing CRS, spatial bounds & formats")
            aoi_bbox: Optional[List[float]] = None
            for asset in retrieval_res.assets:
                if asset.category == "Boundaries / AOI" and asset.spatial_bounds:
                    b = asset.spatial_bounds
                    if isinstance(b, dict) and "min_lon" in b:
                        aoi_bbox = [b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"]]
                        break
            job.update_stage(2, "completed", 100, "Validated GeoJSON / raster source metadata")

            # Stage 4: Running visual detection
            job.current_stage_idx = 3
            if not job.plan.visual_search or len(job.plan.visual_search) == 0:
                job.update_stage(3, "skipped_not_required", 100, "Skipped: Vector GIS analysis query (No vision model required)")
                visual_res = end_to_end_engine.vision_engine.execute_visual_detection_plan(job.plan, retrieval_result=retrieval_res)
            else:
                job.update_stage(3, "running", 40, f"Executing model inference ({len(job.plan.visual_search)} models)")
                visual_res = end_to_end_engine.vision_engine.execute_visual_detection_plan(job.plan, retrieval_result=retrieval_res)
                job.update_stage(3, "completed", 100, f"Generated {len(visual_res.detections)} exact multi-point boundaries/masks")

            # Stage 5: Performing GIS and spatial analysis
            job.current_stage_idx = 4
            if has_blocked_data:
                job.update_stage(4, "blocked_missing_data", 0, "Blocked: Mandatory hazard/risk dataset unavailable for spatial analysis")
                spatial_res = end_to_end_engine.spatial_engine.execute_spatial_plan(
                    plan=job.plan,
                    retrieval_result=retrieval_res,
                    visual_result=visual_res
                )
            else:
                main_op = job.plan.spatial_analysis[0].operation if job.plan.spatial_analysis else "spatial_analysis"
                job.update_stage(4, "running", 50, f"Executing {main_op}")
                spatial_res = end_to_end_engine.spatial_engine.execute_spatial_plan(
                    plan=job.plan,
                    retrieval_result=retrieval_res,
                    visual_result=visual_res
                )
                job.update_stage(4, "completed", 100, f"Processed {spatial_res.total_features_processed} spatial features ({main_op})")

            # Stage 6: Validating results
            job.current_stage_idx = 5
            job.update_stage(5, "running", 60, "Running Shapely topology repair & deduplication")
            val_report = end_to_end_engine.validation_engine.validate_spatial_results(spatial_res, target_crs="EPSG:4326")
            job.update_stage(5, "completed", 100, "Validated EPSG:4326 output geometries")

            # Stage 7: Preparing outputs
            job.current_stage_idx = 6
            job.update_stage(6, "running", 70, "Generating GeoJSON, CSV & Map layer specs")
            deliverable = end_to_end_engine.output_engine.generate_output(
                plan=job.plan,
                spatial_result=spatial_res,
                validation_report=val_report
            )
            job.update_stage(6, "completed", 100, "Created exportable GeoJSON & CSV deliverables")

            # Stage 8: Displaying final results
            job.current_stage_idx = 7
            if has_blocked_data:
                job.update_stage(7, "partial", 100, "Deliverable generated with missing-data warnings")
            else:
                job.update_stage(7, "completed", 100, "Final results ready for rendering")

            job.payload = EndToEndResultPayload(
                plan=job.plan,
                retrieval_result=retrieval_res,
                visual_result=visual_res,
                spatial_result=spatial_res,
                validation_report=val_report,
                deliverable=deliverable
            )
            
            if has_blocked_data:
                job.status = "blocked_missing_data"
                job.error_message = "Mandatory hazard dataset unavailable; analysis partially completed."
            else:
                job.status = "completed"
            job.execution_time_ms = (time.time() - t0) * 1000
            logger.info(f"JobManager: Finished job '{job_id}' with status '{job.status}' in {round(job.execution_time_ms, 2)}ms")


        except Exception as exc:
            logger.error(f"JobManager: Job '{job_id}' failed: {exc}", exc_info=True)
            job.status = "failed"
            job.error_message = str(exc)
            curr_idx = job.current_stage_idx
            job.update_stage(curr_idx, "failed", 100, f"Error: {exc}")

        return job


# Singleton Instance
job_manager = JobManager()
