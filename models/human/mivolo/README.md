# MiVOLO Model Assets Inventory

## Model Overview
- **Model Name**: MiVOLO v2 (Multi-input Transformer for Age and Gender Estimation)
- **Author**: Maksim Kuprashevich, Irina Tolstykh (arXiv 2307.04616 / 2403.02302)
- **License**: Apache-2.0
- **Repository**: [https://github.com/WildChlamydia/MiVOLO](https://github.com/WildChlamydia/MiVOLO)

## File Inventory & Checksums

| Asset File | Size (MB) | SHA256 Checksum | Source Repository |
| :--- | :---: | :---: | :--- |
| `weights/model.safetensors` | 109.75 MB | `96efb47051c038ebeec74b73b4253c5fd000433e5afcab7deee0bd8f3fa7bf18` | `iitolstykh/mivolo_v2` (HuggingFace) |
| `weights/yolov8x_person_face.pt` | 130.38 MB | `2620f45609a65f909eb876bd7401308b5a8f3843ad5a03cb7416066a3e492989` | `iitolstykh/YOLO-Face-Person-Detector` |

## Deployment Backend Recommendation
- **Recommended Backend**: **PyTorch Eager Mode / TorchScript**
- **ONNX Status**: Unsupported natively due to custom VOLO transformer operators (`ReduceMax`, `col2im` dynamic reshaping).
