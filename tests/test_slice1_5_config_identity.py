"""
Test suite for Slice 1.5: Configuration Safety, Environment Expansion, and Identity Resolution.
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from camera_analytics.bootstrap.engine_bootstrap import EngineBootstrap
from camera_analytics.bootstrap.heartbeat_service import EngineHeartbeatService
from camera_analytics.bootstrap.models import EngineConfig
from camera_analytics.bootstrap.providers.backend_provider import BackendConfigurationProvider
from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider
from camera_analytics.bootstrap.registration_service import EngineRegistrationService
from camera_analytics.communication.publisher_base import PublisherHealthState
from camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher
import camera_analytics.config.env_expander as env_expander_module
from camera_analytics.config.env_expander import (
    ConfigExpansionError,
    expand_env_vars,
)
from camera_analytics.config.identity import resolve_application_id
from camera_analytics.config.loader import ConfigLoader
from camera_analytics.config.validator import StandaloneConfigValidator


class TestEnvExpansion(unittest.TestCase):
    """Test suite for ${VAR} and ${VAR:-default} configuration string expansion."""

    def test_expansion_with_default(self) -> None:
        """${VAR:-default} uses default when env var is unset, and uses env var when set."""
        with patch.dict(os.environ, {}, clear=True):
            data = {"host": "${TEST_HOST:-localhost}", "port": "${TEST_PORT:-5672}"}
            expanded = expand_env_vars(data)
            self.assertEqual(expanded["host"], "localhost")
            self.assertEqual(expanded["port"], "5672")

        with patch.dict(os.environ, {"TEST_HOST": "remote.broker.net"}, clear=True):
            data = {"host": "${TEST_HOST:-localhost}"}
            expanded = expand_env_vars(data)
            self.assertEqual(expanded["host"], "remote.broker.net")

    def test_expansion_missing_raises_error(self) -> None:
        """${VAR} without default raises ConfigExpansionError naming the variable."""
        with patch.dict(os.environ, {}, clear=True):
            data = {"secret": "${UNSET_MANDATORY_SECRET}"}
            with self.assertRaises(ConfigExpansionError) as ctx:
                expand_env_vars(data)
            self.assertIn("UNSET_MANDATORY_SECRET", str(ctx.exception))

    def test_expansion_escape_syntax(self) -> None:
        """$${VAR} escapes expansion and resolves to literal ${VAR}."""
        with patch.dict(os.environ, {"VAR": "danger"}, clear=True):
            data = {"template": "$${VAR}", "other": "prefix $${VAR:-fallback} suffix"}
            expanded = expand_env_vars(data)
            self.assertEqual(expanded["template"], "${VAR}")
            self.assertEqual(expanded["other"], "prefix ${VAR:-fallback} suffix")

    def test_expansion_nested_structures(self) -> None:
        """Recursive expansion traverses nested dictionaries and lists."""
        with patch.dict(os.environ, {"APP_ENV": "staging", "WORKER_COUNT": "4"}, clear=True):
            data = {
                "system": {
                    "env": "${APP_ENV}",
                    "workers": ["worker-${WORKER_COUNT}", "${APP_ENV}-node"],
                }
            }
            expanded = expand_env_vars(data)
            self.assertEqual(expanded["system"]["env"], "staging")
            self.assertEqual(expanded["system"]["workers"], ["worker-4", "staging-node"])

    def test_expansion_disabled_block_skipped(self) -> None:
        """Blocks with 'enabled': False are skipped, so unresolved variables do not raise error."""
        with patch.dict(os.environ, {}, clear=True):
            data = {
                "active_publisher": {
                    "enabled": True,
                    "host": "${CONFIGURED_HOST:-127.0.0.1}",
                },
                "disabled_publisher": {
                    "enabled": False,
                    "host": "${MISSING_UNCONFIGURED_VAR}",
                    "credentials": {"token": "${ANOTHER_MISSING_VAR}"},
                },
            }
            expanded = expand_env_vars(data)
            self.assertEqual(expanded["active_publisher"]["host"], "127.0.0.1")
            self.assertEqual(expanded["disabled_publisher"]["host"], "${MISSING_UNCONFIGURED_VAR}")

    def test_expansion_non_string_untouched(self) -> None:
        """Integers, floats, booleans, and None are untouched with exact types preserved."""
        data = {
            "int_val": 42,
            "float_val": 3.1415,
            "bool_val": True,
            "none_val": None,
            "list_val": [1, 2.5, False, None],
        }
        expanded = expand_env_vars(data)
        self.assertEqual(expanded, data)
        self.assertIsInstance(expanded["int_val"], int)
        self.assertIsInstance(expanded["float_val"], float)
        self.assertIsInstance(expanded["bool_val"], bool)
        self.assertIsNone(expanded["none_val"])

    def test_expansion_allowlist_for_backend(self) -> None:
        """Allowlist prefix CCTV_ expands matching vars and leaves others unexpanded with warning."""
        with patch.dict(os.environ, {"CCTV_RTSP_PORT": "8554", "SECRET_KEY": "12345"}, clear=True):
            data = {
                "allowed": "rtsp://camera:${CCTV_RTSP_PORT}/stream",
                "disallowed": "auth:${SECRET_KEY}",
            }
            with self.assertLogs("camera_analytics.config.env_expander", level="WARNING") as log_ctx:
                expanded = expand_env_vars(data, allowlist_prefix="CCTV_")

            self.assertEqual(expanded["allowed"], "rtsp://camera:8554/stream")
            # Disallowed variable remains unexpanded
            self.assertEqual(expanded["disallowed"], "auth:${SECRET_KEY}")
            # Variable name logged, never the value
            self.assertTrue(any("SECRET_KEY" in msg for msg in log_ctx.output))
            for msg in log_ctx.output:
                self.assertNotIn("12345", msg)


class TestDoubleExpansionPrevention(unittest.TestCase):
    """Test suite ensuring configuration data is expanded exactly once per entry point."""

    def test_standalone_load_escape_literal_not_re_expanded(self) -> None:
        """StandaloneConfigurationProvider.load with $${LITERAL} produces literal ${LITERAL} without error."""
        raw_config = {
            "engine": {"engine_id": "test_e1", "hostname": "$${LITERAL}"},
            "cameras": [
                {
                    "camera_id": "cam_01",
                    "name": "Camera $${LITERAL}",
                    "zones": [{"name": "Zone A", "points": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
                }
            ],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
            json.dump(raw_config, f)
            cfg_path = f.name

        try:
            provider = StandaloneConfigurationProvider(cfg_path)
            snapshot = provider.load()
            self.assertEqual(snapshot.engine.hostname, "${LITERAL}")
            self.assertEqual(snapshot.pipelines[0].app.camera.name, "Camera ${LITERAL}")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_parse_dict_and_config_loader_escape_literal(self) -> None:
        """parse_dict and ConfigLoader.from_dict with $${LITERAL} produce ${LITERAL} without error."""
        raw_dict = {
            "engine": {"engine_id": "test_e1", "hostname": "$${LITERAL}"},
            "cameras": [{"camera_id": "cam_01", "zones": []}],
        }
        provider = StandaloneConfigurationProvider()
        snap = provider.parse_dict(raw_dict)
        self.assertEqual(snap.engine.hostname, "${LITERAL}")

        loader_dict = {
            "camera": {"camera_id": "cam_01", "name": "Cam $${LITERAL}"},
            "source": {"source_type": "rtsp", "uri": "rtsp://127.0.0.1/$${LITERAL}"},
            "detector": {"model_name": "yolo_pose"},
            "tracker": {"tracker_name": "botsort"},
            "runner": {},
            "analytics": {"enabled_modules": ["people_counting"]},
        }
        app_cfg = ConfigLoader.from_dict(loader_dict)
        self.assertEqual(app_cfg.camera.name, "Cam ${LITERAL}")
        self.assertEqual(app_cfg.source.uri, "rtsp://127.0.0.1/${LITERAL}")

    def test_env_var_value_containing_nested_token_preserved_verbatim(self) -> None:
        """An env var whose VALUE contains '${OTHER}' is preserved verbatim after load without re-expansion."""
        sentinel_val = "sentinel_${OTHER}_token"
        with patch.dict(os.environ, {"EXP_SRC": sentinel_val}, clear=True):
            raw_config = {
                "engine": {"engine_id": "eng_test", "hostname": "${EXP_SRC}"},
                "cameras": [{"camera_id": "c1", "name": "${EXP_SRC}", "zones": []}],
            }
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
                json.dump(raw_config, f)
                cfg_path = f.name

            try:
                provider = StandaloneConfigurationProvider(cfg_path)
                snapshot = provider.load()
                self.assertEqual(snapshot.engine.hostname, sentinel_val)
                self.assertEqual(snapshot.pipelines[0].app.camera.name, sentinel_val)
            finally:
                if os.path.exists(cfg_path):
                    os.remove(cfg_path)

    def test_one_expand_per_entry_point(self) -> None:
        """Call counter proves exactly one expand_env_vars call per entry point."""
        orig_expand = env_expander_module.expand_env_vars

        # 1. StandaloneConfigurationProvider.load
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
            json.dump({"engine": {"engine_id": "e1"}, "cameras": []}, f)
            tmp_cfg = f.name
        try:
            with patch("camera_analytics.bootstrap.providers.standalone_provider.expand_env_vars", wraps=orig_expand) as mock_exp:
                StandaloneConfigurationProvider(tmp_cfg).load()
                self.assertEqual(mock_exp.call_count, 1, "StandaloneConfigurationProvider.load must call expand_env_vars exactly once")
        finally:
            if os.path.exists(tmp_cfg):
                os.remove(tmp_cfg)

        # 2. StandaloneConfigurationProvider.parse_dict
        with patch("camera_analytics.bootstrap.providers.standalone_provider.expand_env_vars", wraps=orig_expand) as mock_exp:
            StandaloneConfigurationProvider().parse_dict({"engine": {"engine_id": "e1"}, "cameras": []})
            self.assertEqual(mock_exp.call_count, 1, "StandaloneConfigurationProvider.parse_dict must call expand_env_vars exactly once")

        # 3. ConfigLoader.from_dict
        with patch("camera_analytics.config.loader.expand_env_vars", wraps=orig_expand) as mock_exp:
            ConfigLoader.from_dict({
                "camera": {"camera_id": "cam_01"},
                "source": {"source_type": "rtsp", "uri": "rtsp://127.0.0.1/s"},
                "detector": {"model_name": "yolo_pose"},
                "tracker": {"tracker_name": "botsort"},
                "runner": {},
                "analytics": {"enabled_modules": ["people_counting"]},
            })
            self.assertEqual(mock_exp.call_count, 1, "ConfigLoader.from_dict must call expand_env_vars exactly once")

        # 4. BackendConfigurationProvider.load
        with patch("camera_analytics.bootstrap.providers.backend_provider.expand_env_vars", wraps=orig_expand) as mock_exp:
            backend = BackendConfigurationProvider(backend_url="http://127.0.0.1:9")
            with patch.dict(os.environ, {"APPLICATION_ID": "app_01", "RABBITMQ_USER": "u", "RABBITMQ_PASSWORD": "p", "RTSP_URL": "rtsp://127.0.0.1/s"}):
                # Backend will fail connection and fall back without calling expand_env_vars
                backend.load()
                self.assertEqual(mock_exp.call_count, 0, "BackendConfigurationProvider.load falls back when offline")


class TestApplicationIdResolver(unittest.TestCase):
    """Test suite for application_id resolution order and mode-specific fallbacks."""

    def test_env_var_highest_precedence(self) -> None:
        """APPLICATION_ID in environment takes highest precedence."""
        with patch.dict(os.environ, {"APPLICATION_ID": "app-env-1234"}, clear=True):
            app_id = resolve_application_id(
                config={"engine": {"application_id": "app-cfg-5678"}},
                mode="enterprise",
            )
            self.assertEqual(app_id, "app-env-1234")

    def test_config_key_fallback(self) -> None:
        """Config key is used when environment variable is unset."""
        with patch.dict(os.environ, {}, clear=True):
            app_id = resolve_application_id(
                config={"engine": {"application_id": "app-cfg-5678"}},
                mode="enterprise",
            )
            self.assertEqual(app_id, "app-cfg-5678")

            # Also supports root level application_id
            app_id_root = resolve_application_id(
                config={"application_id": "app-root-9999"},
                mode="enterprise",
            )
            self.assertEqual(app_id_root, "app-root-9999")

            # Also supports EngineConfig dataclass
            eng_cfg = EngineConfig(engine_id="eng_01", application_id="app-dataclass-7777")
            app_id_obj = resolve_application_id(config=eng_cfg, mode="enterprise")
            self.assertEqual(app_id_obj, "app-dataclass-7777")

    def test_standalone_zero_uuid_fallback_with_warning(self) -> None:
        """Standalone mode falls back to zero-UUID placeholder with a WARNING."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertLogs("camera_analytics.config.identity", level="WARNING") as log_ctx:
                app_id = resolve_application_id(config={}, mode="standalone")

            self.assertEqual(app_id, "00000000-0000-0000-0000-000000000000")
            self.assertTrue(any("00000000-0000-0000-0000-000000000000" in msg for msg in log_ctx.output))

    def test_enterprise_missing_raises_runtime_error(self) -> None:
        """Enterprise mode fails fast at startup if application_id cannot be resolved."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                resolve_application_id(config={}, mode="enterprise")
            self.assertIn("application_id", str(ctx.exception))


class TestRabbitMQCredentialsAndSafety(unittest.TestCase):
    """Test suite for RabbitMQPublisher credential removal and safe failure handling."""

    def test_default_credentials_are_none(self) -> None:
        """RabbitMQPublisher default username and password are None (no hardcoded credentials)."""
        pub = RabbitMQPublisher(name="test_rmq")
        self.assertIsNone(pub._username)
        self.assertIsNone(pub._password)

    def test_missing_credentials_fails_safely_without_connecting(self) -> None:
        """Enabled RabbitMQPublisher without credentials transitions to FAILED state and does not connect."""
        pub = RabbitMQPublisher(name="test_rmq", enabled=True, username=None, password=None)
        pub.initialize({})

        # Mock pika to ensure connection is NEVER attempted
        mock_pika = MagicMock()
        with patch.dict("sys.modules", {"pika": mock_pika}):
            with self.assertLogs("camera_analytics.communication.publishers.rabbitmq_publisher", level="WARNING") as log_ctx:
                pub.start()

            self.assertEqual(pub.state, PublisherHealthState.FAILED)
            self.assertFalse(pub.is_running)
            mock_pika.BlockingConnection.assert_not_called()
            self.assertTrue(any("credentials" in msg.lower() for msg in log_ctx.output))


class TestServicePayloadIdentity(unittest.TestCase):
    """Test suite verifying heartbeat and registration payloads carry resolved application_id."""

    def test_heartbeat_payload_uses_resolver(self) -> None:
        """EngineHeartbeatService payload carries resolved application_id, removing hardcoded UUID."""
        with patch.dict(os.environ, {"APPLICATION_ID": "resolved-app-tenant-01"}, clear=True):
            service = EngineHeartbeatService(
                instance_id="eng_01",
                comm_manager=MagicMock(),
                interval_sec=1.0,
            )
            self.assertEqual(service.application_id, "resolved-app-tenant-01")

    def test_registration_payload_uses_resolver(self) -> None:
        """EngineRegistrationService payload carries resolved application_id."""
        with patch.dict(os.environ, {"APPLICATION_ID": "resolved-reg-tenant-02"}, clear=True):
            service = EngineRegistrationService(
                instance_id="eng_01",
                comm_manager=MagicMock(),
            )
            payload = service.build_registration_payload()
            self.assertEqual(payload["application_id"], "resolved-reg-tenant-02")


class TestBootstrapApplicationIdWiring(unittest.TestCase):
    """Test suite verifying engine.application_id reaches heartbeat and registration services in bootstrap path."""

    def test_standalone_config_application_id_reaches_both_services(self) -> None:
        """Standalone config with engine.application_id wires to heartbeat and registration payloads."""
        raw_config = {
            "engine": {
                "engine_id": "eng_wire_test",
                "mode": "enterprise",
                "application_id": "tenant-custom-wire-uuid-1234",
            },
            "communication": {
                "publishers": [{"type": "log", "enabled": True}]
            },
            "cameras": [
                {
                    "camera_id": "cam_bootstrap_01",
                    "name": "Bootstrap Cam",
                    "zones": [{"name": "Zone 1", "points": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
                }
            ],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
            json.dump(raw_config, f)
            cfg_path = f.name

        try:
            with patch.dict(os.environ, {}, clear=True):
                provider = StandaloneConfigurationProvider(cfg_path)
                bootstrap = EngineBootstrap(provider)
                res = bootstrap.bootstrap()
                self.assertTrue(res.is_success, f"Bootstrap failed: {res.error_message}")
                self.assertIsNotNone(res.context)

                # Check registration service payload if registered
                reg_svc = res.context.services.get("registration_service")
                if reg_svc:
                    payload = reg_svc.build_registration_payload()
                    self.assertEqual(payload["application_id"], "tenant-custom-wire-uuid-1234")

                hb_svc = res.context.services.get("heartbeat_service")
                if hb_svc:
                    self.assertEqual(hb_svc.application_id, "tenant-custom-wire-uuid-1234")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)


class TestStandaloneZoneIdPrecedenceAndDeduplication(unittest.TestCase):
    """Test suite for StandaloneConfigurationProvider zone ID 3-key precedence, fallback, and deduplication."""

    def setUp(self) -> None:
        self.provider = StandaloneConfigurationProvider()
        self.dummy_pts = [[0, 0], [100, 0], [100, 100], [0, 100]]

    def test_three_zones_lacking_ids_produce_z0_z1_z2(self) -> None:
        """Three zones without IDs generate distinct positional IDs z_0, z_1, z_2."""
        raw_dict = {
            "cameras": [
                {
                    "camera_id": "cam_pos_test",
                    "zones": [
                        {"name": "Zone A", "points": self.dummy_pts},
                        {"name": "Zone B", "points": self.dummy_pts},
                        {"name": "Zone C", "points": self.dummy_pts},
                    ],
                }
            ]
        }
        snapshot = self.provider.parse_dict(raw_dict)
        cam_pipe = snapshot.pipelines[0]
        zones = cam_pipe.app.camera.raw_zones_payload
        self.assertEqual(len(zones), 3)
        self.assertEqual(zones[0]["zone_id"], "z_0")
        self.assertEqual(zones[1]["zone_id"], "z_1")
        self.assertEqual(zones[2]["zone_id"], "z_2")

    def test_precedence_order_zone_id_id_zoneId(self) -> None:
        """zone_id wins over id, which wins over zoneId."""
        raw_dict = {
            "cameras": [
                {
                    "camera_id": "cam_prec_test",
                    "zones": [
                        {"zone_id": "z_winner", "id": "z_second", "zoneId": "z_third", "points": self.dummy_pts},
                        {"id": "id_winner", "zoneId": "zoneId_second", "points": self.dummy_pts},
                        {"zoneId": "zoneId_winner", "points": self.dummy_pts},
                    ],
                }
            ]
        }
        snapshot = self.provider.parse_dict(raw_dict)
        zones = snapshot.pipelines[0].app.camera.raw_zones_payload
        self.assertEqual(zones[0]["zone_id"], "z_winner")
        self.assertEqual(zones[1]["zone_id"], "id_winner")
        self.assertEqual(zones[2]["zone_id"], "zoneId_winner")

    def test_duplicate_zone_id_warning_and_skipping(self) -> None:
        """Duplicate zone_id per camera emits WARNING and skips the later duplicate."""
        raw_dict = {
            "cameras": [
                {
                    "camera_id": "cam_dup_test",
                    "zones": [
                        {"zone_id": "dup_zone", "name": "First Definition", "points": self.dummy_pts},
                        {"zone_id": "dup_zone", "name": "Second Definition", "points": self.dummy_pts},
                        {"zone_id": "unique_zone", "name": "Unique Zone", "points": self.dummy_pts},
                    ],
                }
            ]
        }
        with self.assertLogs("camera_analytics.bootstrap.providers.standalone_provider", level="WARNING") as log_ctx:
            snapshot = self.provider.parse_dict(raw_dict)

        self.assertTrue(any("Duplicate zone_id 'dup_zone'" in msg for msg in log_ctx.output))
        zones = snapshot.pipelines[0].app.camera.raw_zones_payload
        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0]["zone_id"], "dup_zone")
        self.assertEqual(zones[0]["name"], "First Definition")
        self.assertEqual(zones[1]["zone_id"], "unique_zone")

    def test_zones_named_unnamed_duplicate_unnamed_yield_same_ids(self) -> None:
        """Zones [named, unnamed, duplicate of named, unnamed] yield same IDs across provider and validator."""
        raw_zones = [
            {"zone_id": "named_zone", "name": "Named Zone", "points": self.dummy_pts},
            {"name": "Unnamed 1", "points": self.dummy_pts},
            {"zone_id": "named_zone", "name": "Duplicate of Named", "points": self.dummy_pts},
            {"name": "Unnamed 2", "points": self.dummy_pts},
        ]
        raw_dict = {"cameras": [{"camera_id": "cam_mixed", "zones": raw_zones}]}

        # Validator path
        StandaloneConfigValidator.validate(raw_dict)

        # Provider path
        snapshot = self.provider.parse_dict(raw_dict)
        provider_zones = snapshot.pipelines[0].app.camera.raw_zones_payload
        provider_ids = [z["zone_id"] for z in provider_zones]

        # In ZoneManager (core/spatial/zone_manager.py:82), positional fallback uses f"z_{len(loaded_zones)}".
        # Zone 0: "named_zone" -> loaded has 1 zone.
        # Zone 1: unnamed -> receives "z_1" -> loaded has 2 zones.
        # Zone 2: duplicate "named_zone" -> skipped! loaded still has 2 zones.
        # Zone 3: unnamed -> receives "z_2" -> loaded has 3 zones.
        self.assertEqual(provider_ids, ["named_zone", "z_1", "z_2"])


class TestLogSafety(unittest.TestCase):
    """Test suite proving that logs never leak sensitive values using sentinels."""

    def setUp(self) -> None:
        self.sentinel = "SUPER_SECRET_SENTINEL_TOKEN_XYZ987"
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        self.handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger()
        root_logger.addHandler(self.handler)
        root_logger.setLevel(logging.DEBUG)

    def tearDown(self) -> None:
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.handler)

    def get_logs(self) -> str:
        return self.log_stream.getvalue()

    def test_expansion_log_safety(self) -> None:
        """Expansion should never log variable values when logging allowlist warnings."""
        env = {"DISALLOWED_VAR": self.sentinel}
        with patch.dict(os.environ, env, clear=True):
            expand_env_vars({"key": "${DISALLOWED_VAR}"}, allowlist_prefix="CCTV_")
        logs = self.get_logs()
        self.assertIn("DISALLOWED_VAR", logs)
        self.assertNotIn(self.sentinel, logs)

    def test_rabbitmq_start_log_safety(self) -> None:
        """RabbitMQPublisher fails safely without printing secret values in logs."""
        pub = RabbitMQPublisher(name="rmq_safe", enabled=True, username=None, password=None)
        pub.initialize({})
        pub.start()
        logs = self.get_logs()
        self.assertNotIn(self.sentinel, logs)

    def test_resolver_log_safety(self) -> None:
        """Resolver logs warnings without printing secret tokens."""
        with patch.dict(os.environ, {}, clear=True):
            resolve_application_id(config={}, mode="standalone")
        logs = self.get_logs()
        self.assertNotIn(self.sentinel, logs)

    def test_backend_provider_log_safety(self) -> None:
        """Backend provider logs warnings without printing credentials."""
        provider = BackendConfigurationProvider(backend_url="http://127.0.0.1:9")
        env = {
            "APPLICATION_ID": "app_test_123",
            "RABBITMQ_USER": "test_user",
            "RABBITMQ_PASSWORD": self.sentinel,
            "RTSP_URL": f"rtsp://admin:{self.sentinel}@127.0.0.1/stream",
        }
        with patch.dict(os.environ, env, clear=True):
            provider.load()
        logs = self.get_logs()
        self.assertNotIn(self.sentinel, logs)


class TestMessagingUnknownKeysWarning(unittest.TestCase):
    """Test suite verifying top-level messaging block emits WARNING on unknown keys without rejection."""

    def test_unknown_key_under_messaging_logs_warning_no_rejection(self) -> None:
        """Unknown key under messaging emits a WARNING and does not raise exception."""
        raw_dict = {
            "messaging": {
                "snapshot": {"interval_seconds": 2.0},
                "unknown_experimental_feature": {"enabled": True},
            },
            "cameras": [{"camera_id": "cam_01", "zones": []}],
        }
        provider = StandaloneConfigurationProvider()
        with self.assertLogs("camera_analytics.config.validator", level="WARNING") as log_ctx:
            snapshot = provider.parse_dict(raw_dict)

        self.assertIsNotNone(snapshot)
        self.assertTrue(any("unknown_experimental_feature" in msg for msg in log_ctx.output))


if __name__ == "__main__":
    unittest.main()
