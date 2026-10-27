# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None

project_root = Path(os.getcwd()).resolve()

datas = [
    (str(project_root / 'configs' / 'standalone.json'), 'configs'),
    (str(project_root / 'configs' / 'distribution.manifest.json'), 'configs'),
    (str(project_root / 'camera_analytics' / 'third_party' / 'MiVOLO' / 'mivolo'), 'mivolo'),
]

hiddenimports = [
    'ultralytics',
    'ultralytics.nn.modules',
    'timm',
    'timm.models.volo',
    'timm.models.layers',
    'safetensors',
    'safetensors.torch',
    'camera_analytics.plugins.loitering.plugin',
    'camera_analytics.plugins.people_counter.plugin',
    'camera_analytics.plugins.zone_occupancy.plugin',
    'camera_analytics.plugins.crowd_detection.plugin',
    'camera_analytics.plugins.queue_detection.plugin',
    'camera_analytics.plugins.zone_enter.plugin',
    'camera_analytics.plugins.zone_exit.plugin',
    'camera_analytics.plugins.dwell_time.plugin',
    'camera_analytics.plugins.direction_detection.plugin',
    'camera_analytics.studio.inspectors.runtime_overview_inspector',
    'camera_analytics.studio.inspectors.ai_model_inspector',
    'camera_analytics.studio.inspectors.human_runtime_inspector',
    'camera_analytics.studio.inspectors.camera_inspector',
    'camera_analytics.studio.inspectors.module_inspector',
    'camera_analytics.studio.inspectors.timeline_inspector',
]

a = Analysis(
    [str(project_root / 'camera_analytics' / 'main.py')],
    pathex=[str(project_root), str(project_root / 'camera_analytics' / 'third_party' / 'MiVOLO')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AIEngine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AIEngine',
)
