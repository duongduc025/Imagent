import streamlit as st
import os
import glob
from PIL import Image

st.set_page_config(layout="wide", page_title="Imagent Results")

st.title("Imagent Restoration Result")

# Base paths
output_base = "/workspace/Imagent/outputs/Result_GPT4V/baby"
input_path = "/workspace/Imagent/assets/profile_test_example/classicsr/baby.png"

# Find latest output folder
subdirs = sorted(glob.glob(os.path.join(output_base, "*")), key=os.path.getmtime, reverse=True)

if not subdirs:
    st.error("No output directories found!")
else:
    latest_dir = subdirs[0]
    result_path = os.path.join(latest_dir, "result.png")
    
    st.info(f"Viewing output from: {latest_dir}")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original Input")
        if os.path.exists(input_path):
            st.image(input_path, use_container_width=True)
        else:
            st.warning("Input image not found.")

    with col2:
        st.subheader("Restored Output (4K + Face Restore)")
        if os.path.exists(result_path):
            st.image(result_path, use_container_width=True)
        else:
            st.error(f"Result image not found in {latest_dir}")
