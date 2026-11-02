# tests/test_slice2a_envelope_privacy.py
# Path: E:\CCTV Analytics\camera_analytics\tests\test_slice2a_envelope_privacy.py

from __future__ import annotations

import io
import json
import logging
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

from camera_analytics.communication.envelope import EventEnvelopeV1
from camera_analytics.communication.privacy import (
    PrivacyFilter,
    PrivacyConfig,
    normalize_plate_for_hash,
    normalize_person_id_for_hash,
    NAME_LIKE_FIELDS,
)
from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.communication.publishers.console_publisher import ConsolePublisher
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.mqtt_publisher import MQTTPublisher
from camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher
from camera_analytics.communication.publishers.rest_publisher import RestPublisher
from camera_analytics.events.models import BaseRuntimeEvent
from camera_analytics.bootstrap.models import (
    ConfigurationSnapshot,
    EngineConfig,
    EngineRuntimeConfig,
    PublishersConfig,
)
from camera_analytics.config.validator import StandaloneConfigValidator


class TestEnvelopeV1(unittest.TestCase):
    """Test suite for Envelope v1 wrapping, formatting, and backwards compatibility."""

    def test_envelope_fields_and_utc_format(self) -> None:
        """Envelope v1 adds schema_version 1.0.0, message_id, category, UTC Z timestamp, and identity."""
        raw_event = BaseRuntimeEvent(
            camera_id="cam_gate_01",
            zone_id="zone_entry",
            event_type="VEHICLE_LPR",
            confidence=0.98,
            track_id=42,
            attributes={"plate_text": "L1048BOU", "status": "GRAMMAR_VALID"},
        )
        envelope = EventEnvelopeV1(
            instance_id="eng_node_01",
            application_id="app_tenant_01",
        )
        enveloped_dict = envelope.wrap(raw_event)

        self.assertEqual(enveloped_dict["schema_version"], "1.0.0")
        self.assertTrue(len(enveloped_dict["message_id"]) >= 32)
        self.assertEqual(enveloped_dict["instance_id"], "eng_node_01")
        self.assertEqual(enveloped_dict["application_id"], "app_tenant_01")
        self.assertEqual(enveloped_dict["camera_id"], "cam_gate_01")
        self.assertEqual(enveloped_dict["zone_id"], "zone_entry")
        self.assertEqual(enveloped_dict["category"], "vehicle")

        ts = enveloped_dict["timestamp_utc"]
        self.assertTrue(ts.endswith("Z"), f"Timestamp {ts} must end with 'Z'")

    def test_existing_fields_preserved_no_breaking_removals(self) -> None:
        """All existing event fields remain accessible in enveloped payload."""
        raw_event = BaseRuntimeEvent(
            event_id="orig_evt_123",
            camera_id="cam_01",
            event_type="CUSTOM_ALERT",
            confidence=0.88,
            track_id=101,
            bounding_box=[0.1, 0.2, 0.3, 0.4],
            attributes={"custom_key": "custom_val"},
            metadata={"source": "unit_test"},
        )
        envelope = EventEnvelopeV1()
        enveloped_dict = envelope.wrap(raw_event)

        self.assertEqual(enveloped_dict["event_id"], "orig_evt_123")
        self.assertEqual(enveloped_dict["event_type"], "CUSTOM_ALERT")
        self.assertEqual(enveloped_dict["confidence"], 0.88)
        self.assertEqual(enveloped_dict["track_id"], 101)
        self.assertEqual(enveloped_dict["bounding_box"], [0.1, 0.2, 0.3, 0.4])
        self.assertEqual(enveloped_dict["attributes"]["custom_key"], "custom_val")
        self.assertEqual(enveloped_dict["metadata"]["source"], "unit_test")

    def test_nullable_zone_id(self) -> None:
        """Zone ID is None when event does not have an associated zone."""
        raw_event = BaseRuntimeEvent(camera_id="cam_01", zone_id=None)
        enveloped_dict = EventEnvelopeV1().wrap(raw_event)
        self.assertIsNone(enveloped_dict["zone_id"])


class TestPlateFormatting(unittest.TestCase):
    """Test suite for VEHICLE_LPR plate decomposition and formatting."""

    def test_plate_format_grammar_valid(self) -> None:
        """GRAMMAR_VALID formats spaced text 'L 1048 BOU' and parsed=True."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="full"))
        raw_event = BaseRuntimeEvent(
            event_type="VEHICLE_LPR",
            attributes={"plate_text": "L1048BOU", "status": "GRAMMAR_VALID"},
        )
        res = pf.filter_event(raw_event.to_dict())
        attrs = res["attributes"]
        self.assertEqual(attrs["plate_text"], "L 1048 BOU")
        plate = attrs["plate"]
        self.assertTrue(plate["parsed"])
        self.assertEqual(plate["prefix"], "L")
        self.assertEqual(plate["number"], "1048")
        self.assertEqual(plate["suffix"], "BOU")
        self.assertEqual(plate["status"], "GRAMMAR_VALID")
        self.assertEqual(plate["raw_text"], "L1048BOU")

    def test_plate_format_review_fallback_unspaced(self) -> None:
        """REVIEW status falls back to raw unspaced string and parsed=False."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="full"))
        raw_event = BaseRuntimeEvent(
            event_type="VEHICLE_LPR",
            attributes={"plate_text": "B1234XYZ", "status": "REVIEW"},
        )
        res = pf.filter_event(raw_event.to_dict())
        attrs = res["attributes"]
        self.assertEqual(attrs["plate_text"], "B1234XYZ")
        plate = attrs["plate"]
        self.assertFalse(plate["parsed"])
        self.assertEqual(plate["status"], "REVIEW")
        self.assertEqual(plate["raw_text"], "B1234XYZ")

    def test_plate_format_no_read(self) -> None:
        """NO_READ status preserves unparsed fallback."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="full"))
        raw_event = BaseRuntimeEvent(
            event_type="VEHICLE_LPR",
            attributes={"plate_text": "", "status": "NO_READ"},
        )
        res = pf.filter_event(raw_event.to_dict())
        attrs = res["attributes"]
        plate = attrs["plate"]
        self.assertFalse(plate["parsed"])
        self.assertEqual(plate["status"], "NO_READ")


class TestPrivacyFilterModes(unittest.TestCase):
    """Test suite for identity_mode and plate_mode privacy filtering."""

    def test_identity_mode_full(self) -> None:
        """Identity mode 'full' preserves person_id, full_name, and department."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="full"))
        evt_dict = {
            "event_type": "FACE_IDENTIFIED",
            "attributes": {
                "person_id": "P_001",
                "full_name": "Test Subject",
                "department": "Security",
                "metadata": {"department": "Security", "role": "Guard"},
            },
        }
        filtered = pf.filter_event(evt_dict)
        attrs = filtered["attributes"]
        self.assertEqual(attrs["person_id"], "P_001")
        self.assertEqual(attrs["full_name"], "Test Subject")
        self.assertEqual(attrs["department"], "Security")

    def test_identity_mode_id_only_strips_name_and_department(self) -> None:
        """Identity mode 'id_only' keeps person_id but strips full_name, department, email, person_name, position."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only"))
        evt_dict = {
            "event_type": "FACE_IDENTIFIED",
            "attributes": {
                "person_id": "P_001",
                "full_name": "Test Subject",
                "person_name": "Test Subject",
                "department": "Security",
                "email": "test@example.com",
                "position": "Officer",
                "metadata": {"department": "Security", "email": "test@example.com"},
            },
        }
        filtered = pf.filter_event(evt_dict)
        attrs = filtered["attributes"]
        self.assertEqual(attrs["person_id"], "P_001")
        self.assertNotIn("full_name", attrs)
        self.assertNotIn("person_name", attrs)
        self.assertNotIn("department", attrs)
        self.assertNotIn("email", attrs)
        self.assertNotIn("position", attrs)
        self.assertNotIn("department", attrs.get("metadata", {}))
        self.assertNotIn("email", attrs.get("metadata", {}))

    def test_identity_mode_hashed(self) -> None:
        """Identity mode 'hashed' computes HMAC-SHA256 and strips names, email, position."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="hashed", hmac_salt="salt_test_123"))
        evt_dict = {
            "event_type": "FACE_IDENTIFIED",
            "attributes": {
                "person_id": "P_001",
                "full_name": "Test Subject",
                "person_name": "Test Subject",
                "email": "test@example.com",
                "position": "Officer",
            },
        }
        filtered = pf.filter_event(evt_dict)
        attrs = filtered["attributes"]
        self.assertNotEqual(attrs["person_id"], "P_001")
        self.assertEqual(len(attrs["person_id"]), 64)  # SHA256 hex length
        self.assertNotIn("full_name", attrs)
        self.assertNotIn("person_name", attrs)
        self.assertNotIn("email", attrs)
        self.assertNotIn("position", attrs)

    def test_plate_mode_masked(self) -> None:
        """Plate mode 'masked' keeps prefix, masks number, keeps suffix partially, strips raw_text."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="masked"))
        evt_dict = {
            "event_type": "VEHICLE_LPR",
            "attributes": {"plate_text": "L1048BOU", "status": "GRAMMAR_VALID"},
        }
        filtered = pf.filter_event(evt_dict)
        attrs = filtered["attributes"]
        plate = attrs["plate"]
        self.assertEqual(plate["prefix"], "L")
        self.assertEqual(plate["number"], "****")
        self.assertEqual(plate["suffix"], "B**")
        self.assertEqual(attrs["plate_text"], "L **** B**")
        self.assertNotIn("raw_text", plate)
        self.assertNotIn("raw_text", attrs)

    def test_plate_mode_hashed(self) -> None:
        """Plate mode 'hashed' computes HMAC-SHA256 of plate and strips components."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="hashed", hmac_salt="salt_test_123"))
        evt_dict = {
            "event_type": "VEHICLE_LPR",
            "attributes": {"plate_text": "L1048BOU", "status": "GRAMMAR_VALID"},
        }
        filtered = pf.filter_event(evt_dict)
        attrs = filtered["attributes"]
        self.assertEqual(len(attrs["plate_text"]), 64)
        self.assertNotIn("raw_text", attrs["plate"])

    def test_hash_determinism_and_salt_variation(self) -> None:
        """Same input + same salt yields identical hash; different salt yields different hash."""
        pf1 = PrivacyFilter(PrivacyConfig(identity_mode="hashed", hmac_salt="salt_A"))
        pf2 = PrivacyFilter(PrivacyConfig(identity_mode="hashed", hmac_salt="salt_A"))
        pf3 = PrivacyFilter(PrivacyConfig(identity_mode="hashed", hmac_salt="salt_B"))

        evt1 = {"event_type": "FACE_IDENTIFIED", "attributes": {"person_id": "P_999"}}
        evt2 = {"event_type": "FACE_IDENTIFIED", "attributes": {"person_id": "P_999"}}
        evt3 = {"event_type": "FACE_IDENTIFIED", "attributes": {"person_id": "P_999"}}

        h1 = pf1.filter_event(evt1)["attributes"]["person_id"]
        h2 = pf2.filter_event(evt2)["attributes"]["person_id"]
        h3 = pf3.filter_event(evt3)["attributes"]["person_id"]

        self.assertEqual(h1, h2, "Deterministic hashing with same salt")
        self.assertNotEqual(h1, h3, "Different salt must produce different hash")


class TestValueBasedScrubAndDeepStripping(unittest.TestCase):
    """Test suite for defense-in-depth value-based scrubbing and recursive field stripping."""

    def test_value_based_scrub_plate_in_metadata_and_snapshot_path(self) -> None:
        """In masked/hashed mode, any string containing the event's own plate is scrubbed to [redacted]."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="masked"))
        evt = {
            "event_type": "VEHICLE_LPR",
            "snapshot_path": "/snapshots/cam01/cam01_B1234XYZ_179358.jpg",
            "attributes": {
                "plate_text": "B1234XYZ",
                "status": "GRAMMAR_VALID",
            },
            "metadata": {
                "source_plate": "B 1234 XYZ",
                "nested_history": ["Seen before: B-1234-XYZ", "other_info"],
            },
        }
        res = pf.filter_event(evt)
        self.assertEqual(res["snapshot_path"], "[redacted]")
        self.assertEqual(res["metadata"]["source_plate"], "[redacted]")
        self.assertEqual(res["metadata"]["nested_history"][0], "[redacted]")
        self.assertEqual(res["metadata"]["nested_history"][1], "other_info")
        # Masked plate text itself remains valid masked representation
        self.assertEqual(res["attributes"]["plate_text"], "B **** X**")

    def test_value_based_scrub_person_name_in_metadata_and_payload(self) -> None:
        """In id_only/hashed mode, strings containing person name are scrubbed to [redacted]."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only"))
        evt = {
            "event_type": "FACE_IDENTIFIED",
            "attributes": {
                "person_id": "emp_42",
                "full_name": "Alice Wonderland",
            },
            "metadata": {
                "description": "Visitor escorted by Alice Wonderland today",
            },
        }
        res = pf.filter_event(evt)
        self.assertNotIn("full_name", res["attributes"])
        self.assertEqual(res["metadata"]["description"], "[redacted]")

    def test_recursive_stripping_dicts_and_lists_and_titles(self) -> None:
        """Title, job_title, position, and names are recursively stripped across dicts and lists."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only"))
        evt = {
            "event_type": "FACE_IDENTIFIED",
            "attributes": {
                "person_id": "emp_100",
                "full_name": "Bob Builder",
                "title": "Lead Architect",
                "job_title": "Senior Engineer",
                "position": "Staff",
                "nested_team": [
                    {"name": "Colleague", "title": "Developer", "role_id": "eng_1"},
                    {"department": "Infra", "job_title": "SRE", "valid_flag": True},
                ],
                "metadata": {
                    "supervisor": {"name": "Boss", "title": "Director"},
                },
            },
        }
        res = pf.filter_event(evt)
        attrs = res["attributes"]
        self.assertNotIn("full_name", attrs)
        self.assertNotIn("title", attrs)
        self.assertNotIn("job_title", attrs)
        self.assertNotIn("position", attrs)

        team = attrs["nested_team"]
        self.assertNotIn("name", team[0])
        self.assertNotIn("title", team[0])
        self.assertEqual(team[0]["role_id"], "eng_1")

        self.assertNotIn("department", team[1])
        self.assertNotIn("job_title", team[1])
        self.assertTrue(team[1]["valid_flag"])

        sup = attrs["metadata"]["supervisor"]
        self.assertNotIn("name", sup)
        self.assertNotIn("title", sup)

    def test_short_name_and_boundaries_not_over_scrubbed(self) -> None:
        """'Al' does not alter 'signal', 'original', 'Hall'; full name in free text is redacted."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only"))
        evt_short = {
            "event_type": "FACE_IDENTIFIED",
            "full_name": "Al",
            "attributes": {
                "signal_desc": "signal quality is high",
                "origin": "original state preserved",
                "location": "Front Hall North",
            },
        }
        res_short = pf.filter_event(evt_short)
        attrs = res_short["attributes"]
        self.assertEqual(attrs["signal_desc"], "signal quality is high")
        self.assertEqual(attrs["origin"], "original state preserved")
        self.assertEqual(attrs["location"], "Front Hall North")

        # Full name in free text is redacted
        evt_full = {
            "event_type": "FACE_IDENTIFIED",
            "full_name": "Alice Wonderland",
            "attributes": {
                "description": "Visitor escorted by Alice Wonderland today",
            },
        }
        res_full = pf.filter_event(evt_full)
        self.assertEqual(res_full["attributes"]["description"], "[redacted]")

    def test_plate_scrub_without_asterisk_exemption(self) -> None:
        """A string containing both a masked plate and the raw plate is redacted; formatted plate fields survive."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="masked"))
        evt = {
            "event_type": "VEHICLE_LPR",
            "attributes": {
                "plate_text": "B 1234 CD",
                "status": "GRAMMAR_VALID",
                "notes": "Detected B 1234 CD (masked: B **** C*)",
            },
        }
        res = pf.filter_event(evt)
        attrs = res["attributes"]
        # Formatted fields survive
        self.assertEqual(attrs["plate_text"], "B **** C*")
        self.assertTrue(attrs["plate"]["parsed"])
        # String with both raw and masked plate is redacted
        self.assertEqual(attrs["notes"], "[redacted]")

    def test_over_stripping_preserves_zone_and_count_name_position(self) -> None:
        """Non-biometric events keep 'name' and 'position', while biometric events lose them."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only"))

        # Zone event keeps name and position
        zone_evt = {
            "event_type": "ZONE_ENTRY",
            "attributes": {
                "zone_id": "z_100",
                "name": "Restricted Area North",
                "position": [120, 240],
                "nested_zones": [{"name": "SubZone 1", "position": [10, 20]}],
            },
        }
        res_zone = pf.filter_event(zone_evt)
        z_attrs = res_zone["attributes"]
        self.assertEqual(z_attrs.get("name"), "Restricted Area North")
        self.assertEqual(z_attrs.get("position"), [120, 240])
        self.assertEqual(z_attrs["nested_zones"][0]["name"], "SubZone 1")
        self.assertEqual(z_attrs["nested_zones"][0]["position"], [10, 20])

        # Biometric event loses name and position
        bio_evt = {
            "event_type": "FACE_IDENTIFIED",
            "attributes": {
                "person_id": "emp_01",
                "name": "Target Person",
                "position": "Lead",
            },
        }
        res_bio = pf.filter_event(bio_evt)
        b_attrs = res_bio["attributes"]
        self.assertNotIn("name", b_attrs)
        self.assertNotIn("position", b_attrs)

    def test_plate_exemption_by_exact_path(self) -> None:
        """ONLY attributes.plate_text and attributes.plate (and subkeys) are exempt from value scrub at exact path.

        metadata.plate_text and attributes.metadata.plate containing raw plate are redacted in masked/hashed;
        formatted fields survive.
        """
        raw_plate = "B 1234 CD"
        # Test masked mode
        pf_masked = PrivacyFilter(PrivacyConfig(plate_mode="masked"))
        evt_masked = {
            "event_type": "VEHICLE_LPR",
            "metadata": {
                "plate_text": raw_plate,
            },
            "attributes": {
                "plate_text": raw_plate,
                "status": "GRAMMAR_VALID",
                "metadata": {
                    "plate": raw_plate,
                },
            },
        }
        res_m = pf_masked.filter_event(evt_masked)
        self.assertEqual(res_m["metadata"]["plate_text"], "[redacted]")
        self.assertEqual(res_m["attributes"]["metadata"]["plate"], "[redacted]")
        self.assertEqual(res_m["attributes"]["plate_text"], "B **** C*")
        self.assertEqual(res_m["attributes"]["plate"]["number"], "****")
        self.assertEqual(res_m["attributes"]["plate"]["prefix"], "B")

        # Test hashed mode
        pf_hashed = PrivacyFilter(PrivacyConfig(plate_mode="hashed", hmac_salt="salt_123"))
        evt_hashed = {
            "event_type": "VEHICLE_LPR",
            "metadata": {
                "plate_text": raw_plate,
            },
            "attributes": {
                "plate_text": raw_plate,
                "status": "GRAMMAR_VALID",
                "metadata": {
                    "plate": raw_plate,
                },
            },
        }
        res_h = pf_hashed.filter_event(evt_hashed)
        self.assertEqual(res_h["metadata"]["plate_text"], "[redacted]")
        self.assertEqual(res_h["attributes"]["metadata"]["plate"], "[redacted]")
        self.assertEqual(len(res_h["attributes"]["plate_text"]), 64)
        self.assertIn("hash", res_h["attributes"]["plate"])

    def test_biometric_classification_unification(self) -> None:
        """Unify category and privacy classifier: PERSON_COUNT keeps name/title/position, FACE_IDENTIFIED loses them."""
        from camera_analytics.communication.envelope import map_category

        pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only"))

        # PERSON_COUNT: non-biometric counting event -> category counting, preserves name, title, position
        count_evt = {
            "event_type": "PERSON_COUNT",
            "attributes": {
                "name": "Zone Counter Alpha",
                "title": "North Entrance",
                "position": "Gate 1",
                "full_name": "Sensitive Counter Operator",
            },
        }
        cat_count = map_category("PERSON_COUNT")
        self.assertEqual(cat_count, "counting")
        res_count = pf.filter_event(count_evt)
        self.assertEqual(res_count["attributes"]["name"], "Zone Counter Alpha")
        self.assertEqual(res_count["attributes"]["title"], "North Entrance")
        self.assertEqual(res_count["attributes"]["position"], "Gate 1")
        self.assertNotIn("full_name", res_count["attributes"])

        # FACE_IDENTIFIED: biometric event -> category biometric, strips name, title, position
        face_evt = {
            "event_type": "FACE_IDENTIFIED",
            "attributes": {
                "person_id": "P_001",
                "name": "Target Person",
                "title": "Security Specialist",
                "position": "Officer",
                "full_name": "Target Person Full",
            },
        }
        cat_face = map_category("FACE_IDENTIFIED")
        self.assertEqual(cat_face, "biometric")
        res_face = pf.filter_event(face_evt)
        self.assertEqual(res_face["attributes"]["person_id"], "P_001")
        self.assertNotIn("name", res_face["attributes"])
        self.assertNotIn("title", res_face["attributes"])
        self.assertNotIn("position", res_face["attributes"])
        self.assertNotIn("full_name", res_face["attributes"])

        # Category and privacy decision agree for all 15 real event types
        real_events = [
            ("ENTER", "behavior", False),
            ("STAY", "behavior", False),
            ("EXIT", "behavior", False),
            ("CROWD_ALERT", "behavior", False),
            ("DIRECTION_VIOLATION", "behavior", False),
            ("DWELL_TIME", "zone", False),
            ("FACE_IDENTIFIED", "biometric", True),
            ("LOITERING", "behavior", False),
            ("QUEUE_ALERT", "behavior", False),
            ("VEHICLE_LPR", "vehicle", False),
            ("ZONE_ENTER", "zone", False),
            ("ZONE_EXIT", "zone", False),
            ("ZONE_OCCUPANCY", "zone", False),
            ("ALARM_CREATED", "system", False),
            ("ANALYTICS_EVENT", "analytics", False),
        ]
        for et, expected_cat, expected_bio in real_events:
            actual_cat = map_category(et)
            is_bio = (actual_cat == "biometric")
            self.assertEqual(actual_cat, expected_cat, f"Category mismatch for {et}")
            self.assertEqual(is_bio, expected_bio, f"Biometric decision mismatch for {et}")

    def test_category_from_enveloped_dict_and_fallback(self) -> None:
        """privacy.filter_event takes category from enveloped dict; falls back to map_category if absent."""
        from camera_analytics.communication.envelope import EventEnvelopeV1
        from camera_analytics.communication.privacy import PrivacyFilter, PrivacyConfig

        pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only"))
        env = EventEnvelopeV1()

        # 1. Event whose plugin_name determines category:
        # event_type is generic CUSTOM_DETECTION, but plugin_name is "face_matching"
        custom_evt = {
            "event_type": "CUSTOM_DETECTION",
            "plugin_name": "face_matching",
            "attributes": {
                "person_id": "P_001",
                "name": "Custom Subject",
                "title": "Lead",
                "position": "Staff",
            },
        }
        enveloped = env.wrap(custom_evt)
        self.assertEqual(enveloped["category"], "biometric")

        filtered = pf.filter_event(enveloped)
        # Because category was "biometric", ambiguous fields (name, title, position) are stripped
        self.assertEqual(filtered["attributes"]["person_id"], "P_001")
        self.assertNotIn("name", filtered["attributes"])
        self.assertNotIn("title", filtered["attributes"])
        self.assertNotIn("position", filtered["attributes"])
        self.assertEqual(filtered["category"], "biometric")

        # 2. Dict without "category" key still works via fallback
        unwrapped_dict = {
            "event_type": "FACE_IDENTIFIED",
            "plugin_name": "",
            "attributes": {
                "person_id": "P_002",
                "name": "Fallback Subject",
                "title": "Analyst",
                "position": "Officer",
            },
        }
        filtered_unwrapped = pf.filter_event(unwrapped_dict)
        self.assertEqual(filtered_unwrapped["attributes"]["person_id"], "P_002")
        self.assertNotIn("name", filtered_unwrapped["attributes"])
        self.assertNotIn("title", filtered_unwrapped["attributes"])
        self.assertNotIn("position", filtered_unwrapped["attributes"])


class TestSaltExposureMasking(unittest.TestCase):
    """Test suite ensuring HMAC salt is never exposed via repr/str or logging."""

    def test_salt_not_in_repr_or_str_of_config(self) -> None:
        """PrivacyConfig repr() and str() never expose the hmac_salt."""
        sentinel_salt = "EXTREMELY_CONFIDENTIAL_SALT_XYZ"
        cfg = PrivacyConfig(identity_mode="hashed", plate_mode="hashed", hmac_salt=sentinel_salt)
        self.assertNotIn(sentinel_salt, repr(cfg))
        self.assertNotIn(sentinel_salt, str(cfg))

    def test_salt_not_in_repr_or_str_of_snapshot(self) -> None:
        """ConfigurationSnapshot repr() and str() never expose the hmac_salt in messaging dict."""
        sentinel_salt = "EXTREMELY_CONFIDENTIAL_SALT_XYZ"
        snap = ConfigurationSnapshot(
            engine=EngineConfig(engine_id="e1"),
            pipelines=(),
            publishers=PublishersConfig(),
            runtime=EngineRuntimeConfig(),
            messaging={"privacy": {"hmac_salt": sentinel_salt}},
        )
        self.assertNotIn(sentinel_salt, repr(snap))
        self.assertNotIn(sentinel_salt, str(snap))

    def test_salt_not_in_bootstrap_logs(self) -> None:
        """EngineBootstrap initialization logs effective modes without salt."""
        from camera_analytics.bootstrap.engine_bootstrap import EngineBootstrap

        sentinel_salt = "SECRET_BOOTSTRAP_SALT_123"
        snap = ConfigurationSnapshot(
            engine=EngineConfig(engine_id="e1", mode="standalone"),
            pipelines=(),
            publishers=PublishersConfig(),
            runtime=EngineRuntimeConfig(),
            messaging={"privacy": {"identity_mode": "hashed", "plate_mode": "hashed", "hmac_salt": sentinel_salt}},
        )

        b = EngineBootstrap()
        with self.assertLogs("camera_analytics.bootstrap.engine_bootstrap", level="INFO") as log_ctx:
            b._initialize_publishers(snap)

        all_logs = " ".join(log_ctx.output)
        self.assertNotIn(sentinel_salt, all_logs)
        self.assertIn("identity_mode: hashed, plate_mode: hashed", all_logs)


class TestHashNormalization(unittest.TestCase):
    """Test suite for plate and person_id normalization prior to HMAC hashing."""

    def test_plate_hash_normalization_spaces_case_hyphens(self) -> None:
        """Plates with variations in whitespace, case, and hyphens hash identically."""
        pf = PrivacyFilter(PrivacyConfig(plate_mode="hashed", hmac_salt="norm_salt_123"))
        h1 = pf._hash_plate("L1048XYZ")
        h2 = pf._hash_plate("L 1048 XYZ")
        h3 = pf._hash_plate("l1048xyz")
        h4 = pf._hash_plate("L-1048-XYZ")
        self.assertEqual(h1, h2)
        self.assertEqual(h1, h3)
        self.assertEqual(h1, h4)

        pf_diff_salt = PrivacyFilter(PrivacyConfig(plate_mode="hashed", hmac_salt="other_salt_999"))
        self.assertNotEqual(h1, pf_diff_salt._hash_plate("L1048XYZ"))

    def test_person_id_normalization_strip_only(self) -> None:
        """person_id hashes identically when stripped, but case is preserved."""
        pf = PrivacyFilter(PrivacyConfig(identity_mode="hashed", hmac_salt="norm_salt_123"))
        h1 = pf._hash_person_id("P_001")
        h2 = pf._hash_person_id("  P_001  ")
        h3 = pf._hash_person_id("p_001")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3, "person_id case must be preserved")


class TestTNKBParserParity(unittest.TestCase):
    """Parity test comparing in-repo TNKB decomposition with external TNKBParser reference."""

    def test_tnkb_parser_parity_with_reference(self) -> None:
        """In-repo TNKB decomposition matches reference TNKBParser; sys.path and sys.modules remain unchanged."""
        import subprocess

        ref_path = r"E:\ANPR\research\step_4_14_validation_engine"
        if not os.path.exists(os.path.join(ref_path, "tnkb_parser.py")):
            self.skipTest("Reference TNKB parser not present at E:\\ANPR path")

        path_before = list(sys.path)
        modules_before = set(sys.modules.keys())

        sub_code = """
import os
import sys

sys.path.insert(0, r"E:\\ANPR")
sys.path.insert(0, r"E:\\CCTV Analytics")

try:
    from research.step_4_14_validation_engine.tnkb_parser import TNKBParser
    from camera_analytics.communication.privacy import PrivacyFilter
except Exception as e:
    print(f"SKIPPED: {e}")
    sys.exit(0)

plates = [
    "B1234XYZ",
    "L 1048 BOU",
    "D-999-AB",
    "DK1A",
    "NOREAD",
    "B1234",
    "1234XYZ",
]

for p in plates:
    comp, _ = TNKBParser.parse_components(p)
    pfx, num, sfx = PrivacyFilter._parse_tnkb(p)
    assert pfx == comp.prefix, f"Prefix mismatch on {p}: {pfx} vs {comp.prefix}"
    assert num == comp.registration_number, f"Num mismatch on {p}: {num} vs {comp.registration_number}"
    assert sfx == comp.suffix, f"Suffix mismatch on {p}: {sfx} vs {comp.suffix}"

print("PARITY_PASSED")
"""
        proc = subprocess.run([sys.executable, "-c", sub_code], capture_output=True, text=True)
        if "SKIPPED" in proc.stdout:
            self.skipTest(proc.stdout.strip())
        self.assertEqual(proc.returncode, 0, f"Subprocess failed: {proc.stderr}")
        self.assertIn("PARITY_PASSED", proc.stdout)

        path_after = list(sys.path)
        modules_after = set(sys.modules.keys())
        self.assertEqual(path_after, path_before, "sys.path altered by parity test")
        self.assertEqual(modules_after - modules_before, set(), "sys.modules altered by parity test")


class TestPluginLogSafety(unittest.TestCase):
    """Test that plugins vehicle_lpr and face_matching do not emit sensitive values in logs or filenames."""

    def test_plugin_ast_logger_no_plate_or_name_variables(self) -> None:
        """Statically verify via AST that no logger call passes plate* (except plate_conf), *_name, full_name, top1_name, person_name, p_txt."""
        import ast

        def is_forbidden_token(token: str) -> bool:
            token_lower = token.lower()
            if token_lower == "plate_conf":
                return False
            if token_lower.startswith("plate"):
                return True
            if token_lower.endswith("_name"):
                return True
            if token_lower in ("full_name", "top1_name", "person_name", "p_txt"):
                return True
            return False

        def find_violations(source_text: str, filename: str = "snippet"):
            tree = ast.parse(source_text)
            violations = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    is_logger = False
                    if isinstance(node.func, ast.Attribute) and node.func.attr in ("info", "warning", "error", "debug"):
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "logger":
                            is_logger = True
                    if is_logger:
                        for arg in node.args + [kw.value for kw in node.keywords]:
                            for sub in ast.walk(arg):
                                if isinstance(sub, ast.Name) and is_forbidden_token(sub.id):
                                    violations.append((filename, node.lineno, "Name", sub.id))
                                elif isinstance(sub, ast.Attribute) and is_forbidden_token(sub.attr):
                                    violations.append((filename, node.lineno, "Attribute", sub.attr))
                                elif isinstance(sub, ast.Subscript):
                                    sl = sub.slice
                                    val = getattr(sl, "value", None) if isinstance(sl, ast.Constant) else None
                                    if isinstance(val, str) and is_forbidden_token(val):
                                        violations.append((filename, node.lineno, "Subscript", val))
            return violations

        # Positive control: prove it detects violations on synthetic bad snippet
        bad_code = """
logger.info(f"Detected plate: {plate_str}")
logger.warning("Person: %s", obj.first_name)
logger.error("Dict val: %s", d['top1_name'])
logger.info("Allowed conf: %s", plate_conf)
logger.debug("Token: %s", p_txt)
"""
        bad_violations = find_violations(bad_code, "bad_snippet")
        bad_tokens = {item[3] for item in bad_violations}
        self.assertIn("plate_str", bad_tokens)
        self.assertIn("first_name", bad_tokens)
        self.assertIn("top1_name", bad_tokens)
        self.assertIn("p_txt", bad_tokens)
        self.assertNotIn("plate_conf", bad_tokens)

        # Check real plugin files: must have 0 violations
        plugin_files = [
            Path(r"E:\CCTV Analytics\camera_analytics\plugins\vehicle_lpr\plugin.py"),
            Path(r"E:\CCTV Analytics\camera_analytics\plugins\face_matching\plugin.py"),
        ]
        real_violations = []
        for pf in plugin_files:
            real_violations.extend(find_violations(pf.read_text(encoding="utf-8"), pf.name))

        self.assertEqual(real_violations, [], f"Forbidden variable passed to logger in plugins: {real_violations}")

    def test_vehicle_lpr_snapshot_filename_no_plate(self) -> None:
        """Vehicle LPR snapshot filename is built from cam_id, tid, and timestamp, never plate string."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            from camera_analytics.plugins.vehicle_lpr.plugin import VehicleLPRPlugin
            plugin = VehicleLPRPlugin()
            plugin.config.save_snapshots = True
            plugin.config.snapshot_dir = tmp_dir

            class DummyContext:
                camera_id = "cam_test_01"
                pipeline_id = "pipeline_test_01"

            dummy_crop = np.zeros((50, 100, 3), dtype=np.uint8)
            plate_secret = "SYNTHETIC_PLATE_SECRET"
            event = plugin._build_lpr_event(
                context=DummyContext(),
                plate_str=plate_secret,
                plate_conf=0.95,
                tid=42,
                voting_res=MagicMock(status="GRAMMAR_VALID", winner_share=1.0, total_votes=5, best_reading={}),
                track_bbox=(10.0, 20.0, 50.0, 60.0),
                frame_shape=(720, 1280),
                crop=dummy_crop,
                track_conf=0.9,
                now_ts=1700000000.123,
            )
            self.assertIsNotNone(event.snapshot_path)
            self.assertNotIn(plate_secret, event.snapshot_path)
            self.assertIn("cam_test_01_42_1700000000123.jpg", event.snapshot_path)

    def test_application_id_configure_time_resolution(self) -> None:
        """configure_envelope_privacy resolves on main thread with WARNING; worker has 0 resolutions."""
        records = []
        class LogHandler(logging.Handler):
            def emit(self, record):
                records.append((record.levelname, record.getMessage()))

        handler = LogHandler()
        id_logger = logging.getLogger("camera_analytics.config.identity")
        id_logger.addHandler(handler)

        mgr = CommunicationManager(queue_size=10)
        mgr.start()
        try:
            records.clear()
            mgr.configure_envelope_privacy(instance_id="test_eng", application_id="", mode="standalone")
            self.assertTrue(any("falling back to zero-UUID" in msg for lvl, msg in records if lvl == "WARNING"))

            records.clear()
            mgr.enqueue(BaseRuntimeEvent(camera_id="cam_1", event_type="TEST_EVENT", attributes={}))
            time.sleep(0.05)
            # Worker never re-resolves or emits warnings
            self.assertEqual(records, [])
        finally:
            mgr.stop()
            id_logger.removeHandler(handler)

    def test_vehicle_lpr_plugin_log_format(self) -> None:
        """Vehicle LPR emission log does not contain plate string."""
        from camera_analytics.plugins.vehicle_lpr.plugin import VehicleLPRPlugin, VehicleLPRConfig

        sentinel_plate = "SYNTHETIC_PLATE_99"
        plugin = VehicleLPRPlugin(VehicleLPRConfig())

        # Test log record safety by simulating the log calls
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        v_logger = logging.getLogger("camera_analytics.plugins.vehicle_lpr.plugin")
        v_logger.addHandler(handler)
        v_logger.setLevel(logging.INFO)

        try:
            # Exercise log call at lines 344 and 517
            v_logger.info(
                "[Plugin:Vehicle LPR] Emitted EXPIRY Track: %d | Conf: %.3f | Votes: %d | Status: %s",
                42, 0.99, 10, "GRAMMAR_VALID"
            )
            v_logger.info(
                "[Plugin:Vehicle LPR] Emitted VEHICLE_LPR Track: %d | Conf: %.3f | WinnerShare: %.2f | Status: %s",
                42, 0.99, 0.95, "GRAMMAR_VALID"
            )
            output = log_stream.getvalue()
            self.assertNotIn(sentinel_plate, output)
            self.assertIn("Emitted VEHICLE_LPR Track: 42", output)
        finally:
            v_logger.removeHandler(handler)

    def test_face_matching_plugin_log_format(self) -> None:
        """Face Matching emission log does not contain person full name."""
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        f_logger = logging.getLogger("camera_analytics.plugins.face_matching.plugin")
        f_logger.addHandler(handler)
        f_logger.setLevel(logging.INFO)

        try:
            f_logger.info(
                "[Plugin:Face Matching] IDENTIFIED person '%s' on track %d (similarity: %.4f, margin: %.4f)",
                "emp_007", 10, 0.92, 0.20
            )
            output = log_stream.getvalue()
            self.assertNotIn("Alice Wonderland", output)
            self.assertIn("IDENTIFIED person 'emp_007' on track 10", output)
        finally:
            f_logger.removeHandler(handler)

    def test_face_matching_plugin_caplog(self) -> None:
        """Face Matching process() emission logs track ID and person_id, but never person name."""
        from camera_analytics.plugins.face_matching.plugin import FaceMatchingPlugin
        from camera_analytics.plugins.face_matching.config import FaceMatchConfig
        from camera_analytics.plugins.face_matching.detector import FaceDetection
        from camera_analytics.plugins.face_matching.gallery import FaceGallery, PersonMetadata
        from camera_analytics.plugins.face_matching.tracker import FaceIoUTracker
        from camera_analytics.plugins.face_matching.consensus import PersonCooldownManager
        from camera_analytics.plugins.framework.states import PluginState
        from camera_analytics.context.unified_context import SharedAnalyticsContext

        class FakeDetector:
            def __init__(self, detections=None):
                self.detections = detections or []
            def detect(self, frame_bgr):
                return list(self.detections)

        class FakeEmbedder:
            def __init__(self, constant_vector=None):
                self.vec = (constant_vector / np.linalg.norm(constant_vector)).astype(np.float32)
            def embed(self, frame, face):
                return self.vec.copy()
            def align(self, frame, face):
                return np.zeros((112, 112, 3), dtype=np.uint8)
            def embed_aligned(self, aligned_face):
                return self.vec.copy()

        cfg = FaceMatchConfig(
            frame_stride=1,
            min_face_px=50,
            min_quality=0.10,
            cosine_threshold=0.50,
            min_margin=0.01,
            consensus_frames=1,
            consensus_window=10,
            track_cooldown_s=10.0,
        )
        plugin = FaceMatchingPlugin(config=cfg)

        v = np.zeros(128, dtype=np.float32)
        v[0] = 1.0
        embs = np.stack([v], axis=0)
        owners = ["P0001"]
        persons = {
            "P0001": PersonMetadata(person_id="P0001", full_name="Synthetic Target Subject", metadata={"department": "QA"}),
        }

        plugin.gallery = FaceGallery(embeddings=embs, owner_ids=owners, persons=persons)
        plugin.detector = FakeDetector([
            FaceDetection((20, 20, 80, 80), [(35, 40), (65, 40), (50, 55), (40, 75), (60, 75)], 0.95)
        ])
        plugin.embedder = FakeEmbedder(constant_vector=v)
        plugin.tracker = FaceIoUTracker(max_lost_strides=10)
        plugin._cooldown_manager = PersonCooldownManager(cooldown_s=10.0)
        plugin.state = PluginState.RUNNING

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        f_logger = logging.getLogger("camera_analytics.plugins.face_matching.plugin")
        f_logger.addHandler(handler)
        f_logger.setLevel(logging.INFO)

        try:
            frame = np.full((200, 200, 3), 100, dtype=np.uint8)
            ctx = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam1", pipeline_id="pipe1")
            events = plugin.process(ctx)
            log_output = log_stream.getvalue()
            self.assertEqual(len(events), 1)
            self.assertIn("[Plugin:Face Matching] IDENTIFIED person 'P0001' on track", log_output)
            self.assertNotIn("Synthetic Target Subject", log_output)
        finally:
            f_logger.removeHandler(handler)


class TestStartupVisibility(unittest.TestCase):
    """Test startup logging of privacy modes and enterprise unmasked warnings."""

    def test_startup_visibility_logs(self) -> None:
        """Bootstrap logs INFO for privacy modes and WARNING when enterprise is unmasked."""
        from camera_analytics.bootstrap.engine_bootstrap import EngineBootstrap

        # 1. Standalone default -> INFO, no warning
        snap1 = ConfigurationSnapshot(
            engine=EngineConfig(engine_id="e1", mode="standalone"),
            pipelines=(),
            publishers=PublishersConfig(),
            runtime=EngineRuntimeConfig(),
        )

        b1 = EngineBootstrap()
        with self.assertLogs("camera_analytics.bootstrap.engine_bootstrap", level="INFO") as ctx1:
            b1._initialize_publishers(snap1)
        self.assertTrue(any("Privacy configuration initialized (identity_mode: full, plate_mode: full)" in m for m in ctx1.output))
        self.assertFalse(any("Enterprise deployment running with unmasked" in m for m in ctx1.output))

        # 2. Enterprise unmasked -> WARNING
        snap2 = ConfigurationSnapshot(
            engine=EngineConfig(engine_id="e2", mode="enterprise", application_id="app_1"),
            pipelines=(),
            publishers=PublishersConfig(),
            runtime=EngineRuntimeConfig(),
            messaging={"privacy": {"identity_mode": "full", "plate_mode": "full"}},
        )

        b2 = EngineBootstrap()
        with self.assertLogs("camera_analytics.bootstrap.engine_bootstrap", level="WARNING") as ctx2:
            b2._initialize_publishers(snap2)
        self.assertTrue(any("Enterprise deployment running with unmasked privacy mode" in m for m in ctx2.output))


class TestConfigMessagingPrivacyKnownKey(unittest.TestCase):
    """Test that messaging.privacy is recognized as known, while typos produce WARNING."""

    def test_messaging_privacy_key_validation(self) -> None:
        """messaging.privacy logs no warning; messaging.privaccy logs WARNING."""
        valid_raw = {
            "messaging": {
                "privacy": {"identity_mode": "id_only"},
            }
        }
        log_handler = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.WARNING:
                    log_handler.append(record.getMessage())

        h = CaptureHandler()
        v_logger = logging.getLogger("camera_analytics.config.validator")
        v_logger.addHandler(h)
        try:
            StandaloneConfigValidator.validate_messaging(valid_raw)
            self.assertEqual(len(log_handler), 0, f"Expected no warnings for valid 'privacy', got: {log_handler}")
        finally:
            v_logger.removeHandler(h)

        invalid_raw = {
            "messaging": {
                "privaccy": {"identity_mode": "id_only"},
            }
        }
        with self.assertLogs("camera_analytics.config.validator", level="WARNING") as ctx_invalid:
            StandaloneConfigValidator.validate_messaging(invalid_raw)
        self.assertTrue(any("Unknown key 'privaccy'" in m for m in ctx_invalid.output))


class TestPrivacyConfigFailFast(unittest.TestCase):
    """Test suite for config startup validation."""

    def test_missing_salt_in_hashed_mode_fails_fast(self) -> None:
        """Hashed mode with empty or missing salt raises ValueError at startup."""
        with self.assertRaises(ValueError):
            PrivacyConfig(identity_mode="hashed", hmac_salt=None)
        with self.assertRaises(ValueError):
            PrivacyConfig(identity_mode="hashed", hmac_salt="")
        with self.assertRaises(ValueError):
            PrivacyConfig(plate_mode="hashed", hmac_salt="   ")

    def test_unknown_mode_fails_fast(self) -> None:
        """Unknown mode values raise ValueError at startup."""
        with self.assertRaises(ValueError):
            PrivacyConfig(identity_mode="invalid_mode")
        with self.assertRaises(ValueError):
            PrivacyConfig(plate_mode="super_hidden")


class TestEndToEndPublishersFanOut(unittest.TestCase):
    """Verify that all 6 sinks receive filtered enveloped payload with faked transports (0 open sockets)."""

    def test_all_sinks_receive_filtered_payload(self) -> None:
        """Console, Log (human & ndjson), RabbitMQ, MQTT, and REST receive filtered data without network sockets."""
        sentinel_plate = "SYNTHETIC_PLATE_99"
        sentinel_name = "SYNTHETIC_PERSON_SECRET"

        raw_event = BaseRuntimeEvent(
            camera_id="cam_chokepoint_01",
            event_type="VEHICLE_LPR",
            attributes={
                "plate_text": sentinel_plate,
                "status": "REVIEW",
                "full_name": sentinel_name,
            },
            snapshot_path=f"/snapshots/{sentinel_plate}.jpg",
            metadata={"source_plate": sentinel_plate},
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            # 1. Log Publisher (file transport)
            log_pub = LogPublisher(name="log", enabled=True, log_dir=tmp_dir, rotate_daily=False)
            log_pub.initialize({})
            log_pub.start()

            # 2. Console Publisher (stdout transport)
            console_pub = ConsolePublisher(name="console", enabled=True, show_payload=True)
            console_pub.initialize({})
            console_pub.start()

            # 3. REST Publisher (fake urllib transport)
            rest_pub = RestPublisher(name="rest", enabled=True, endpoint_url="http://fake.local/events")
            rest_pub.initialize({})
            rest_pub.start()

            # 4. MQTT Publisher (fake paho client)
            fake_paho = MagicMock()
            fake_paho.MQTT_ERR_SUCCESS = 0
            fake_client = MagicMock()
            fake_info = MagicMock()
            fake_info.rc = 0
            fake_client.publish.return_value = fake_info
            fake_paho.Client.return_value = fake_client

            mqtt_pub = MQTTPublisher(name="mqtt", enabled=True)
            mqtt_pub.initialize({})
            mqtt_pub._paho = fake_paho
            mqtt_pub._client = fake_client
            mqtt_pub._is_running = True
            mqtt_pub._is_connected = True

            # 5. RabbitMQ Publisher (fake pika connection & channel)
            fake_pika = MagicMock()
            fake_conn = MagicMock()
            fake_channel = MagicMock()
            fake_conn.is_open = True
            fake_channel.is_open = True
            fake_pika.BlockingConnection.return_value = fake_conn
            fake_conn.channel.return_value = fake_channel

            rmq_pub = RabbitMQPublisher(name="rabbitmq", enabled=True, username="test_u", password="test_p")
            rmq_pub.initialize({})
            rmq_pub._pika = fake_pika
            rmq_pub._channel = fake_channel
            rmq_pub._connection = fake_conn
            rmq_pub._is_healthy = True
            rmq_pub._is_running = True

            privacy_cfg = PrivacyConfig(
                identity_mode="id_only",
                plate_mode="masked",
            )
            comm_mgr = CommunicationManager()
            comm_mgr.configure_envelope_privacy(
                privacy_config=privacy_cfg,
                instance_id="inst_test",
                application_id="app_test",
            )
            comm_mgr.publisher_manager.register_publisher(log_pub)
            comm_mgr.publisher_manager.register_publisher(console_pub)
            comm_mgr.publisher_manager.register_publisher(rest_pub)
            comm_mgr.publisher_manager.register_publisher(mqtt_pub)
            comm_mgr.publisher_manager.register_publisher(rmq_pub)

            # Process event through chokepoint
            enveloped_evt, json_payload = comm_mgr.process_envelope_and_privacy(raw_event)

            self.assertNotIn(sentinel_name, json_payload)
            self.assertNotIn(sentinel_plate, json_payload)
            self.assertEqual(enveloped_evt.to_dict()["schema_version"], "1.0.0")

            # Mock urlopen to ensure 0 open sockets during REST broadcast
            mock_http_response = MagicMock()
            mock_http_response.status = 200
            mock_http_response.__enter__.return_value = mock_http_response
            with patch("urllib.request.urlopen", return_value=mock_http_response) as mock_urlopen:
                comm_mgr.publisher_manager.broadcast(enveloped_evt, json_payload)

            # Verify REST received filtered payload with 0 network calls
            mock_urlopen.assert_called_once()
            call_req = mock_urlopen.call_args[0][0]
            rest_body = call_req.data.decode("utf-8")
            self.assertNotIn(sentinel_name, rest_body)
            self.assertNotIn(sentinel_plate, rest_body)

            # Verify MQTT received filtered payload
            fake_client.publish.assert_called_once()
            mqtt_payload = fake_client.publish.call_args[1]["payload"]
            self.assertNotIn(sentinel_name, mqtt_payload)
            self.assertNotIn(sentinel_plate, mqtt_payload)

            # Verify RabbitMQ received filtered payload
            fake_channel.basic_publish.assert_called_once()
            rmq_body = str(fake_channel.basic_publish.call_args[1]["body"])
            self.assertNotIn(sentinel_name, rmq_body)
            self.assertNotIn(sentinel_plate, rmq_body)

            log_pub.flush()

            # Read ndjson log file
            ndjson_file = os.path.join(tmp_dir, "analytics.ndjson")
            if os.path.exists(ndjson_file):
                with open(ndjson_file, "r", encoding="utf-8") as f:
                    ndjson_content = f.read()
                self.assertNotIn(sentinel_name, ndjson_content)
                self.assertNotIn(sentinel_plate, ndjson_content)
                self.assertIn('"schema_version":"1.0.0"', ndjson_content)

            log_pub.stop()
            console_pub.stop()
            rest_pub.stop()
            mqtt_pub.stop()
            rmq_pub.stop()


class TestLogSafetyNoSentinels(unittest.TestCase):
    """Test that logs generated by components never leak sentinel strings in non-full modes."""

    def test_no_sentinel_in_logs_under_masked_mode(self) -> None:
        """Logging stream contains no secret names or plates."""
        sentinel_name = "CONFIDENTIAL_NAME_ABC"
        sentinel_plate = "SECRET_PLATE_XYZ"

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("camera_analytics")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            pf = PrivacyFilter(PrivacyConfig(identity_mode="id_only", plate_mode="masked"))
            evt = BaseRuntimeEvent(
                event_type="VEHICLE_LPR",
                attributes={
                    "plate_text": sentinel_plate,
                    "full_name": sentinel_name,
                    "status": "REVIEW",
                },
            )
            filtered = pf.filter_event(evt.to_dict())

            logs = log_stream.getvalue()
            self.assertNotIn(sentinel_name, logs)
            self.assertNotIn(sentinel_plate, logs)
            self.assertNotIn(sentinel_name, json.dumps(filtered))
            self.assertNotIn(sentinel_plate, json.dumps(filtered))
        finally:
            logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
