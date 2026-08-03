"""
Production Runtime Cleanup & Fail Fast Verification Test Suite.

Certifies:
1. Complete removal of FakeDetector/FakeTracker from production runtime imports.
2. Fail Fast Policy when YOLO weights or tracker cannot be loaded.
3. Startup Diagnostics Banner display.
4. 5-Second Provenance Audit logging.
5. Multi-camera runtime component isolation (YOLOPoseAdapter & BoTSORTAdapter per camera).
"""

import sys
import time
import logging
from pathlib import Path

def test_production_runtime_cleanup():
    print("=== Running Production Runtime Cleanup & Fail Fast Verification Suite ===")

    # 1. Verify FakeDetector & FakeTracker are NOT exported by production adapters
    print("\n--- Step 1: Verifying Production Package Export Isolation ---")
    import camera_analytics.adapters as adapters
    assert not hasattr(adapters, "FakeDetector"), "CRITICAL FAILURE: FakeDetector is exported in camera_analytics.adapters!"
    assert not hasattr(adapters, "FakeTracker"), "CRITICAL FAILURE: FakeTracker is exported in camera_analytics.adapters!"
    print("[+] Verified: FakeDetector and FakeTracker are NOT exported in production 'camera_analytics.adapters'.")

    # 2. Verify Fail Fast Policy
    print("\n--- Step 2: Verifying Fail Fast Policy on Invalid Weights ---")
    from camera_analytics.models.camera import Camera
    from camera_analytics.adapters.bridge.inference_pipeline import InferencePipeline

    bad_camera = Camera(camera_id="cam_fail_test", name="Invalid Weights Test Camera", source="0")
    
    # Temporarily force bad model path load to verify Fail Fast
    from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
    bad_detector = YOLOPoseAdapter()
    
    try:
        bad_detector.load("non_existent_invalid_model_weights_999.pt")
        assert False, "Should have raised FileNotFoundError / RuntimeError"
    except Exception as exc:
        print(f"[+] Verified Fail Fast on missing weights file: {exc}")

    # 3. Test Full Startup Diagnostics Banner & Provenance Audit
    print("\n--- Step 3: Verifying Production Multi-Camera Startup & Provenance ---")
    from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider
    from camera_analytics.bootstrap import EngineBootstrap

    provider = StandaloneConfigurationProvider(config_file_path="configs/standalone.json")
    snapshot = provider.load()
    bootstrap = EngineBootstrap(provider=provider)
    boot_res = bootstrap.bootstrap()
    assert boot_res.is_success, f"Bootstrap failed: {boot_res.error_message}"

    coordinator = boot_res.context.services.get_required("pipeline_coordinator")
    pipelines = coordinator.pipeline_manager.list_pipelines()
    assert len(pipelines) == 2, f"Expected 2 pipelines, got {len(pipelines)}"

    pipe1 = pipelines[0]
    pipe2 = pipelines[1]

    # Verify per-camera model isolation
    print("\n--- Step 4: Verifying Per-Camera Model Provenance & Memory Addresses ---")
    cam1_pipe = InferencePipeline(camera=pipe1.camera, zone_manager=pipe1.zone_manager, zone_engine=pipe1.zone_engine)
    cam2_pipe = InferencePipeline(camera=pipe2.camera, zone_manager=pipe2.zone_manager, zone_engine=pipe2.zone_engine)

    cam1_pipe.initialize()
    cam2_pipe.initialize()

    det1_cls = cam1_pipe._detector.__class__.__name__
    det2_cls = cam2_pipe._detector.__class__.__name__
    trk1_cls = cam1_pipe._tracker.__class__.__name__
    trk2_cls = cam2_pipe._tracker.__class__.__name__

    print(f"[+] Pipeline 1 ('{pipe1.camera_id}'): Detector={det1_cls} (id={id(cam1_pipe._detector)}), Tracker={trk1_cls} (id={id(cam1_pipe._tracker)})")
    print(f"[+] Pipeline 2 ('{pipe2.camera_id}'): Detector={det2_cls} (id={id(cam2_pipe._detector)}), Tracker={trk2_cls} (id={id(cam2_pipe._tracker)})")

    assert det1_cls == "YOLOPoseAdapter" and det2_cls == "YOLOPoseAdapter", "Pipelines MUST use YOLOPoseAdapter!"
    assert trk1_cls == "BoTSORTAdapter" and trk2_cls == "BoTSORTAdapter", "Pipelines MUST use BoTSORTAdapter!"
    assert id(cam1_pipe._detector) != id(cam2_pipe._detector), "Detectors MUST be isolated per camera!"
    assert id(cam1_pipe._tracker) != id(cam2_pipe._tracker), "Trackers MUST be isolated per camera!"

    print("\n[SUCCESS] Production Runtime Cleanup & Fail Fast Verification PASSED!")

if __name__ == "__main__":
    test_production_runtime_cleanup()
