
import os
import torch
import cv2
from pathlib import Path
from utils.expert_face_score import compute_face_scores
from facexlib.utils.face_restoration_helper import FaceRestoreHelper

def test_face_score():
    print("Testing compute_face_scores...")
    # Create a dummy face image
    img = torch.randn(1, 3, 112, 112) # Dummy tensor, but read expects path
    dummy_path = "dummy_face.png"
    cv2.imwrite(dummy_path, (torch.rand(112, 112, 3).numpy() * 255).astype('uint8'))
    
    try:
        score = compute_face_scores(dummy_path)
        print(f"Success! Score: {score}")
    except Exception as e:
        print(f"Failed! {e}")
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

def test_face_helper():
    print("Testing FaceRestoreHelper initialization...")
    try:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        helper = FaceRestoreHelper(
            1,
            face_size=512,
            crop_ratio=(1, 1),
            det_model="retinaface_resnet50",
            save_ext="png",
            use_parse=True,
            device=device
        )
        print("Success! FaceRestoreHelper initialized.")
    except Exception as e:
        print(f"Failed! {e}")

if __name__ == "__main__":
    test_face_score()
    test_face_helper()
