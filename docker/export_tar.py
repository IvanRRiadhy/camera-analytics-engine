import subprocess
import gzip
import shutil
import sys
from pathlib import Path

target_file = Path(r"e:\CCTV Analytics\dist\docker-windows\AIEngine-Windows-Docker.tar.gz")
print(f"[+] Starting Docker export to: {target_file}")

proc = subprocess.Popen(["docker", "save", "aiengine:2.2.1-windows"], stdout=subprocess.PIPE)
with gzip.open(target_file, "wb", compresslevel=6) as f_out:
    shutil.copyfileobj(proc.stdout, f_out)

proc.wait()
if proc.returncode == 0:
    print(f"[+] Successfully exported and compressed: {target_file.stat().st_size / (1024*1024*1024):.2f} GB")
else:
    print(f"[!] Docker save failed with returncode {proc.returncode}")
    sys.exit(proc.returncode)
