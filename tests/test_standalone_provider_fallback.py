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
