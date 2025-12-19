
import os
from huggingface_hub import snapshot_download

model_id = "stabilityai/stable-diffusion-2-1-base"
local_dir = "/workspace/Imagent/pretrained_ckpts/stable-diffusion-2-1-base"

print(f"Downloading {model_id} to {local_dir}...")
try:
    path = snapshot_download(repo_id=model_id, local_dir=local_dir, local_dir_use_symlinks=False)
    print(f"Successfully downloaded to {path}")
except Exception as e:
    print(f"Download failed: {e}")
