# models/face

Weights for the `face_matching` plugin. Both models run on the CPU through
OpenCV (`cv2.FaceDetectorYN` and `cv2.FaceRecognizerSF`).

**The `.onnx` files are not in git.** The repository ignores `*.onnx`, the same
way it ignores `*.pt`. Download them once and place them in this folder.

## Files

| File | Role | Size (bytes) | SHA256 |
| --- | --- | --- | --- |
| `face_detection_yunet_2023mar.onnx` | YuNet face detector (box, 5 landmarks, score) | 232589 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| `face_recognition_sface_2021dec.onnx` | SFace recognizer (128-D embedding) | 38696353 | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

## Where to get them

The OpenCV Zoo repository: <https://github.com/opencv/opencv_zoo>

- `models/face_detection_yunet/` for the YuNet file
- `models/face_recognition_sface/` for the SFace file

The zoo stores the `.onnx` files with Git LFS. Cloning needs `git lfs install`
and `git lfs pull`, or download the file from the repository page.

## Verify after downloading

PowerShell:

```powershell
Get-FileHash .\face_detection_yunet_2023mar.onnx -Algorithm SHA256
Get-FileHash .\face_recognition_sface_2021dec.onnx -Algorithm SHA256
```

The hashes must equal the table above. A different hash means a different
model version: do not use it without re-checking the plugin behavior and
updating this table.

## Licenses

| Model | License file | License |
| --- | --- | --- |
| YuNet | `LICENSE_yunet` | MIT (Copyright (c) 2020 Shiqi Yu) |
| SFace | `LICENSE_sface` | Apache License 2.0 |

The license files are in git and must stay next to the weights. The packaging
script (`--withFR`) copies any `*license*` file from this folder into the
build. Terms of the original training datasets have not been reviewed; get
that checked before distributing the models inside a commercial product.

## Using other locations

The plugin reads `yunet_weights` and `sface_weights` from the `face_matching`
config. Frozen builds default to `<exe dir>/models/face/`. The environment
variables `FACE_DETECTOR_WEIGHTS` and `FACE_RECOGNIZER_WEIGHTS` override the
paths (the generated launcher sets them).

## Not in this folder

Enrollment photos and embeddings are biometric personal data (UU PDP, Law
27/2022). They belong in `data/faces/` and `cache/faces/`, which are ignored by
git and must never be committed.
