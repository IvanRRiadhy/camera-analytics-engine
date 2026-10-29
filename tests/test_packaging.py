"""
Packaging Regression Test Suite for CCTV Analytics AI Engine.

Verifies:
1. RuntimeResourceManager path resolution logic across environments.
2. DistributionValidator & RuntimeEnvironmentAudit logic.
3. Pre-flight verification and distribution.manifest.json integrity.
4. Official `--verify` CLI contract functionality.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from camera_analytics.bootstrap.distribution_validator import (
    DistributionValidator,
    RuntimeEnvironmentAudit,
)
from camera_analytics.bootstrap.first_run import FirstRunBootstrap
from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager


class TestPackagingAndDistribution(unittest.TestCase):
    """Test suite for packaging compatibility and distribution verification."""

    def test_resource_manager_resolution(self) -> None:
        """Test RuntimeResourceManager resolves core files cleanly."""
        rm = RuntimeResourceManager.get_instance()
        self.assertIsNotNone(rm.executable_dir)

        # Test config resolution
        config_path = rm.resolve_config_path()
        self.assertTrue(config_path.exists(), f"Config file should exist: {config_path}")

        # Test model resolution
        model_path = rm.resolve_model_path("yolo26m-pose.pt")
        self.assertTrue(model_path.exists(), f"Model file should exist: {model_path}")

        # Test writable directory creation
        log_dir = rm.resolve_writable_dir("logs")
        self.assertTrue(log_dir.exists(), f"Log dir should exist: {log_dir}")

    def test_distribution_manifest_and_validator(self) -> None:
        """Test DistributionValidator checks distribution.manifest.json."""
        validator = DistributionValidator()
        passed, messages = validator.validate_distribution()

        self.assertTrue(passed, f"Distribution validation should pass: {messages}")
        self.assertTrue(any("[OK] Config" in m for m in messages))
        self.assertTrue(any("[OK] Model Asset" in m for m in messages))

    def test_environment_audit_collection(self) -> None:
        """Test RuntimeEnvironmentAudit collects system metadata."""
        env_data = RuntimeEnvironmentAudit.collect()
        self.assertIn("python_version", env_data)
        self.assertIn("torch_version", env_data)
        self.assertIn("cuda_available", env_data)

    def test_first_run_bootstrap_execution(self) -> None:
        """Test FirstRunBootstrap pre-flight verification."""
        bootstrap = FirstRunBootstrap()
        res = bootstrap.execute(verify_only=False)
        self.assertTrue(res, "FirstRunBootstrap should pass pre-flight checks")

    def test_sanitize_lpr_weight_paths(self) -> None:
        """Test sanitize_lpr_weight_paths cleans weight keys across all block forms."""
        import hashlib
        import tempfile
        from camera_analytics.packaging.build_executable import (
            project_root,
            sanitize_lpr_weight_paths,
        )

        test_config = {
            "module_settings": {
                "vehicle_lpr": {
                    "detector_weights": "E:/ANPR/runs/detect/indonesian_plate_yolo26_v1/weights/best.pt",
                    "reader_weights": "E:/ANPR/runs/detect/lprd_yolo26n_320/weights/last.pt",
                    "frame_stride": 3,
                    "mode": "detector",
                }
            },
            "analytics": {
                "module_settings": {
                    "vehicle_lpr": {
                        "detector_weights": "E:/ANPR/runs/detect/indonesian_plate_yolo26_v1/weights/best.pt",
                        "reader_weights": "E:/ANPR/runs/detect/lprd_yolo26n_320/weights/last.pt",
                        "min_observations": 3,
                    }
                }
            },
            "cameras": [
                {
                    "camera_id": "cam_01",
                    "module_settings": {
                        "vehicle_lpr": {
                            "detector_weights": "E:/ANPR/runs/detect/indonesian_plate_yolo26_v1/weights/best.pt",
                            "reader_weights": "E:/ANPR/runs/detect/lprd_yolo26n_320/weights/last.pt",
                            "detector_conf": 0.25,
                        }
                    },
                    "analytics": {
                        "module_settings": {
                            "vehicle_lpr": {
                                "detector_weights": "E:/ANPR/runs/detect/indonesian_plate_yolo26_v1/weights/best.pt",
                                "reader_weights": "E:/ANPR/runs/detect/lprd_yolo26n_320/weights/last.pt",
                                "reader_conf": 0.02,
                            }
                        }
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "test_standalone.json"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(test_config, f, indent=2)

            # Record source standalone.json sha256 to ensure untouched
            src_standalone = project_root / "configs" / "standalone.json"
            src_sha_before = (
                hashlib.sha256(src_standalone.read_bytes()).hexdigest()
                if src_standalone.is_file()
                else None
            )

            # Execute sanitization
            removed = sanitize_lpr_weight_paths(tmp_path)

            # Verify return structure: list of removed keys with their old values
            self.assertIsInstance(removed, list)
            self.assertGreater(len(removed), 0)
            removed_keys = [k for k, _ in removed]
            self.assertIn("detector_weights", removed_keys)
            self.assertIn("reader_weights", removed_keys)

            # Reload sanitized file and verify keys removed from all forms
            with open(tmp_path, "r", encoding="utf-8") as f:
                sanitized_data = json.load(f)

            self.assertNotIn("detector_weights", sanitized_data["module_settings"]["vehicle_lpr"])
            self.assertNotIn("reader_weights", sanitized_data["module_settings"]["vehicle_lpr"])
            self.assertNotIn("detector_weights", sanitized_data["analytics"]["module_settings"]["vehicle_lpr"])
            self.assertNotIn("reader_weights", sanitized_data["analytics"]["module_settings"]["vehicle_lpr"])
            self.assertNotIn("detector_weights", sanitized_data["cameras"][0]["module_settings"]["vehicle_lpr"])
            self.assertNotIn("reader_weights", sanitized_data["cameras"][0]["module_settings"]["vehicle_lpr"])
            self.assertNotIn("detector_weights", sanitized_data["cameras"][0]["analytics"]["module_settings"]["vehicle_lpr"])
            self.assertNotIn("reader_weights", sanitized_data["cameras"][0]["analytics"]["module_settings"]["vehicle_lpr"])

            # Verify other keys are kept
            self.assertEqual(sanitized_data["module_settings"]["vehicle_lpr"]["frame_stride"], 3)
            self.assertEqual(sanitized_data["module_settings"]["vehicle_lpr"]["mode"], "detector")
            self.assertEqual(sanitized_data["analytics"]["module_settings"]["vehicle_lpr"]["min_observations"], 3)
            self.assertEqual(sanitized_data["cameras"][0]["module_settings"]["vehicle_lpr"]["detector_conf"], 0.25)
            self.assertEqual(sanitized_data["cameras"][0]["analytics"]["module_settings"]["vehicle_lpr"]["reader_conf"], 0.02)

            # Source file untouched
            if src_standalone.is_file() and src_sha_before:
                src_sha_after = hashlib.sha256(src_standalone.read_bytes()).hexdigest()
                self.assertEqual(src_sha_before, src_sha_after, "Source configs/standalone.json was modified!")

            # No-op on a config without vehicle_lpr
            no_lpr_config = {
                "cameras": [
                    {
                        "camera_id": "cam_02",
                        "enabled_modules": ["people_counting"],
                        "module_settings": {
                            "people_counting": {"line_position": 0.5}
                        },
                    }
                ]
            }
            no_lpr_path = Path(tmp_dir) / "no_lpr.json"
            with open(no_lpr_path, "w", encoding="utf-8") as f:
                json.dump(no_lpr_config, f, indent=2)
            no_lpr_bytes_before = no_lpr_path.read_bytes()

            removed_no_lpr = sanitize_lpr_weight_paths(no_lpr_path)
            self.assertEqual(removed_no_lpr, [])
            self.assertEqual(no_lpr_path.read_bytes(), no_lpr_bytes_before, "No-op config file was modified!")

    def test_sanitize_fr_weight_paths(self) -> None:
        """Test sanitize_lpr_weight_paths cleans face_matching weight keys across all block forms."""
        import hashlib
        import tempfile
        from camera_analytics.packaging.build_executable import sanitize_lpr_weight_paths

        project_root = Path(__file__).resolve().parent.parent.parent

        test_config = {
            "module_settings": {
                "face_matching": {
                    "yunet_weights": "camera_analytics/models/face/face_detection_yunet_2023mar.onnx",
                    "sface_weights": "camera_analytics/models/face/face_recognition_sface_2021dec.onnx",
                    "gallery_path": "data/faces",
                    "min_face_px": 64,
                }
            },
            "analytics": {
                "module_settings": {
                    "face_matching": {
                        "yunet_weights": "E:/custom/yunet.onnx",
                        "sface_weights": "E:/custom/sface.onnx",
                        "cosine_threshold": 0.40,
                    }
                }
            },
            "cameras": [
                {
                    "camera_id": "cam_01",
                    "enabled_modules": ["face_matching"],
                    "module_settings": {
                        "face_matching": {
                            "yunet_weights": "models/face/face_detection_yunet_2023mar.onnx",
                            "sface_weights": "models/face/face_recognition_sface_2021dec.onnx",
                            "min_quality": 0.30,
                        }
                    },
                    "analytics": {
                        "module_settings": {
                            "face_matching": {
                                "yunet_weights": "nested/weights/yunet.onnx",
                                "sface_weights": "nested/weights/sface.onnx",
                                "score_threshold": 0.60,
                            }
                        }
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "test_fr_config.json"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(test_config, f, indent=2)

            src_standalone = project_root / "configs" / "standalone.json"
            src_sha_before = (
                hashlib.sha256(src_standalone.read_bytes()).hexdigest()
                if src_standalone.is_file()
                else None
            )

            removed = sanitize_lpr_weight_paths(tmp_path, verbose=False)

            self.assertIsInstance(removed, list)
            self.assertGreater(len(removed), 0)
            removed_keys = [k for k, _ in removed]
            self.assertIn("yunet_weights", removed_keys)
            self.assertIn("sface_weights", removed_keys)

            with open(tmp_path, "r", encoding="utf-8") as f:
                sanitized_data = json.load(f)

            # Weight keys removed
            self.assertNotIn("yunet_weights", sanitized_data["module_settings"]["face_matching"])
            self.assertNotIn("sface_weights", sanitized_data["module_settings"]["face_matching"])
            self.assertNotIn("yunet_weights", sanitized_data["analytics"]["module_settings"]["face_matching"])
            self.assertNotIn("sface_weights", sanitized_data["analytics"]["module_settings"]["face_matching"])
            self.assertNotIn("yunet_weights", sanitized_data["cameras"][0]["module_settings"]["face_matching"])
            self.assertNotIn("sface_weights", sanitized_data["cameras"][0]["module_settings"]["face_matching"])
            self.assertNotIn("yunet_weights", sanitized_data["cameras"][0]["analytics"]["module_settings"]["face_matching"])
            self.assertNotIn("sface_weights", sanitized_data["cameras"][0]["analytics"]["module_settings"]["face_matching"])

            # Other keys preserved
            self.assertEqual(sanitized_data["module_settings"]["face_matching"]["gallery_path"], "data/faces")
            self.assertEqual(sanitized_data["module_settings"]["face_matching"]["min_face_px"], 64)
            self.assertEqual(sanitized_data["analytics"]["module_settings"]["face_matching"]["cosine_threshold"], 0.40)
            self.assertEqual(sanitized_data["cameras"][0]["module_settings"]["face_matching"]["min_quality"], 0.30)
            self.assertEqual(sanitized_data["cameras"][0]["analytics"]["module_settings"]["face_matching"]["score_threshold"], 0.60)

            # Source standalone.json untouched
            if src_standalone.is_file() and src_sha_before:
                src_sha_after = hashlib.sha256(src_standalone.read_bytes()).hexdigest()
                self.assertEqual(src_sha_before, src_sha_after, "Source configs/standalone.json was modified!")

            # No-op test
            no_fr_config = {"cameras": [{"camera_id": "cam_02", "enabled_modules": ["people_counting"]}]}
            no_fr_path = Path(tmp_dir) / "no_fr.json"
            with open(no_fr_path, "w", encoding="utf-8") as f:
                json.dump(no_fr_config, f, indent=2)
            no_fr_bytes_before = no_fr_path.read_bytes()

            removed_no_fr = sanitize_lpr_weight_paths(no_fr_path, verbose=False)
            self.assertEqual(removed_no_fr, [])
            self.assertEqual(no_fr_path.read_bytes(), no_fr_bytes_before)

    def test_plugin_ignore_patterns_combinations(self) -> None:
        """Test get_plugin_ignore_patterns across all 4 combinations of with_lpr and with_fr."""
        from camera_analytics.packaging.build_executable import get_plugin_ignore_patterns

        # Case 1: Both disabled -> ignore both
        p1 = get_plugin_ignore_patterns(with_lpr=False, with_fr=False)
        self.assertEqual(set(p1), {"vehicle_lpr", "face_matching"})

        # Case 2: Only LPR enabled -> ignore face_matching
        p2 = get_plugin_ignore_patterns(with_lpr=True, with_fr=False)
        self.assertEqual(p2, ["face_matching"])

        # Case 3: Only FR enabled -> ignore vehicle_lpr
        p3 = get_plugin_ignore_patterns(with_lpr=False, with_fr=True)
        self.assertEqual(p3, ["vehicle_lpr"])

        # Case 4: Both enabled -> ignore neither (empty list)
        p4 = get_plugin_ignore_patterns(with_lpr=True, with_fr=True)
        self.assertEqual(p4, [])

    def test_create_faces_readme(self) -> None:
        """Test create_faces_readme produces valid instructions, UU PDP citation, and operator responsibility notice."""
        import tempfile
        from camera_analytics.packaging.build_executable import create_faces_readme

        with tempfile.TemporaryDirectory() as tmp_dir:
            readme_path = Path(tmp_dir) / "README.txt"
            create_faces_readme(readme_path)

            self.assertTrue(readme_path.is_file())
            content = readme_path.read_text(encoding="utf-8")
            self.assertIn("Face Gallery Directory", content)
            self.assertIn("<person_id>.jpg", content)
            self.assertIn("<person_id>_meta.json", content)
            self.assertIn("UU PDP", content)
            self.assertIn("Undang-Undang No. 27 Tahun 2022", content)
            self.assertIn("consent", content.lower())
            self.assertIn("retention", content.lower())
            self.assertIn("operator", content.lower())

    def test_sanitize_weight_paths_name_and_alias(self) -> None:
        """Test sanitize_weight_paths primary function and sanitize_lpr_weight_paths alias."""
        from camera_analytics.packaging.build_executable import (
            sanitize_weight_paths,
            sanitize_lpr_weight_paths,
        )
        self.assertIs(sanitize_lpr_weight_paths, sanitize_weight_paths)

    def test_should_sanitize_weights_combinations(self) -> None:
        """Verify should_sanitize_weights helper across all 4 flag combinations."""
        from camera_analytics.packaging.build_executable import should_sanitize_weights

        self.assertFalse(should_sanitize_weights(with_lpr=False, with_fr=False))
        self.assertTrue(should_sanitize_weights(with_lpr=True, with_fr=False))
        self.assertTrue(should_sanitize_weights(with_lpr=False, with_fr=True))
        self.assertTrue(should_sanitize_weights(with_lpr=True, with_fr=True))

    def test_generate_launcher_content_combinations(self) -> None:
        """Verify generate_launcher_content across all 4 combinations."""
        from camera_analytics.packaging.build_executable import generate_launcher_content

        for with_lpr in (False, True):
            for with_fr in (False, True):
                content = generate_launcher_content(with_lpr=with_lpr, with_fr=with_fr)

                # Standalone flag present, --mode absent
                self.assertIn("--standalone", content)
                self.assertNotIn("--mode", content)

                # _internal sync block present
                self.assertIn('if exist "_internal\\configs\\"', content)
                self.assertIn('copy /Y "configs\\standalone.json" "_internal\\configs\\standalone.json" >nul', content)

                # Standalone config path
                self.assertIn('"%~dp0configs\\standalone.json"', content)

                # Tip present
                self.assertIn("[TIP] Press 'q' or 'ESC' on any camera window to close the viewer.", content)

                # LPR env lines condition
                if with_lpr:
                    self.assertIn(":: ANPR Model Environment Variables", content)
                    self.assertIn('set "ANPR_DETECTOR_WEIGHTS=%~dp0models\\lpr\\best.pt"', content)
                    self.assertIn('set "ANPR_READER_WEIGHTS=%~dp0models\\lpr\\last.pt"', content)
                else:
                    self.assertNotIn("ANPR_DETECTOR_WEIGHTS", content)
                    self.assertNotIn("ANPR_READER_WEIGHTS", content)

                # FR env lines condition
                if with_fr:
                    self.assertIn(":: Face Recognition Model Environment Variables", content)
                    self.assertIn('set "FACE_DETECTOR_WEIGHTS=%~dp0models\\face\\face_detection_yunet_2023mar.onnx"', content)
                    self.assertIn('set "FACE_RECOGNIZER_WEIGHTS=%~dp0models\\face\\face_recognition_sface_2021dec.onnx"', content)
                    self.assertIn('set "FACE_MATCH_GALLERY=%~dp0data\\faces"', content)
                else:
                    self.assertNotIn("FACE_DETECTOR_WEIGHTS", content)
                    self.assertNotIn("FACE_RECOGNIZER_WEIGHTS", content)
                    self.assertNotIn("FACE_MATCH_GALLERY", content)



if __name__ == "__main__":
    unittest.main()
