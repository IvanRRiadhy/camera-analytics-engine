# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import tempfile
from pathlib import Path

block_cipher = None

project_root = Path(os.getcwd()).resolve()

with_lpr = os.environ.get("AIENGINE_WITH_LPR") == "1"
with_fr = os.environ.get("AIENGINE_WITH_FR") == "1"
anpr_root_env = os.environ.get("ANPR_ROOT")

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
    'camera_analytics.plugins.loitering_detection.plugin',
    'camera_analytics.plugins.people_counting.plugin',
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

pathex = [
    str(project_root),
    str(project_root / 'camera_analytics' / 'third_party' / 'MiVOLO'),
]

if with_lpr:
    if not anpr_root_env:
        raise ValueError("AIENGINE_WITH_LPR=1 is set, but ANPR_ROOT environment variable is unset!")
    anpr_root = Path(anpr_root_env).resolve()
    if not anpr_root.is_dir():
        raise FileNotFoundError(f"ANPR_ROOT directory does not exist: {anpr_root}")

    pathex.append(str(anpr_root))
    hiddenimports.extend([
        'camera_analytics.plugins.vehicle_lpr.plugin',
        'anpr.prefix_lexicon',
        'anpr_v2',
        'anpr_v2.reader',
        'anpr_v2.voting',
        'research.step5_04_assembler.assembler',
        'research.step_4_14_validation_engine.tnkb_validator',
        'research.step_4_14_validation_engine.tnkb_parser',
        'research.step_4_14_validation_engine.validation_models',
        'research.step_4_14_validation_engine.rejection_reasons',
        'research.step_4_14_validation_engine.integration_adapter',
    ])

    lpr_datas = []

    # 1. anpr_v2 files (excluding __pycache__ and tests)
    anpr_v2_dir = anpr_root / 'anpr_v2'
    for item in anpr_v2_dir.iterdir():
        if item.is_file() and not item.name.endswith('.pyc') and not item.name.startswith('.'):
            lpr_datas.append((str(item), 'anpr_v2'))

    # 2. research/step5_04_assembler/assembler.py
    asm_dir = anpr_root / 'research' / 'step5_04_assembler'
    asm_file = asm_dir / 'assembler.py'
    if asm_file.is_file():
        lpr_datas.append((str(asm_file), 'research/step5_04_assembler'))

    # 3. research/step_4_14_validation_engine files (excluding __pycache__ and tests)
    val_dir = anpr_root / 'research' / 'step_4_14_validation_engine'
    for item in val_dir.iterdir():
        if item.is_file() and item.suffix == '.py' and not item.name.startswith('test_') and not item.name.endswith('.pyc'):
            lpr_datas.append((str(item), 'research/step_4_14_validation_engine'))

    # 4. __init__.py files needed above them:
    init_src = anpr_root / 'research' / '__init__.py'
    if not init_src.exists():
        empty_init = Path(tempfile.gettempdir()) / '_anpr_empty_init.py'
        empty_init.write_text('', encoding='utf-8')
        init_src = empty_init
    lpr_datas.append((str(init_src), 'research'))

    asm_init_src = asm_dir / '__init__.py'
    if not asm_init_src.exists():
        asm_init_src = init_src
    lpr_datas.append((str(asm_init_src), 'research/step5_04_assembler'))

    datas.extend(lpr_datas)

    total_lpr_bytes = sum(Path(src).stat().st_size for src, _ in lpr_datas)
    print(f"[ai_engine.spec] Total size of bundled LPR datas: {total_lpr_bytes:,} bytes ({total_lpr_bytes / 1024:.1f} KB) across {len(lpr_datas)} files.")

if with_fr:
    hiddenimports.extend([
        'camera_analytics.plugins.face_matching.plugin',
        'camera_analytics.plugins.face_matching.config',
        'camera_analytics.plugins.face_matching.detector',
        'camera_analytics.plugins.face_matching.embedder',
        'camera_analytics.plugins.face_matching.gallery',
        'camera_analytics.plugins.face_matching.tracker',
        'camera_analytics.plugins.face_matching.consensus',
        'camera_analytics.plugins.face_matching.model_cache',
    ])
    print("[ai_engine.spec] Face Recognition plugin hiddenimports enabled.")

a = Analysis(
    [str(project_root / 'camera_analytics' / 'main.py')],
    pathex=pathex,
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
