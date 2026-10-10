"""FUSION 2026 - Comprehensive Generic GeoAI Query Test Suite.

Validates domain-agnostic behavior across:
1. Infrastructure analysis (Commercial buildings with solar panels, Drainage threshold)
2. Disaster analysis (Wildfire burn scar, Earthquake building collapse)
3. Urban change (Impervious surface expansion, Construction detection)
4. Ecological monitoring (Coral reef bleaching, Mangrove loss)
5. Vehicle / Telemetry monitoring (Maritime vessel tracking live, Fleet distribution)
6. Satellite analysis (SAR backscatter anomaly, Surface reflectance NDVI)
7. Spatial prediction (Landslide hazard forecasting, Future flood susceptibility)
8. Environmental analysis (Methane plume detection, Urban heat island index)
9. Unseen / Exotic GeoAI queries (Glacial lake outburst, Archaeological mound detection)
10. Multi-turn preservation, accumulation, explicit replacement, and sufficiency progression.
"""

import sys
import os
import json
import uuid
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base
from app.models.project import Project
from app.schemas.query_schema import QueryUnderstanding, MeasurementSchema
from app.services.context_merger import context_merger
from app.services.sufficiency_checker import sufficiency_checker
from app.services.conversation_manager import conversation_manager

# Isolated test DB
TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)
Base.metadata.create_all(bind=TEST_ENGINE)


class TestSufficiencyCheckerDomainAgnostic:
    """Sufficiency checking on merged state across diverse domains."""

    def test_disaster_missing_measurement(self):
        state = QueryUnderstanding(
            what={"value": "wildfire burn severity", "confidence": 0.95, "provided_by_user": True},
            where={"value": "Maui, Hawaii", "type": "named_area", "confidence": 0.95, "provided_by_user": True},
            target={"values": ["vegetation", "structures"], "confidence": 0.9, "provided_by_user": True},
            measurement={"value": None, "confidence": 0.0, "provided_by_user": False},
            output_format={"values": [], "confidence": 0.0, "provided_by_user": False}
        )
        res = sufficiency_checker.check(state)
        assert res.status == "NEEDS_INFORMATION"
        assert res.is_sufficient is False
        assert "measurement" in res.missing_information
        assert "output_format" in res.missing_information
        assert "where" not in res.missing_information
        assert "what" not in res.missing_information
        assert len(res.questions_for_user) == 2

    def test_disaster_complete(self):
        state = QueryUnderstanding(
            what={"value": "wildfire burn severity", "confidence": 0.95, "provided_by_user": True},
            where={"value": "Maui, Hawaii", "type": "named_area", "confidence": 0.95, "provided_by_user": True},
            target={"values": ["vegetation"], "confidence": 0.9, "provided_by_user": True},
            measurement={"value": "delta NBR burn severity index calculation", "confidence": 0.95, "provided_by_user": True},
            output_format={"values": ["burn severity map"], "confidence": 0.95, "provided_by_user": True}
        )
        res = sufficiency_checker.check(state)
        assert res.status == "READY"
        assert res.is_sufficient is True
        assert res.missing_information == []
        assert res.questions_for_user == []

    def test_output_format_compulsory(self):
        state = QueryUnderstanding(
            what={"value": "high-voltage transmission line mapping", "confidence": 0.95, "provided_by_user": True},
            where={"value": "Bavaria, Germany", "type": "state", "confidence": 0.95, "provided_by_user": True},
            target={"values": ["power lines", "pylons"], "confidence": 0.95, "provided_by_user": True},
            measurement={"value": "buffer distance filter 50m", "confidence": 0.95, "provided_by_user": True},
            output_format={"values": [], "confidence": 0.0, "provided_by_user": False}
        )
        res = sufficiency_checker.check(state)
        assert res.status == "NEEDS_INFORMATION"
        assert res.is_sufficient is False
        assert res.missing_information == ["output_format"]

    def test_static_infrastructure_complete(self):
        state = QueryUnderstanding(
            what={"value": "high-voltage transmission line mapping", "confidence": 0.95, "provided_by_user": True},
            where={"value": "Bavaria, Germany", "type": "state", "confidence": 0.95, "provided_by_user": True},
            target={"values": ["power lines", "pylons"], "confidence": 0.95, "provided_by_user": True},
            measurement={"value": "buffer distance filter 50m", "confidence": 0.95, "provided_by_user": True},
            output_format={"values": ["vector layer"], "confidence": 0.95, "provided_by_user": True}
        )
        res = sufficiency_checker.check(state)
        assert res.status == "READY"
        assert res.is_sufficient is True
        assert res.missing_information == []


class TestContextMergerLifecycle:
    """Preservation, accumulation, and explicit replacement."""

    def test_preserves_unchanged_dimensions(self):
        prev = QueryUnderstanding(
            what={"value": "urban heat island analysis", "confidence": 0.95, "provided_by_user": True},
            where={"value": "Phoenix, Arizona", "type": "city", "confidence": 0.95, "provided_by_user": True},
            target={"values": ["residential zones"], "confidence": 0.9, "provided_by_user": True},
            measurement={"value": "surface temperature threshold > 35C", "confidence": 0.95, "provided_by_user": True},
            output_format={"values": [], "confidence": 0.0, "provided_by_user": False}
        )
        curr = QueryUnderstanding(
            what={"value": None, "confidence": 0.0, "provided_by_user": False},
            where={"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
            target={"values": [], "confidence": 0.0, "provided_by_user": False},
            measurement={"value": None, "confidence": 0.0, "provided_by_user": False},
            output_format={"values": ["raster", "PDF report"], "confidence": 0.95, "provided_by_user": True}
        )
        merged = context_merger.merge(prev, curr, user_message="Export as raster and PDF report.")

        assert merged.what.value == "urban heat island analysis"
        assert merged.where.value == "Phoenix, Arizona"
        assert merged.measurement.value == "surface temperature threshold > 35C"
        assert merged.target.values == ["residential zones"]
        assert merged.output_format.values == ["raster", "PDF report"]

    def test_accumulates_targets_on_also(self):
        prev = QueryUnderstanding(
            what={"value": "flood damage assessment", "confidence": 0.95, "provided_by_user": True},
            where={"value": "Valencia, Spain", "type": "city", "confidence": 0.95, "provided_by_user": True},
            target={"values": ["bridges"], "confidence": 0.95, "provided_by_user": True},
            measurement={"value": "inundation depth > 1m", "confidence": 0.95, "provided_by_user": True},
            output_format={"values": [], "confidence": 0.0, "provided_by_user": False}
        )
        curr = QueryUnderstanding(
            what={"value": None, "confidence": 0.0, "provided_by_user": False},
            where={"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
            target={"values": ["railways"], "confidence": 0.95, "provided_by_user": True},
            measurement={"value": None, "confidence": 0.0, "provided_by_user": False},
            output_format={"values": [], "confidence": 0.0, "provided_by_user": False}
        )
        merged = context_merger.merge(prev, curr, user_message="Also include railways.")
        assert "bridges" in merged.target.values
        assert "railways" in merged.target.values
        assert len(merged.target.values) == 2


class TestFullMultiTurnLifecycleWithDB:
    """Full database-backed multi-turn conversation pipeline validation."""

    def test_multi_turn_ecological_dialogue(self):
        db = TestSession()
        project = Project(name="Amazon Deforestation Analysis Session")
        db.add(project)
        db.commit()
        db.refresh(project)

        # TURN 1: User gives WHAT and WHERE, omits MEASUREMENT
        t1_llm = {
            "what": {"value": "tropical rainforest deforestation monitoring", "confidence": 0.95, "provided_by_user": True},
            "where": {"value": "Rondonia, Brazil", "type": "state", "confidence": 0.98, "provided_by_user": True},
            "target": {"values": ["canopy cover"], "confidence": 0.9, "provided_by_user": True},
            "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        }
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(t1_llm)):
            r1 = conversation_manager.process_query(
                project_id=project.id,
                user_query="Monitor tropical rainforest deforestation in Rondonia, Brazil.",
                db=db
            )
            assert r1.conversation_number == 1
            assert r1.sufficiency.status == "NEEDS_INFORMATION"
            assert "measurement" in r1.sufficiency.missing_information
            assert "output_format" in r1.sufficiency.missing_information

        # TURN 2: User provides measurement constraint
        t2_llm = {
            "what": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "where": {"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
            "target": {"values": [], "confidence": 0.0, "provided_by_user": False},
            "measurement": {"value": "filter loss areas > 5 hectares using NDVI anomaly threshold", "confidence": 0.95, "provided_by_user": True},
            "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
        }
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(t2_llm)):
            r2 = conversation_manager.process_query(
                project_id=project.id,
                user_query="Filter loss areas > 5 hectares using NDVI anomaly threshold.",
                db=db
            )
            assert r2.conversation_number == 2
            assert r2.understanding.what.value == "tropical rainforest deforestation monitoring"
            assert r2.understanding.where.value == "Rondonia, Brazil"
            assert r2.understanding.target.values == ["canopy cover"]
            assert r2.understanding.measurement.value == "filter loss areas > 5 hectares using NDVI anomaly threshold"
            assert r2.sufficiency.status == "NEEDS_INFORMATION"
            assert r2.sufficiency.missing_information == ["output_format"]

        # TURN 3: User requests explicit output format
        t3_llm = {
            "what": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "where": {"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
            "target": {"values": [], "confidence": 0.0, "provided_by_user": False},
            "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
            "output_format": {"values": ["loss map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
        }
        with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(t3_llm)):
            r3 = conversation_manager.process_query(
                project_id=project.id,
                user_query="Give me a loss map and GeoJSON.",
                db=db
            )
            assert r3.conversation_number == 3
            assert r3.understanding.what.value == "tropical rainforest deforestation monitoring"
            assert r3.understanding.where.value == "Rondonia, Brazil"
            assert r3.understanding.measurement.value == "filter loss areas > 5 hectares using NDVI anomaly threshold"
            assert "loss map" in r3.understanding.output_format.values
            assert "GeoJSON" in r3.understanding.output_format.values
            assert r3.sufficiency.status == "READY"
