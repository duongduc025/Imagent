import streamlit as st
import subprocess
import os
import shutil
import time
from pathlib import Path
import glob
import shlex
from PIL import Image
import json
from datetime import datetime

# Try to import required libraries
try:
    from streamlit_image_comparison import image_comparison
    HAS_IMAGE_COMPARISON = True
except ImportError:
    HAS_IMAGE_COMPARISON = False

try:
    from streamlit_elements import elements, mui, html, sync
    HAS_ELEMENTS = True
except ImportError:
    HAS_ELEMENTS = False

# Config
INPUT_DIR = Path("assets/streamlit_input")
OUTPUT_DIR = Path("outputs/streamlit_result")
STATUS_FILE = Path("outputs/.processing_status.json")

# Page config with Material Design theme
st.set_page_config(
    page_title="Imagent - AI Image Restoration",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Imagent - Phục hồi ảnh thông minh với AI"
    }
)

# Custom CSS for Material Design look
st.markdown("""
<style>
    /* Material Design Colors */
    :root {
        --primary: #1976d2;
        --primary-dark: #1565c0;
        --primary-light: #42a5f5;
        --secondary: #ff4081;
        --background: #fafafa;
        --surface: #ffffff;
        --error: #f44336;
        --success: #4caf50;
    }
    
    /* Main container */
    .main {
        background-color: var(--background);
    }
    
    /* Material Card style */
    .material-card {
        background: white;
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 16px;
    }
    
    /* Material Button override */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
        color: white;
        border: none;
        border-radius: 4px;
        padding: 12px 24px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        transform: translateY(-2px);
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
    }
    
    /* Info boxes */
    .element-container .stAlert {
        border-radius: 8px;
        border-left: 4px solid var(--primary);
    }
    
    /* Typography */
    h1, h2, h3 {
        font-family: 'Roboto', sans-serif;
        font-weight: 500;
    }
    
    /* Image container */
    .image-container {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
    }
    
    .image-container:hover {
        transform: scale(1.02);
    }
    
    /* Status chip */
    .status-chip {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 500;
        text-transform: uppercase;
    }
    
    .status-processing {
        background: #fff3e0;
        color: #e65100;
    }
    
    .status-complete {
        background: #e8f5e9;
        color: #2e7d32;
    }
    
    .status-error {
        background: #ffebee;
        color: #c62828;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0
if 'process_pid' not in st.session_state:
    st.session_state.process_pid = None

# Functions
def save_status(status_data):
    """Save processing status to file"""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, 'w') as f:
        json.dump(status_data, f)

def load_status():
    """Load processing status from file"""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def check_new_results(input_filename):
    """Check for new results in output directory"""
    if not input_filename:
        return None
        
    input_stem = Path(input_filename).stem
    target_base = OUTPUT_DIR / input_stem
    
    if target_base.exists():
        subdirs = sorted([d for d in target_base.iterdir() if d.is_dir()], 
                        key=lambda x: x.stat().st_mtime, reverse=True)
        if subdirs:
            latest_run = subdirs[0]
            result_img = latest_run / "result.png"
            if result_img.exists():
                return {
                    'path': str(result_img),
                    'folder': str(latest_run),
                    'timestamp': latest_run.stat().st_mtime
                }
    return None

# Header with Material Design
st.markdown("""
<div style='background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); padding: 32px; border-radius: 8px; margin-bottom: 24px;'>
    <h1 style='color: white; margin: 0; font-size: 36px; font-weight: 500;'>
        ✨ Imagent - AI Image Restoration
    </h1>
    <p style='color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 16px;'>
        Phục hồi ảnh thông minh với công nghệ AI và 4K upscaling
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar with Material UI
with st.sidebar:
    st.markdown("### ⚙️ Cấu hình")
    
    gpu_id = st.text_input("🎮 GPU ID", "0", help="ID của GPU sử dụng để xử lý")
    profile_name = st.selectbox(
        "📋 Profile",
        ["GPT4V_Profile", "Custom_Profile"],
        help="Chọn profile xử lý"
    )
    
    st.markdown("---")
    
    # Auto-refresh settings
    st.markdown("### 🔄 Tự động cập nhật")
    auto_refresh = st.checkbox("Bật tự động làm mới", value=True, 
                               help="Tự động kiểm tra kết quả mới")
    if auto_refresh:
        refresh_interval = st.slider("Chu kỳ làm mới (giây)", 2, 10, 3)
    else:
        refresh_interval = None
    
    st.markdown("---")
    
    # Status info
    st.markdown("### 📊 Thông tin")
    status_data = load_status()
    if status_data:
        status = status_data.get('status', 'unknown')
        if status == 'processing':
            st.markdown('<span class="status-chip status-processing">⚡ Đang xử lý</span>', 
                       unsafe_allow_html=True)
        elif status == 'complete':
            st.markdown('<span class="status-chip status-complete">✅ Hoàn thành</span>', 
                       unsafe_allow_html=True)
        elif status == 'error':
            st.markdown('<span class="status-chip status-error">❌ Lỗi</span>', 
                       unsafe_allow_html=True)
        
        if 'filename' in status_data:
            st.caption(f"📄 File: {status_data['filename']}")
        if 'started_at' in status_data:
            st.caption(f"🕐 Bắt đầu: {status_data['started_at']}")
    else:
        st.markdown('<span class="status-chip">💤 Sẵn sàng</span>', unsafe_allow_html=True)
    
    if not HAS_IMAGE_COMPARISON:
        st.warning("📦 Cài đặt streamlit-image-comparison")
        st.code("pip install streamlit-image-comparison", language="bash")
    
    if not HAS_ELEMENTS:
        st.warning("📦 Cài đặt streamlit-elements")
        st.code("pip install streamlit-elements", language="bash")

# Main content area
if HAS_ELEMENTS:
    # Material UI Layout
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Process", "🖼️ Results", "📊 Process Flow"])
    
    with tab1:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="material-card">', unsafe_allow_html=True)
            st.markdown("#### 📁 Chọn ảnh để phục hồi")
            
            uploaded_file = st.file_uploader(
                "Kéo thả hoặc click để chọn ảnh",
                type=['png', 'jpg', 'jpeg'],
                help="Hỗ trợ PNG, JPG, JPEG"
            )
            
            if uploaded_file:
                # Save file
                if INPUT_DIR.exists():
                    shutil.rmtree(INPUT_DIR)
                INPUT_DIR.mkdir(parents=True, exist_ok=True)
                
                file_path = INPUT_DIR / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                st.markdown("##### 🖼️ Preview")
                st.image(str(file_path), width='stretch')
                
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                img = Image.open(file_path)
                st.caption(f"📐 Kích thước: {img.size[0]}x{img.size[1]} | 💾 Dung lượng: {file_size:.2f} MB")
                
                st.markdown("---")
                start_btn = st.button("🚀 BẮT ĐẦU PHỤC HỒI", type="primary", use_container_width=True)
            else:
                start_btn = False
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="material-card">', unsafe_allow_html=True)
            st.markdown("#### 📝 Logs & Status")
            
            log_container = st.container()
            progress_container = st.empty()
            status_container = st.empty()
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        result_area = st.container()
        
    with tab3:
        flow_area = st.container()

else:
    # Fallback to classic layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📁 Chọn ảnh")
        uploaded_file = st.file_uploader("Tải ảnh lên (PNG, JPG)", type=['png', 'jpg', 'jpeg'])
        
        if uploaded_file:
            if INPUT_DIR.exists():
                shutil.rmtree(INPUT_DIR)
            INPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            file_path = INPUT_DIR / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.image(str(file_path), caption="Ảnh gốc", width='stretch')
            start_btn = st.button("🚀 Bắt đầu phục hồi", type="primary")
        else:
            start_btn = False
    
    with col2:
        st.subheader("🖼️ Kết quả")
        result_placeholder = st.empty()
        log_area = st.empty()

# Processing logic
if uploaded_file and start_btn:
    st.session_state.processing = True
    
    # Save status
    save_status({
        'status': 'processing',
        'filename': uploaded_file.name,
        'started_at': datetime.now().isoformat(),
        'progress': 0
    })
    
    cmd_list = [
        "/venv/4kagent/bin/python", "infer_imagent.py",
        "--input_dir", str(INPUT_DIR),
        "--output_dir", str(OUTPUT_DIR),
        "--profile_name", profile_name,
        "--tool_run_gpu_id", str(gpu_id)
    ]
    
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    
    st.toast("🚀 Đang khởi chạy Imagent...")
    
    process = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
        universal_newlines=True
    )
    
    st.session_state.process_pid = process.pid
    
    logs = []
    progress_value = 0
    
    with st.status("⚙️ Đang xử lý...", expanded=True) as status:
        st_step_init = status.write("🎬 Khởi động Imagent...")
        st_step_percept = None
        st_step_plan = None
        st_step_exec = None
        st_step_face = None
        
        progress_bar = st.progress(0)
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                clean_line = line.strip()
                logs.append(clean_line)
                
                # Update progress based on stages
                if "Nhận định của AI:" in clean_line:
                    progress_value = 20
                    if st_step_init: st_step_init = None
                    if not st_step_percept: 
                        st_step_percept = status.write("🔍 Đang phân tích ảnh (Perception)...")
                    st.write(f"&nbsp;&nbsp;&nbsp;&nbsp; {clean_line.split(':', 1)[1].strip()}")
                    
                if "Kế hoạch:" in clean_line:
                    progress_value = 40
                    if not st_step_plan: 
                        st_step_plan = status.write("📋 Đang lập kế hoạch (Planning)...")
                    st.info(f"Kế hoạch: {clean_line.split(':', 1)[1].strip()}")
                    
                if "được dùng để xử lý" in clean_line:
                    progress_value = min(progress_value + 5, 80)
                    parts = clean_line.split("(", 1)
                    tool_name = parts[0].strip()
                    if not st_step_exec: 
                        st_step_exec = status.write(f"⚡ Đang thực thi các công cụ...")
                    st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;Chạy thử: **{tool_name}**")
                    
                if "Tool tốt nhất:" in clean_line:
                    tool = clean_line.split(':', 1)[1].strip()
                    st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;**✅ CHỐT**: {tool}")
                    
                if "Khuôn mặt" in clean_line and "Kết quả phục hồi" in clean_line:
                    progress_value = 90
                    if not st_step_face: 
                        st_step_face = status.write("👤 Đang phục hồi khuôn mặt...")
                
                progress_bar.progress(progress_value / 100)
                
                # Update status file
                save_status({
                    'status': 'processing',
                    'filename': uploaded_file.name,
                    'started_at': datetime.now().isoformat(),
                    'progress': progress_value
                })
                
                # Show last 30 lines
                if HAS_ELEMENTS:
                    with log_container:
                        st.code("\n".join(logs[-30:]), language='bash')
                else:
                    log_area.code("\n".join(logs[-30:]), language='bash')
        
        progress_bar.progress(100)
        status.update(label="✅ Hoàn thành!", state="complete", expanded=False)
    
    # Show full log
    with st.expander("📋 Xem toàn bộ Log"):
        st.code("\n".join(logs), language='bash')
    
    if process.returncode == 0:
        st.balloons()
        st.success("🎉 Xử lý hoàn tất!")
        
        # Update status
        save_status({
            'status': 'complete',
            'filename': uploaded_file.name,
            'completed_at': datetime.now().isoformat(),
            'progress': 100
        })
        
        st.session_state.processing = False
        st.session_state.last_result = uploaded_file.name
        
        # Force refresh to show results
        st.rerun()
    else:
        st.error(f"❌ Có lỗi xảy ra! Exit code: {process.returncode}")
        save_status({
            'status': 'error',
            'filename': uploaded_file.name,
            'error_code': process.returncode
        })

# Auto-refresh check for new results
if auto_refresh and not st.session_state.processing:
    current_status = load_status()
    if current_status and current_status.get('status') == 'complete':
        filename = current_status.get('filename')
        if filename:
            new_result = check_new_results(filename)
            if new_result and (not st.session_state.last_result or 
                             st.session_state.last_result != filename):
                st.session_state.last_result = filename
                st.rerun()
    
    # Auto-refresh timer
    if refresh_interval:
        time.sleep(refresh_interval)
        st.session_state.refresh_counter += 1
        st.rerun()

# Display results if available
if st.session_state.last_result or (uploaded_file and not start_btn):
    result_filename = st.session_state.last_result or (uploaded_file.name if uploaded_file else None)
    
    if result_filename:
        result_data = check_new_results(result_filename)
        
        if result_data:
            input_stem = Path(result_filename).stem
            input_path = INPUT_DIR / result_filename
            result_img_path = Path(result_data['path'])
            
            if input_path.exists() and result_img_path.exists():
                if HAS_ELEMENTS:
                    with result_area:
                        st.markdown("---")
                        st.markdown("### 🖼️ So sánh Before/After")
                        
                        if HAS_IMAGE_COMPARISON:
                            img_before = Image.open(input_path)
                            img_after = Image.open(result_img_path)
                            
                            image_comparison(
                                img1=img_before,
                                img2=img_after,
                                label1="Trước (Original)",
                                label2="Sau (Restored)",
                                width=900,
                                starting_position=50,
                                show_labels=True,
                                make_responsive=True,
                                in_memory=True
                            )
                            
                            with st.expander("📸 Xem ảnh riêng lẻ"):
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.image(str(input_path), caption="Ảnh gốc (Before)", width='stretch')
                                with col_b:
                                    st.image(str(result_img_path), caption="Ảnh phục hồi (After)", width='stretch')
                        else:
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.image(str(input_path), caption="Ảnh gốc (Before)", width='stretch')
                            with col_b:
                                st.image(str(result_img_path), caption="Ảnh phục hồi (After)", width='stretch')
                
                # Process Flow Visualization
                if HAS_ELEMENTS:
                    with flow_area:
                        st.markdown("### 📊 Quy trình thực thi")
                        
                        latest_run = Path(result_data['folder'])
                        img_tree_root = latest_run / "img_tree"
                        
                        if img_tree_root.exists():
                            # Render process flow (keeping original logic)
                            def render_flow(current_path, step_num=1):
                                subtasks = sorted([d for d in current_path.iterdir() 
                                                 if d.is_dir() and d.name.startswith("subtask-")])
                                
                                for subtask in subtasks:
                                    subtask_name = subtask.name.replace("subtask-", "").upper()
                                    st.markdown(f"#### 🔹 Bước {step_num}: {subtask_name}")
                                    
                                    # Read scores
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
                                                        name_part = parts[0].strip()
                                                        overall_part = parts[-1].strip()
                                                        
                                                        if ":" in overall_part:
                                                            score_val = overall_part.split(":")[-1].strip()
                                                        else:
                                                            score_val = overall_part
                                                        
                                                        if name_part.startswith("image_"):
                                                            t_name = name_part.replace("image_", "").replace("tool-", "")
                                                            try:
                                                                scores[t_name] = float(score_val)
                                                            except:
                                                                pass
                                        except:
                                            pass
                                    
                                    tools = sorted([d for d in subtask.iterdir() 
                                                  if d.is_dir() and d.name.startswith("tool-")])
                                    
                                    if tools:
                                        cols = st.columns(min(len(tools), 4))
                                        winner_tool = None
                                        
                                        for idx, tool in enumerate(tools):
                                            tool_name = tool.name.replace("tool-", "")
                                            has_children = any(d.is_dir() and d.name.startswith("subtask-") 
                                                             for d in tool.iterdir())
                                            
                                            score_display = ""
                                            if tool_name in scores:
                                                score_display = f" | ⭐ {scores[tool_name]:.4f}"
                                            
                                            col_idx = idx % 4
                                            with cols[col_idx]:
                                                img_path = tool / "0-img" / "output.png"
                                                if img_path.exists():
                                                    if has_children:
                                                        st.image(str(img_path), width=180, 
                                                               caption=f"✅ {tool_name}{score_display}")
                                                        winner_tool = tool
                                                    else:
                                                        st.image(str(img_path), width=180, 
                                                               caption=f"{tool_name}{score_display}")
                                        
                                        if winner_tool:
                                            st.markdown(f"➡️ **{winner_tool.name.replace('tool-', '')}** được chọn")
                                            render_flow(winner_tool, step_num + 1)
                            
                            render_flow(img_tree_root)
                            
                            st.markdown("---")
                            st.info("""
                            **ℹ️ Giải thích điểm đánh giá:**
                            
                            - **HPSv2**: Thẩm mỹ và độ ưa nhìn
                            - **CLIPIQA+**: Đánh giá ngữ nghĩa
                            - **MANIQA**: Chi tiết và cấu trúc
                            - **MUSIQ**: Độ phân giải và bố cục
                            - **NIQE**: Độ tự nhiên
                            """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>Powered by <strong>Imagent</strong> | AI Image Restoration Technology</p>
    <p style='font-size: 12px;'>© 2025 Imagent. All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
