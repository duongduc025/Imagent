import streamlit as st
import subprocess
import os
import shutil
import time
from pathlib import Path
import glob
import shlex
from PIL import Image

# Try to import streamlit-image-comparison
try:
    from streamlit_image_comparison import image_comparison
    HAS_IMAGE_COMPARISON = True
except ImportError:
    HAS_IMAGE_COMPARISON = False

# Config
INPUT_DIR = Path("assets/streamlit_input")
OUTPUT_DIR = Path("outputs/streamlit_result")

st.set_page_config(page_title="Imagent Control Panel", layout="wide")

st.title("Phục hồi ảnh cùng Imagent")
st.markdown("---")

# Sidebar
st.sidebar.header("Cấu hình")
gpu_id = st.sidebar.text_input("GPU ID", "0")
profile_name = "GPT4V_Profile"

if not HAS_IMAGE_COMPARISON:
    st.sidebar.warning("📦 Cài đặt streamlit-image-comparison để xem Before/After slider")
    st.sidebar.code("pip install streamlit-image-comparison", language="bash")

# Main Area
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Chọn ảnh")
    uploaded_file = st.file_uploader("Tải ảnh lên (PNG, JPG)", type=['png', 'jpg', 'jpeg'])

    if uploaded_file:
        # Save file to input dir
        if INPUT_DIR.exists():
            shutil.rmtree(INPUT_DIR)
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        file_path = INPUT_DIR / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.image(str(file_path), caption="Ảnh gốc", width='stretch')
        
        start_btn = st.button("🚀 Bắt đầu phục hồi", type="primary")

with col2:
    st.subheader("2. Kết quả")
    result_placeholder = st.empty()
    log_area = st.empty()

if uploaded_file and start_btn:
    # Prepare Output Dir
    # We don't delete OUTPUT_DIR here because Imagent creates timestamped subfolders inside it.
    # We will track the latest folder created.
    
    cmd_list = [
        "/venv/4kagent/bin/python", "infer_imagent.py",
        "--input_dir", str(INPUT_DIR),
        "--output_dir", str(OUTPUT_DIR),
        "--profile_name", profile_name,
        "--tool_run_gpu_id", str(gpu_id)
    ]
    
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    
    st.toast("Đang khởi chạy Imagent...")
    
    # Run Process
    process = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,            # Line buffered
        universal_newlines=True
    )
    
    logs = []
    log_area_container = st.container()
    
    # Status Container
    with st.status("Đang xử lý...", expanded=True) as status:
        st_step_init = status.write("Khởi động Imagent...")
        st_step_percept = None
        st_step_plan = None
        st_step_exec = None
        st_step_face = None
    
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            clean_line = line.strip()
            logs.append(clean_line)
            
            # Real-time Status Parsing
            if "Nhận định của AI:" in clean_line:
                if st_step_init: st_step_init = None # Clear init
                if not st_step_percept: st_step_percept = status.write("Đang phân tích ảnh con người (Perception)...")
                st.write(f"&nbsp;&nbsp;&nbsp;&nbsp; {clean_line.split(':', 1)[1].strip()}")
                
            if "Kế hoạch:" in clean_line:
                if not st_step_plan: st_step_plan = status.write("Đang lập kế hoạch (Planning)...")
                st.info(f"Kế hoạch: {clean_line.split(':', 1)[1].strip()}")
                
            if "được dùng để xử lý" in clean_line:
                parts = clean_line.split("(", 1)
                tool_name = parts[0].strip()
                # subtask = clean_line.split("thực hiện", 1)[1].strip().replace("...", "")
                if not st_step_exec: st_step_exec = status.write(f"Đang thực thi các công cụ...")
                st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;Chạy thử: **{tool_name}**")
                
            if "Tool tốt nhất:" in clean_line:
                tool = clean_line.split(':', 1)[1].strip()
                st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;**CHỐT**: {tool}")
                
            if "Khuôn mặt" in clean_line and "Kết quả phục hồi" in clean_line:
                 if not st_step_face: st_step_face = status.write("Đang phục hồi khuôn mặt...")
                 
            # Show last 30 lines to avoid UI lag
            log_text = "\n".join(logs[-30:])
            log_area.code(log_text, language='bash')
            
    status.update(label="Hoàn thành!", state="complete", expanded=False)
            
    # Show full log in expander when finished
    with st.expander("Xem toàn bộ Log"):
        st.code("\n".join(logs), language='bash')
            
    if process.returncode == 0:
        st.success("✅ Xử lý hoàn tất!")
        
        # Find the latest result folder
        # Result structure: outputs/streamlit_result/INPUT_FILENAME_NO_EXT/timestamped_folder/result.png
        
        input_stem = Path(uploaded_file.name).stem
        target_base = OUTPUT_DIR / input_stem
        
        if target_base.exists():
            # Find subdirs, sort by mtime
            subdirs = sorted([d for d in target_base.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
            if subdirs:
                latest_run = subdirs[0]
                result_img = latest_run / "result.png"
                
                if result_img.exists():
                    st.markdown("---")
                    st.subheader("🖼️ So sánh Before/After")
                    
                    # Show Before/After Comparison Slider
                    if HAS_IMAGE_COMPARISON:
                        # Load images
                        img_before = Image.open(file_path)
                        img_after = Image.open(result_img)
                        
                        # Display comparison slider
                        result_placeholder.empty()
                        image_comparison(
                            img1=img_before,
                            img2=img_after,
                            label1="Trước (Original)",
                            label2="Sau (Restored)",
                            width=700,
                            starting_position=50,
                            show_labels=True,
                            make_responsive=True,
                            in_memory=True
                        )
                        
                        # Also show separate images in expander
                        with st.expander("📸 Xem ảnh riêng lẻ"):
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.image(str(file_path), caption="Ảnh gốc (Before)", width='stretch')
                            with col_b:
                                st.image(str(result_img), caption="Ảnh phục hồi (After)", width='stretch')
                    else:
                        # Fallback to side-by-side display
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.image(str(file_path), caption="Ảnh gốc (Before)", width='stretch')
                        with col_b:
                            st.image(str(result_img), caption="Ảnh phục hồi (After)", width='stretch')
                        st.info("💡 Cài đặt streamlit-image-comparison để xem slider so sánh tốt hơn!")
                else:
                    st.error(f"Không tìm thấy file result.png trong {latest_run}")
            else:
                st.error(f"Không tìm thấy thư mục chạy nào trong {target_base}")
        else:
             st.error(f"Thư mục kết quả {target_base} chưa được tạo.")
             
        # Visualization of the Process Tree
        st.markdown("---")
        st.subheader("3. Quy trình thực thi & Lựa chọn (Process Visualization)")
        
        if target_base.exists() and subdirs:
             latest_run = subdirs[0]
             img_tree_root = latest_run / "img_tree"
             
             def render_flow(current_path, step_num=1):
                 # Find subtasks (steps) in this folder.
                 # Usually, a folder might have one or more sequential subtasks if the logic was linear, 
                 # but in this recursive structure: Current Folder -> has Subtask Folder -> has Tool Folders.
                 # The "Chosen Tool" folder will contain the Next Subtask Folder.
                 
                 subtasks = sorted([d for d in current_path.iterdir() if d.is_dir() and d.name.startswith("subtask-")])
                 
                 for subtask in subtasks:
                     subtask_name = subtask.name.replace("subtask-", "").upper()
                     st.markdown(f"#### Bước {step_num}: {subtask_name}")
                     
                     # Try to read scores
                     scores = {}
                     score_file = subtask / "tmp" / "result_scores.txt"
                     if not score_file.exists():
                          score_file = subtask / "tmp" / "result_scores_with_metrics.txt"
                     
                     if score_file.exists():
                         try:
                             with open(score_file, "r", encoding="utf-8") as f:
                                 for line in f:
                                     if "," in line:
                                         parts = line.strip().split(",")
                                         # format: image_TOOLNAME, HPSv2: x, Metric: y, Overall: z
                                         name_part = parts[0].strip()
                                         # Get the last part "Overall: 0.xyz"
                                         overall_part = parts[-1].strip()
                                         
                                         if ":" in overall_part:
                                             score_val = overall_part.split(":")[-1].strip()
                                         else:
                                             score_val = overall_part
                                         
                                         if name_part.startswith("image_"):
                                             t_name = name_part.replace("image_", "")
                                             # Handle potential "tool-" prefix if inconsistent
                                             if t_name.startswith("tool-"):
                                                 t_name = t_name.replace("tool-", "")
                                             try:
                                                 scores[t_name] = float(score_val)
                                             except:
                                                 pass
                         except Exception as e:
                             # st.error(f"Error reading scores: {e}")
                             pass

                     # Find tools (Candidates)
                     tools = sorted([d for d in subtask.iterdir() if d.is_dir() and d.name.startswith("tool-")])
                     
                     if not tools:
                         st.caption("Không có tool nào chạy trong bước này?")
                         continue
                         
                     # Display Candidates for this Step
                     # We determine which one was the "Winner" (Selected) by checking which one has deeper subtasks/0-img updates
                     # Or simpler: The one that allows recursion is the winner.
                     
                     cols = st.columns(min(len(tools), 4)) # Max 4 cols per row
                     winner_tool = None
                     
                     for idx, tool in enumerate(tools):
                         tool_name = tool.name.replace("tool-", "")
                         
                         has_children = any(d.is_dir() and d.name.startswith("subtask-") for d in tool.iterdir())
                         
                         # Get score
                         score_display = ""
                         if tool_name in scores:
                             score_display = f" | {scores[tool_name]:.4f}"
                         
                         # For display:
                         col_idx = idx % 4
                         with cols[col_idx]:
                             img_path = tool / "0-img" / "output.png"
                             if img_path.exists():
                                 if has_children:
                                     st.image(str(img_path), width=150, caption=f"{tool_name}{score_display}")
                                     winner_tool = tool
                                 else:
                                     st.image(str(img_path), width=150, caption=f"{tool_name}{score_display}")
                                     
                     
                     if winner_tool:
                         # Continue flow from the winner
                         st.markdown(f"Đã chọn **{winner_tool.name.replace('tool-', '')}** để đi tiếp:")
                         render_flow(winner_tool, step_num + 1)
                     elif len(tools) > 0:
                         # Could be the final step?
                         pass
 
             if img_tree_root.exists():
                 render_flow(img_tree_root)
                 st.markdown("---")
                 st.info("""
                 **ℹ️ Chú thích về Điểm đánh giá (Score):**
                 
                 Điểm số này là sự tổng hợp giữa **HPSv2 (Thẩm mỹ)** và **IQA Metrics (Kỹ thuật)**:
                 
                 - **HPSv2**: Đánh giá độ "ưa nhìn" và thẩm mỹ theo mắt con người.
                 - **CLIPIQA+**: Đánh giá dựa trên mô hình ngôn ngữ-hình ảnh (CLIP), hiểu ngữ nghĩa bức ảnh.
                 - **MANIQA**: Sử dụng mạng Attention đa chiều để soi xét chi tiết và cấu trúc.
                 - **MUSIQ**: Mô hình Transformer đa tỷ lệ, đánh giá tốt độ phân giải và bố cục.
                 - **NIQE**: Đo độ "tự nhiên" của ảnh (Naturalness), ảnh càng ít nhiễu càng tốt.
                 
                 *Điểm càng cao thể hiện bức ảnh càng cân bằng giữa phục hồi kỹ thuật và thẩm mỹ.*
                 """)
             else:
                 st.info("Chưa có dữ liệu chi tiết (img_tree).")

    else:
        st.error(f"Có lỗi xảy ra! Exit code: {process.returncode}")
