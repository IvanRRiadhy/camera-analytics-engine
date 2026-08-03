import inspect
import camera_analytics.adapters.bridge.inference_pipeline  # Pre-import to break circular import cycle
import camera_analytics.viewer.builder as b
from camera_analytics.viewer.models import PresentedMetrics

print("1. Loaded builder module file:")
print(b.__file__)

print("\n2. Signature of PresentedMetrics:")
print(inspect.signature(PresentedMetrics))

print("\n3. Lines 150-175 of loaded builder file:")
with open(b.__file__, "r", encoding="utf-8") as f:
    lines = f.readlines()
    for idx, line in enumerate(lines[149:175], start=150):
        print(f"{idx}: {line}", end="")
