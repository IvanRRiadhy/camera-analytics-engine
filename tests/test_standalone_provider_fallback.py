import logging
import pytest
from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider

def test_standalone_provider_absent_enabled_modules_legacy_fallback(tmp_path):
    # Minimal config without enabled_modules on camera
    cfg_file = tmp_path / "test_cfg.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_legacy",
                "name": "Legacy Camera",
                "source": "0",
                "enabled": true
            }
        ]
    }""", encoding="utf-8")

    provider = StandaloneConfigurationProvider(config_file_path=str(cfg_file))
    snapshot = provider.load()
    assert len(snapshot.pipelines) == 1
    pipe_cfg = snapshot.pipelines[0]
    
    # Assert fallback to the 3-module legacy default
    assert pipe_cfg.app.analytics.enabled_modules == ("people_counting", "queue_detection", "loitering_detection")


def test_standalone_provider_skips_disabled_camera(tmp_path, caplog):
    cfg_file = tmp_path / "test_disabled_cam.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_enabled_01",
                "name": "Enabled Camera",
                "source": "0",
                "enabled": true
            },
            {
                "camera_id": "cam_disabled_02",
                "name": "Disabled Camera",
                "source": "0",
                "enabled": false
            }
        ]
    }""", encoding="utf-8")

    provider = StandaloneConfigurationProvider(config_file_path=str(cfg_file))
    with caplog.at_level(logging.INFO):
        snapshot = provider.load()

    assert len(snapshot.pipelines) == 1
    assert snapshot.pipelines[0].camera_id == "cam_enabled_01"
    assert any(
        r.levelname == "INFO" and "cam_disabled_02" in r.message and "enabled=false" in r.message
        for r in caplog.records
    )


def test_standalone_provider_top_level_modules_and_settings(tmp_path):
    cfg_file = tmp_path / "test_top_level.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "module_settings": {
            "vehicle_lpr": {"frame_stride": 5, "min_sharpness": 12.0}
        },
        "cameras": [
            {
                "camera_id": "cam_top",
                "source": "0",
                "enabled_modules": ["vehicle_lpr"],
                "module_settings": {
                    "vehicle_lpr": {"frame_stride": 2}
                }
            }
        ]
    }""", encoding="utf-8")

    snapshot = StandaloneConfigurationProvider(config_file_path=str(cfg_file)).load()
    analytics = snapshot.pipelines[0].app.analytics
    assert analytics.enabled_modules == ("vehicle_lpr",)
    assert analytics.module_settings["vehicle_lpr"]["frame_stride"] == 2
    assert analytics.module_settings["vehicle_lpr"]["min_sharpness"] == 12.0


def test_standalone_provider_analytics_nested_modules_and_settings(tmp_path):
    cfg_file = tmp_path / "test_analytics_nested.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_nested",
                "source": "0",
                "analytics": {
                    "enabled_modules": ["people_counting", "vehicle_lpr"],
                    "module_settings": {
                        "vehicle_lpr": {"min_plate_width_px": 90.0}
                    }
                }
            }
        ]
    }""", encoding="utf-8")

    snapshot = StandaloneConfigurationProvider(config_file_path=str(cfg_file)).load()
    analytics = snapshot.pipelines[0].app.analytics
    assert analytics.enabled_modules == ("people_counting", "vehicle_lpr")
    assert analytics.module_settings["vehicle_lpr"]["min_plate_width_px"] == 90.0


def test_standalone_provider_warns_on_conflict_and_prefers_camera_top_level(tmp_path, caplog):
    cfg_file = tmp_path / "test_conflict.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_conflict",
                "source": "0",
                "enabled_modules": ["vehicle_lpr"],
                "module_settings": {
                    "vehicle_lpr": {"frame_stride": 2}
                },
                "analytics": {
                    "enabled_modules": ["people_counting"],
                    "module_settings": {
                        "vehicle_lpr": {"frame_stride": 9}
                    }
                }
            }
        ]
    }""", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        snapshot = StandaloneConfigurationProvider(config_file_path=str(cfg_file)).load()

    analytics = snapshot.pipelines[0].app.analytics
    assert analytics.enabled_modules == ("vehicle_lpr",)
    assert analytics.module_settings["vehicle_lpr"]["frame_stride"] == 2
    warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any("conflicting 'enabled_modules'" in m for m in warnings)
    assert any("conflicting 'module_settings'" in m for m in warnings)


def test_standalone_provider_skips_unknown_module_with_warning(tmp_path, caplog):
    cfg_file = tmp_path / "test_partial_unknown.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_partial",
                "source": "0",
                "enabled_modules": ["nonexistent_mod", "nonexistent.parent.mod", "vehicle_lpr"]
            }
        ]
    }""", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        snapshot = StandaloneConfigurationProvider(config_file_path=str(cfg_file)).load()

    analytics = snapshot.pipelines[0].app.analytics
    assert analytics.enabled_modules == ("vehicle_lpr",)
    assert any(
        r.levelname == "WARNING" and "skipping unknown module code 'nonexistent_mod'" in r.message
        for r in caplog.records
    )
    assert any(
        r.levelname == "WARNING" and "skipping unknown module code 'nonexistent.parent.mod'" in r.message
        for r in caplog.records
    )


def test_standalone_provider_skips_camera_when_no_valid_modules_remain(tmp_path, caplog):
    cfg_file = tmp_path / "test_all_invalid.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_invalid",
                "source": "0",
                "analytics": {
                    "enabled_modules": ["people_analytics"]
                }
            },
            {
                "camera_id": "cam_valid",
                "source": "0",
                "analytics": {
                    "enabled_modules": ["vehicle_lpr"]
                }
            }
        ]
    }""", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        snapshot = StandaloneConfigurationProvider(config_file_path=str(cfg_file)).load()

    # cam_invalid skipped, only cam_valid gets a pipeline
    assert len(snapshot.pipelines) == 1
    assert snapshot.pipelines[0].camera_id == "cam_valid"
    assert snapshot.pipelines[0].app.analytics.enabled_modules == ("vehicle_lpr",)
    assert any(
        r.levelname == "ERROR" and "cam_invalid" in r.message and "no valid enabled_modules" in r.message
        for r in caplog.records
    )


def test_main_all_cameras_skipped_exits_nonzero(tmp_path, caplog):
    import sys
    from unittest.mock import patch
    from camera_analytics.main import main

    cfg_file = tmp_path / "test_all_skipped.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_invalid_only",
                "source": "0",
                "enabled_modules": ["unknown_plugin_x"]
            }
        ]
    }""", encoding="utf-8")

    test_args = [
        "camera_analytics.main",
        "--standalone",
        "--config-file",
        str(cfg_file),
        "--headless",
    ]
    with patch.object(sys, "argv", test_args):
        rc = main()

    assert rc != 0


def test_standalone_provider_find_spec_exception_logging(tmp_path, caplog, monkeypatch):
    import importlib.util

    cfg_file = tmp_path / "test_import_err.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_err_01",
                "source": "0",
                "enabled_modules": ["boom_plugin", "vehicle_lpr"]
            }
        ]
    }""", encoding="utf-8")

    real_find_spec = importlib.util.find_spec

    def mock_find_spec(name, package=None):
        if "boom_plugin" in name:
            raise ImportError("boom")
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", mock_find_spec)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        snapshot = StandaloneConfigurationProvider(config_file_path=str(cfg_file)).load()

    assert len(snapshot.pipelines) == 1
    assert snapshot.pipelines[0].app.analytics.enabled_modules == ("vehicle_lpr",)
    assert any(
        r.levelname == "WARNING" and "boom" in r.message and "ImportError" in r.message
        for r in caplog.records
    )


