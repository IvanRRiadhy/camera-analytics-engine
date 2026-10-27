import sys
from pathlib import Path
import torch

mivolo_path = Path("camera_analytics/third_party/MiVOLO")
if mivolo_path.exists() and str(mivolo_path.resolve()) not in sys.path:
    sys.path.insert(0, str(mivolo_path.resolve()))

from safetensors.torch import load_file
from mivolo.model.create_timm_model import create_model

print("[1/3] Loading safetensors...")
st_weights = load_file("camera_analytics/models/human/mivolo/weights/model.safetensors")
clean_state_dict = {k.replace("mivolo.model.", ""): v for k, v in st_weights.items()}

print("[2/3] Creating mivolo_d1_384 model...")
model = create_model("mivolo_d1_384", pretrained=False, num_classes=3, in_chans=6)
model.load_state_dict(clean_state_dict, strict=False)
model.eval()

print("[3/3] Tracing & Saving 384 TorchScript...")
dummy = torch.randn(1, 6, 384, 384)
traced = torch.jit.trace(model, dummy)
out_file = "camera_analytics/models/human/mivolo/weights/mivolo_v2.torchscript.pt"
traced.save(out_file)

print(f"[SUCCESS] Native 384 TorchScript saved to '{out_file}'. pos_embed shape: {traced.pos_embed.shape}")
