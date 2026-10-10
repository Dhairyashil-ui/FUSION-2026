"""FUSION 2026 - Part 2 Data Retrieval & Visual Detection Integrated Engine.

Orchestrates the complete Part 2 execution pipeline:
1. Data Retrieval Engine: Fetches required datasets across the 6 categories using registered connectors.
2. Visual Detection Engine: Runs selected vision/foundation model adapters (Grounding DINO, YOLO-World, SAM 2, SegFormer, Prithvi, ChangeFormer, RemoteCLIP).
3. Produces dual structured outputs (Data Retrieval Result + Visual Detection Result) ready for Part 3 Spatial Analysis.
"""

import logging
from typing import Optional, Dict, Any, List

from app.schemas.planner_schema import QueryPlan
from app.schemas.retrieval_schema import RetrievalExecutionResult
from app.schemas.vision_schema import VisualDetectionResult, Part2ExecutionResult
from app.services.retrieval_engine import retrieval_engine, RetrievalEngine
from app.services.vision_engine import vision_engine, VisionEngine

logger = logging.getLogger(__name__)


class Part2Engine:
    """Integrated engine for Part 2 Data Retrieval and Visual Detection execution."""

    def __init__(
        self,
        retrieval: Optional[RetrievalEngine] = None,
        vision: Optional[VisionEngine] = None
    ):
        self.retrieval_engine = retrieval or retrieval_engine
        self.vision_engine = vision or vision_engine

    def execute_part2(self, plan: QueryPlan) -> Part2ExecutionResult:
        """
        Executes Part 2 Data Retrieval and Visual Detection plans for a given QueryPlan.

        Args:
            plan: Validated QueryPlan object from Part 1.

        Returns:
            Part2ExecutionResult: Dual structured outputs containing retrieval assets and model detections.
        """
        logger.info(f"Part2Engine: Starting Part 2 execution for plan '{plan.plan_id}'")

        # 1. Execute Data Retrieval Engine across 6 categories
        retrieval_result: RetrievalExecutionResult = self.retrieval_engine.execute_retrieval_plan(plan)

        # Extract AOI bounding box if available from administrative boundary asset
        aoi_bbox: Optional[List[float]] = None
        for asset in retrieval_result.assets:
            if asset.category == "Boundaries / AOI" and asset.spatial_bounds:
                b = asset.spatial_bounds
                if isinstance(b, dict) and "min_lon" in b:
                    aoi_bbox = [b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"]]
                    break


        # 2. Execute Visual Detection Engine for selected models
        visual_result: VisualDetectionResult = self.vision_engine.execute_visual_detection_plan(plan, aoi_bbox=aoi_bbox)

        # 3. Determine overall Part 2 status
        overall_status = "completed"
        if retrieval_result.status != "completed" or visual_result.status != "completed":
            overall_status = "partial_success"
        if retrieval_result.status == "error" and visual_result.status == "error":
            overall_status = "error"

        summary = (
            f"Part 2 Execution Completed! "
            f"Retrieved {retrieval_result.total_assets_retrieved} GIS datasets; "
            f"Generated {visual_result.total_detections} visual detections across models ({', '.join(visual_result.selected_models)})."
        )

        return Part2ExecutionResult(
            plan_id=plan.plan_id,
            retrieval_result=retrieval_result.model_dump(),
            visual_detection_result=visual_result,
            status=overall_status,
            execution_summary=summary
        )


# Singleton Instance
part2_engine = Part2Engine()
