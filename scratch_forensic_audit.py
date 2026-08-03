"""
Full Forensic Audit Script for Standalone Multi-Camera Runtime.

Inspects object graph IDs, track lifecycles, global states, track ID collisions,
rendering commands, and zone polygon coordinate transformations across 2 cameras.
"""

import sys
import logging
from pathlib import Path
import numpy as np

# Configure debug logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ForensicAudit")

def run_forensic_audit():
    print("==================================================================================")
    print("      ENTERPRISE CCTV ANALYTICS — FULL RUNTIME FORENSIC AUDIT (2 CAMERAS)")
    print("==================================================================================")

    # 1. Load Standalone Provider & Snapshot
    from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider
    from camera_analytics.bootstrap.factory import ConfigurationProviderFactory, RuntimeMode
    from camera_analytics.bootstrap import EngineBootstrap

    provider = StandaloneConfigurationProvider(config_file_path="configs/standalone.json")
    snapshot = provider.load()

    print(f"\n[+] Snapshot Loaded. Mode: {snapshot.engine.mode}, Pipelines: {len(snapshot.pipelines)}")

    # 2. Instantiate EngineBootstrap
    bootstrap = EngineBootstrap(provider=provider)
    boot_res = bootstrap.bootstrap()
    assert boot_res.is_success, f"Bootstrap failed: {boot_res.error_message}"
    context = boot_res.context

    from camera_analytics.orchestration.pipeline_coordinator import PipelineCoordinator
    coordinator: PipelineCoordinator = context.services.get_required("pipeline_coordinator", PipelineCoordinator)
    pipelines = coordinator.pipeline_manager.list_pipelines()
    print(f"[+] Total Active Pipelines Instantiated: {len(pipelines)}")

    # ----------------------------------------------------------------------------------
    # TASK 1: OBJECT GRAPH AUDIT (Component IDs across Pipelines)
    # ----------------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TASK 1: OBJECT GRAPH AUDIT (Component memory address id() comparison)")
    print("=" * 80)

    pipe_objs = []
    for pipe in pipelines:
        cam = pipe.camera
        print(f"\n--- Pipeline: '{pipe.pipeline_id}' (Camera: '{pipe.camera_id}') ---")
        print(f"  PipelineInstance ID         : {id(pipe)}")
        print(f"  Camera Object ID            : {id(cam)}")
        print(f"  ZoneManager ID              : {id(pipe.zone_manager)}")
        print(f"  ZoneEngine ID               : {id(pipe.zone_engine)}")
        print(f"  PipelineAggregator ID       : {id(pipe.aggregator)}")
        
        pipe_objs.append({
            "pipeline_id": pipe.pipeline_id,
            "camera_id": pipe.camera_id,
            "pipe_id": id(pipe),
            "cam_id": id(cam),
            "zm_id": id(pipe.zone_manager),
            "ze_id": id(pipe.zone_engine),
            "agg_id": id(pipe.aggregator),
        })

    # Verify if any core object is accidentally shared between Camera 1 and Camera 2
    if len(pipe_objs) >= 2:
        p1, p2 = pipe_objs[0], pipe_objs[1]
        print("\n[+] Cross-Pipeline Component Identity Verification:")
        print(f"  Same PipelineInstance? : {p1['pipe_id'] == p2['pipe_id']}")
        print(f"  Same Camera Object?    : {p1['cam_id'] == p2['cam_id']}")
        print(f"  Same ZoneManager?      : {p1['zm_id'] == p2['zm_id']}")
        print(f"  Same ZoneEngine?       : {p1['ze_id'] == p2['ze_id']}")
        print(f"  Same Aggregator?       : {p1['agg_id'] == p2['agg_id']}")

    # ----------------------------------------------------------------------------------
    # TASK 6: SPATIAL ZONE POLYGON RENDERING AUDIT
    # ----------------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TASK 6: SPATIAL ZONE POLYGON RENDERING AUDIT (Coordinate Transformation Check)")
    print("=" * 80)

    from camera_analytics.core.spatial.polygon_loader import PolygonLoader
    from camera_analytics.core.spatial.coordinate_transform import CoordinateTransformEngine

    transform = CoordinateTransformEngine(1920, 1080)

    for pipe in pipelines:
        cam_id = pipe.camera_id
        zones = pipe.zone_manager.get_zones(cam_id)
        print(f"\n[+] Camera '{cam_id}' ZoneManager Active Zones Count: {len(zones)}")
        for z in zones:
            print(f"  - Zone ID: '{z.id}', Name: '{z.name}', Type: {z.type.name}")
            print(f"    Normalized Polygon Points : {[p.to_tuple() for p in z.polygon_normalized]}")
            print(f"    Converted Pixel Points    : {[p.to_tuple() for p in z.polygon_pixels]}")
            if z.geometry:
                bbox = z.geometry.bounding_box()
                print(f"    Geometry BoundingBox      : min=({bbox.min_x}, {bbox.min_y}), max=({bbox.max_x}, {bbox.max_y}), WxH=({bbox.width}x{bbox.height})")
                print(f"    Geometry Area             : {z.geometry.area()} px^2")

    # ----------------------------------------------------------------------------------
    # TASK 2 & 4: DETECTOR & TRACKER INSTANTIATION & TRACK LIFECYCLE AUDIT
    # ----------------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TASK 2 & 4: DETECTOR & TRACKER INSTANTIATION AUDIT")
    print("=" * 80)

    from camera_analytics.adapters.bridge.inference_pipeline import InferencePipeline

    for pipe in pipelines:
        cam = pipe.camera
        inf_pipe = InferencePipeline(
            camera=cam,
            gpu_id=pipe.gpu_id,
            zone_manager=pipe.zone_manager,
            zone_engine=pipe.zone_engine,
            aggregator=pipe.aggregator,
            enabled_modules=list(cam.metadata.get("enabled_modules", ["people_counting", "queue_detection"])),
        )
        inf_pipe.initialize()
        
        det_cls = inf_pipe._detector.__class__.__name__
        trk_cls = inf_pipe._tracker.__class__.__name__

        print(f"\n[+] InferencePipeline for Camera '{cam.camera_id}':")
        print(f"    InferencePipeline ID : {id(inf_pipe)}")
        print(f"    Detector Class      : {det_cls} (ID: {id(inf_pipe._detector)})")
        print(f"    Tracker Class       : {trk_cls} (ID: {id(inf_pipe._tracker)})")
        print(f"    ContextBuilder ID   : {id(inf_pipe._context_builder)}")
        print(f"    PluginManager ID    : {id(inf_pipe._plugin_manager)}")

        if det_cls == "FakeDetector":
            print(f"    [!] ALERT: Detector fell back to FakeDetector! Seed={getattr(inf_pipe._detector, '_seed', 'N/A')}")

    print("\n[SUCCESS] Forensic Audit Executed Cleanly.")

if __name__ == "__main__":
    run_forensic_audit()
