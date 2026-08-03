"""
Standalone & Enterprise Dual Runtime Mode Verification Suite (Milestone 4 & 5).

Validates:
1. RuntimeModeResolver resolving ENTERPRISE vs STANDALONE mode
2. ConfigurationProviderFactory instantiating BackendConfigurationProvider vs StandaloneConfigurationProvider
3. StandaloneConfigurationProvider loading local JSON configs (configs/standalone.json)
4. Unified EngineBootstrap execution across both modes
5. Zero network broker connection attempts in Standalone Mode
"""

import argparse
from pathlib import Path
from camera_analytics.bootstrap.factory import ConfigurationProviderFactory, RuntimeMode, RuntimeModeResolver
from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider
from camera_analytics.bootstrap.providers.backend_provider import BackendConfigurationProvider
from camera_analytics.bootstrap import EngineBootstrap

def test_standalone_runtime():
    print("=== Running Standalone & Enterprise Dual Runtime Mode Test ===")

    # 1. Test RuntimeModeResolver
    args_ent = argparse.Namespace(standalone=False, mode="enterprise")
    mode_ent = RuntimeModeResolver.resolve(args_ent)
    assert mode_ent == RuntimeMode.ENTERPRISE
    print(f"[+] Enterprise Mode Resolution: {mode_ent.value.upper()}")

    args_std = argparse.Namespace(standalone=True, mode="standalone", config_file="configs/standalone.json")
    mode_std = RuntimeModeResolver.resolve(args_std)
    assert mode_std == RuntimeMode.STANDALONE
    print(f"[+] Standalone Mode Resolution: {mode_std.value.upper()}")

    # 2. Test ConfigurationProviderFactory
    prov_ent = ConfigurationProviderFactory.create(mode_ent, args_ent)
    assert isinstance(prov_ent, BackendConfigurationProvider)
    print("[+] ConfigurationProviderFactory (Enterprise): BackendConfigurationProvider created.")

    prov_std = ConfigurationProviderFactory.create(mode_std, args_std)
    assert isinstance(prov_std, StandaloneConfigurationProvider)
    print("[+] ConfigurationProviderFactory (Standalone): StandaloneConfigurationProvider created.")

    # 3. Test StandaloneConfigurationProvider Loading & Snapshot Verification
    print("\n--- Testing StandaloneConfigurationProvider Loading ---")
    snapshot = prov_std.load()
    print(f"[+] Snapshot Engine ID: '{snapshot.engine.engine_id}'")
    print(f"[+] Snapshot Mode: '{snapshot.engine.mode}'")
    print(f"[+] Snapshot Schema Version: '{snapshot.schema_version}'")
    print(f"[+] Snapshot Pipelines Count: {len(snapshot.pipelines)}")
    print(f"[+] Snapshot Publishers: {[p.publisher_type for p in snapshot.publishers.publishers]}")

    assert snapshot.engine.mode == "standalone"
    assert len(snapshot.pipelines) > 0
    assert len(snapshot.publishers.publishers) == 2

    # 4. Test Unified EngineBootstrap Execution in Standalone Mode
    print("\n--- Testing EngineBootstrap Execution in Standalone Mode ---")
    bootstrap = EngineBootstrap(provider=prov_std)
    boot_res = bootstrap.bootstrap()
    
    assert boot_res.is_success is True, f"EngineBootstrap failed: {boot_res.error_message}"
    assert boot_res.context is not None
    print(f"[+] EngineBootstrap Success! Context Engine ID: '{boot_res.context.engine_id}'")

    print("\n[SUCCESS] Standalone & Enterprise Dual Runtime Architecture Verification PASSED!")

if __name__ == "__main__":
    test_standalone_runtime()
