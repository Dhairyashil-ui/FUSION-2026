"""FUSION 2026 - End-to-End GeoAI Processing Engine (Parts 1, 2, and 3 Integration).

Unifies the complete GeoAI workflow:
1. Part 1 Query Planner: Generates canonical 6-field summary and the Five Structured Plans.
2. Part 2 Data Retrieval Engine: Obtains vector, optical, elevation, and thematic datasets across 6 categories.
3. Part 2 Visual Detection Engine: Executes selected vision/foundation model adapters (Grounding DINO, YOLO-World, SAM 2, SegFormer, Prithvi, ChangeFormer, RemoteCLIP).
4. Part 3 GIS Engine: Performs metric distance math (EPSG:3857), 200m buffer filtering, and spatial joins.
5. Part 3 AI-to-Map Feature Matcher: Connects visual detections to mapped vector GIS features.
6. Part 3 Validation Engine: Audits geometries, CRS EPSG:4326, and lineage provenance.
7. Part 3 Output Engine: Generates GeoJSON FeatureCollection exports, CSV text tables, and interactive map layers.
"""

import logging
from typing import Optional, Dict, Any

from app.schemas.query_schema import QueryUnderstanding
from app.schemas.planner_schema import QueryPlan
from app.schemas.retrieval_schema import RetrievalExecutionResult
from app.schemas.vision_schema import VisualDetectionResult
from app.schemas.spatial_schema import (
    SpatialEngineResult,
    FinalValidationReport,
    FinalOutputDeliverable,
)

from app.services.query_planner import query_planner, QueryPlanner
from app.services.retrieval_engine import retrieval_engine, RetrievalEngine
from app.services.vision_engine import vision_engine, VisionEngine
from app.services.spatial_engine import spatial_engine, SpatialEngine
from app.services.validation_engine import validation_engine, ValidationEngine
from app.services.output_engine import output_engine, OutputEngine

logger = logging.getLogger(__name__)


class EndToEndResultPayload:
    """Full execution payload returned by EndToEndEngine."""
    def __init__(
        self,
        plan: QueryPlan,
        retrieval_result: RetrievalExecutionResult,
        visual_result: VisualDetectionResult,
        spatial_result: SpatialEngineResult,
        validation_report: FinalValidationReport,
        deliverable: FinalOutputDeliverable
    ):
        self.plan = plan
        self.retrieval_result = retrieval_result
        self.visual_result = visual_result
        self.spatial_result = spatial_result
        self.validation_report = validation_report
        self.deliverable = deliverable

    def model_dump(self) -> Dict[str, Any]:
        """Serializes full payload to dict."""
        return {
            "plan_id": self.plan.plan_id,
            "query_summary": self.plan.query_summary.model_dump(),
            "status": self.deliverable.status,
            "plan": self.plan.model_dump(),
            "retrieval_result": self.retrieval_result.model_dump(),
            "visual_detection_result": self.visual_result.model_dump(),
            "spatial_engine_result": self.spatial_result.model_dump(),
            "validation_report": self.validation_report.model_dump(),
            "final_deliverable": self.deliverable.model_dump()
        }


class EndToEndEngine:
    """Orchestrates end-to-end GeoAI execution across Parts 1, 2, and 3."""

    def __init__(
        self,
        planner: Optional[QueryPlanner] = None,
        retrieval: Optional[RetrievalEngine] = None,
        vision: Optional[VisionEngine] = None,
        spatial: Optional[SpatialEngine] = None,
        validator: Optional[ValidationEngine] = None,
        output: Optional[OutputEngine] = None
    ):
        self.query_planner = planner or query_planner
        self.retrieval_engine = retrieval or retrieval_engine
        self.vision_engine = vision or vision_engine
        self.spatial_engine = spatial or spatial_engine
        self.validation_engine = validator or validation_engine
        self.output_engine = output or output_engine

    def execute_end_to_end(self, understanding: QueryUnderstanding) -> EndToEndResultPayload:
        """
        Executes end-to-end GeoAI pipeline starting from QueryUnderstanding state.

        Args:
            understanding: Complete 6-field canonical QueryUnderstanding state.

        Returns:
            EndToEndResultPayload: Full pipeline execution payload.
        """
        logger.info(f"EndToEndEngine: Starting pipeline execution for query '{understanding.what.value}'")

        # 1. Part 1: Generate 5 Structured Plans
        plan: QueryPlan = self.query_planner.generate_plan(understanding)

        # 2. Part 2: Data Retrieval Engine (6 Categories)
        retrieval_res: RetrievalExecutionResult = self.retrieval_engine.execute_retrieval_plan(plan)

        # Extract AOI bbox
        aoi_bbox: Optional[List[float]] = None
        for asset in retrieval_res.assets:
            if asset.category == "Boundaries / AOI" and asset.spatial_bounds:
                b = asset.spatial_bounds
                if isinstance(b, dict) and "min_lon" in b:
                    aoi_bbox = [b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"]]
                    break

        # 3. Part 2: Visual Detection Engine (7 Vision Models)
        visual_res: VisualDetectionResult = self.vision_engine.execute_visual_detection_plan(plan, aoi_bbox=aoi_bbox)

        # 4. Part 3: GIS Spatial Engine & Feature Matcher (Metric 3857, 200m buffer)
        spatial_res: SpatialEngineResult = self.spatial_engine.execute_spatial_plan(
            plan=plan,
            retrieval_result=retrieval_res,
            visual_result=visual_res
        )

        # 5. Part 3: Validation and Provenance Engine
        val_report: FinalValidationReport = self.validation_engine.validate_spatial_results(spatial_res, target_crs="EPSG:4326")

        # 6. Part 3: Final Output and Visualization Engine
        deliverable: FinalOutputDeliverable = self.output_engine.generate_output(
            plan=plan,
            spatial_result=spatial_res,
            validation_report=val_report
        )

        logger.info(f"EndToEndEngine: Successfully completed execution for plan '{plan.plan_id}'")

        return EndToEndResultPayload(
            plan=plan,
            retrieval_result=retrieval_res,
            visual_result=visual_res,
            spatial_result=spatial_res,
            validation_report=val_report,
            deliverable=deliverable
        )


# Singleton Instance
end_to_end_engine = EndToEndEngine()
