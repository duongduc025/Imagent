import os
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

# Optional: before/after slider
try:
    from streamlit_image_comparison import image_comparison
    HAS_IMAGE_COMPARISON = True
except Exception:
    HAS_IMAGE_COMPARISON = False


# =====================
# Paths / Config
# =====================
INPUT_DIR = Path("assets/streamlit_input")
OUTPUT_DIR = Path("outputs/streamlit_result")
STATUS_FILE = Path("outputs/.processing_status.json")

PYTHON_BIN = "/venv/4kagent/bin/python"     # <-- chỉnh nếu khác
INFER_SCRIPT = "infer_imagent.py"           # <-- chỉnh nếu khác

# Display sizing (fix "slider nhỏ xíu")
COMPARE_WIDTH_MAIN = 1000   # tab Compare
COMPARE_WIDTH_STEP = 900    # tab Steps


# =====================
# Page
# =====================
st.set_page_config(
    page_title="Imagent - AI Image Restoration",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal CSS (không phá theme)
st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px; }
.card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 16px;
}
.small { color: rgba(255,255,255,0.65); font-size: 0.9rem; }
.badge {
  display:inline-block; padding: 4px 10px; border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.04);
  font-size: 0.8rem;
}
hr { border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 12px 0; }
</style>
""", unsafe_allow_html=True)


# =====================
# Session state
# =====================
def _ss_init():
    st.session_state.setdefault("processing", False)
    st.session_state.setdefault("last_filename", None)
    st.session_state.setdefault("logs", [])
    st.session_state.setdefault("last_progress", 0)

_ss_init()

# Clear old state on a fresh visit (new session)
if "fresh_visit" not in st.session_state:
    st.session_state.fresh_visit = True
    st.session_state.last_filename = None
    st.session_state.logs = []
    st.session_state.last_progress = 0

    # remove old status file so it won't show previous run
    try:
        STATUS_FILE.unlink()
    except FileNotFoundError:
        pass

    # optional: clear old uploaded input
    if INPUT_DIR.exists():
        shutil.rmtree(INPUT_DIR)



# =====================
# Utils: load & resize for display
# =====================
def load_for_display(path: Path, width: int) -> Image.Image:
    """Resize image to a fixed width for UI (fix slider tiny)."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    if w == width:
        return img
    new_h = max(1, int(h * (width / w)))
    return img.resize((width, new_h), Image.LANCZOS)


# =====================
# Status helpers
# =====================
def save_status(payload: dict):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_status():
    if not STATUS_FILE.exists():
        return None
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# =====================
# Results discovery
# =====================
def check_new_results(input_filename: str):
    if not input_filename:
        return None
    stem = Path(input_filename).stem
    target_base = OUTPUT_DIR / stem
    if not target_base.exists():
        return None

    subdirs = sorted([d for d in target_base.iterdir() if d.is_dir()],
                     key=lambda x: x.stat().st_mtime, reverse=True)
    if not subdirs:
        return None

    latest_run = subdirs[0]
    result_img = latest_run / "result.png"
    if not result_img.exists():
        return None

    return {"folder": latest_run, "result": result_img, "timestamp": latest_run.stat().st_mtime}


# =====================
# img_tree: scoring + UI
# =====================
def _read_scores(subtask: Path) -> dict:
    scores = {}
    score_file = subtask / "tmp" / "result_scores_with_metrics.txt"
    if not score_file.exists():
        score_file = subtask / "tmp" / "result_scores.txt"
    if not score_file.exists():
        return scores

    try:
        with open(score_file, "r", encoding="utf-8") as f:
            for line in f:
                if "," not in line:
                    continue
                parts = line.strip().split(",")
                name_part = parts[0].strip()
                overall_part = parts[-1].strip()
                score_val = overall_part.split(":")[-1].strip() if ":" in overall_part else overall_part

                if name_part.startswith("image_"):
                    t_name = name_part.replace("image_", "").replace("tool-", "")
                    try:
                        scores[t_name] = float(score_val)
                    except Exception:
                        pass
    except Exception:
        pass
    return scores


def _tool_is_winner(tool_dir: Path) -> bool:
    return any(d.is_dir() and d.name.startswith("subtask-") for d in tool_dir.iterdir())


def _collect_candidates(subtask: Path):
    scores = _read_scores(subtask)
    tools = sorted([d for d in subtask.iterdir() if d.is_dir() and d.name.startswith("tool-")])

    cands = []
    for tool in tools:
        tool_name = tool.name.replace("tool-", "")
        out_img = tool / "0-img" / "output.png"
        if out_img.exists():
            cands.append({
                "tool_dir": tool,
                "tool": tool_name,
                "path": out_img,
                "score": scores.get(tool_name),
                "is_winner": _tool_is_winner(tool),
            })

    def _key(x):
        score = x["score"] if x["score"] is not None else -1e9
        mtime = x["path"].stat().st_mtime if x["path"].exists() else 0
        return (1 if x["is_winner"] else 0, score, mtime)

    cands.sort(key=_key, reverse=True)
    winner = next((c for c in cands if c["is_winner"]), None)
    if winner is None and cands:
        winner = cands[0]
    return cands, winner


def _find_root_input(img_tree_root: Path) -> Path | None:
    p = img_tree_root / "0-img" / "input.png"
    return p if p.exists() else None


def render_flow_pretty(current_path: Path, input_img: Path, step_num: int = 1, top_k: int = 8):
    subtasks = sorted([d for d in current_path.iterdir() if d.is_dir() and d.name.startswith("subtask-")])

    for subtask in subtasks:
        subtask_name = subtask.name.replace("subtask-", "").upper()
        cands, winner = _collect_candidates(subtask)
        if not cands:
            continue

        winner_label = winner["tool"].upper() if winner else "N/A"
        winner_score = f"{winner['score']:.4f}" if (winner and winner["score"] is not None) else "-"

        with st.expander(f"🔹 Bước {step_num}: {subtask_name}  •  Winner: {winner_label}  •  ⭐ {winner_score}", expanded=False):
            # --- Compare + Thumb side-by-side (giảm khoảng trắng) ---
            left, right = st.columns([2.2, 1], gap="large", vertical_alignment="top")

            # picker
            labels = []
            for c in cands:
                s = f"{c['score']:.4f}" if c["score"] is not None else "-"
                mark = " ✅" if winner and c["path"] == winner["path"] else ""
                labels.append(f"{c['tool'].upper()}{mark}  •  ⭐ {s}")

            pick = left.selectbox(
                "So sánh nhanh (chọn tool)",
                options=list(range(len(cands))),
                format_func=lambda i: labels[i],
                index=0,
                key=f"pick_{subtask.as_posix()}_{step_num}",
            )
            picked = cands[pick]

            # compare (resize to fixed width => không bị tiny)
            if HAS_IMAGE_COMPARISON:
                img1 = load_for_display(input_img, COMPARE_WIDTH_STEP)
                img2 = load_for_display(picked["path"], COMPARE_WIDTH_STEP)
                image_comparison(
                    img1=img1,
                    img2=img2,
                    label1="Input",
                    label2=f"Output • {picked['tool'].upper()}",
                    width=COMPARE_WIDTH_STEP,
                    starting_position=50,
                    show_labels=True,
                    make_responsive=False,
                    in_memory=True,
                )
            else:
                a, b = left.columns(2)
                with a:
                    st.image(str(input_img), use_container_width=True)
                with b:
                    st.image(str(picked["path"]), use_container_width=True)

            # thumbs on the right
            show_all = right.checkbox("Hiện tất cả", value=False, key=f"all_{subtask.as_posix()}_{step_num}")
            view = cands if show_all else cands[:top_k]

            # small 2-col grid inside right panel
            thumb_cols = right.columns(2, gap="small")
            for i, c in enumerate(view[:12]):  # cap for UI
                with thumb_cols[i % 2]:
                    right.image(str(c["path"]), use_container_width=True)
                    s = f"{c['score']:.4f}" if c["score"] is not None else "-"
                    badge = "✅" if winner and c["path"] == winner["path"] else ""
                    right.caption(f"{c['tool'].upper()} {badge} • ⭐ {s}")

            # recurse into winner for next steps
            if winner and winner["tool_dir"].exists():
                next_input = winner["path"] if winner["path"].exists() else input_img
                render_flow_pretty(winner["tool_dir"], next_input, step_num + 1, top_k=top_k)


# =====================
# Inference runner
# =====================
def run_inference(input_filename: str, gpu_id: str, profile_name: str):
    st.session_state.processing = True
    st.session_state.logs = []
    st.session_state.last_progress = 0

    save_status({
        "status": "processing",
        "filename": input_filename,
        "started_at": datetime.now().isoformat(),
        "progress": 0,
        "logs_tail": [],
    })

    cmd = [
        PYTHON_BIN, INFER_SCRIPT,
        "--input_dir", str(INPUT_DIR),
        "--output_dir", str(OUTPUT_DIR),
        "--profile_name", profile_name,
        "--tool_run_gpu_id", str(gpu_id),
    ]

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    progress = st.progress(0)
    with st.status("⚙️ Đang xử lý...", expanded=True) as status:
        status.write("🎬 Khởi chạy pipeline...")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
            universal_newlines=True,
        )

        p = 0
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if not line and proc.poll() is not None:
                break
            if not line:
                continue

            s = line.strip()
            if s:
                st.session_state.logs.append(s)

            # heuristics progress (gọn)
            if "Nhận định của AI:" in s:
                p = max(p, 20)
            elif "Kế hoạch:" in s:
                p = max(p, 40)
            elif "được dùng để xử lý" in s:
                p = min(max(p, 55), 80)
            elif "Tool tốt nhất:" in s:
                p = max(p, 85)
            elif "Khuôn mặt" in s and "Kết quả phục hồi" in s:
                p = max(p, 92)

            st.session_state.last_progress = p
            progress.progress(p / 100)

            save_status({
                "status": "processing",
                "filename": input_filename,
                "started_at": datetime.now().isoformat(),
                "progress": p,
                "logs_tail": st.session_state.logs[-200:],
            })

        rc = proc.poll() or 0
        progress.progress(1.0)

        if rc == 0:
            status.update(label="✅ Hoàn thành!", state="complete", expanded=False)
            save_status({
                "status": "complete",
                "filename": input_filename,
                "completed_at": datetime.now().isoformat(),
                "progress": 100,
                "logs_tail": st.session_state.logs[-200:],
            })
            st.session_state.processing = False
            st.session_state.last_filename = input_filename
            st.success("🎉 Xử lý hoàn tất!")
            st.rerun()
        else:
            status.update(label="❌ Lỗi", state="error", expanded=True)
            save_status({
                "status": "error",
                "filename": input_filename,
                "error_code": rc,
                "progress": p,
                "logs_tail": st.session_state.logs[-200:],
            })
            st.session_state.processing = False
            st.error(f"❌ Có lỗi xảy ra! Exit code: {rc}")


# =====================
# UI
# =====================
st.title("✨ Imagent - AI Image Restoration")

with st.sidebar:
    st.subheader("⚙️ Cấu hình")
    gpu_id = st.text_input("GPU ID", "0")
    profile_name = st.selectbox("Profile", ["GPT4V_Profile", "Custom_Profile"])
    # st.markdown("<div class='small'>Bật dark theme bằng <code>.streamlit/config.toml</code> (mẫu ở dưới).</div>", unsafe_allow_html=True)

left, right = st.columns([1, 1.9], gap="large")

with left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📁 Upload")
    up = st.file_uploader("Chọn ảnh", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

    start_btn = False
    if up is not None:
        if INPUT_DIR.exists():
            shutil.rmtree(INPUT_DIR)
        INPUT_DIR.mkdir(parents=True, exist_ok=True)

        file_path = INPUT_DIR / up.name
        with open(file_path, "wb") as f:
            f.write(up.getbuffer())

        img = Image.open(file_path)
        st.markdown(f"<span class='badge'>📐 {img.size[0]}×{img.size[1]}</span>", unsafe_allow_html=True)
        st.image(str(file_path), use_container_width=True)

        start_btn = st.button("🚀 XỬ LÝ", use_container_width=True, disabled=st.session_state.processing)

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("🖼️ Kết quả")
    status = load_status()

    if status and status.get("status") == "processing":
        p = int(status.get("progress", 0))
        st.markdown(f"<span class='badge'>Processing • {p}%</span>", unsafe_allow_html=True)
        st.progress(p / 100)

    if status and status.get("status") == "error":
        st.markdown("<span class='badge'>Error</span>", unsafe_allow_html=True)
        st.error(f"Exit code: {status.get('error_code')}")

    last_file = (up.name if up else None) or st.session_state.last_filename

    result_info = check_new_results(last_file) if last_file else None

    if result_info and last_file:
        input_path = INPUT_DIR / last_file
        result_img_path = result_info["result"]
        latest_run = result_info["folder"]

        tabs = st.tabs(["✅ Compare", "🧩 Steps", "📋 Logs"])

        with tabs[0]:
            if input_path.exists() and result_img_path.exists():
                if HAS_IMAGE_COMPARISON:
                    img1 = load_for_display(input_path, COMPARE_WIDTH_MAIN)
                    img2 = load_for_display(result_img_path, COMPARE_WIDTH_MAIN)
                    image_comparison(
                        img1=img1,
                        img2=img2,
                        label1="Before",
                        label2="After",
                        width=COMPARE_WIDTH_MAIN,
                        starting_position=50,
                        show_labels=True,
                        make_responsive=False,
                        in_memory=True,
                    )
                else:
                    a, b = st.columns(2)
                    with a:
                        st.image(str(input_path), use_container_width=True)
                    with b:
                        st.image(str(result_img_path), use_container_width=True)

                with open(result_img_path, "rb") as f:
                    st.download_button("⬇️ Tải ảnh kết quả", data=f, file_name="result.png", use_container_width=True)

        with tabs[1]:
            img_tree_root = latest_run / "img_tree"
            if img_tree_root.exists():
                root_input = _find_root_input(img_tree_root) or (input_path if input_path.exists() else None)
                if root_input is not None:
                    render_flow_pretty(img_tree_root, root_input, step_num=1, top_k=8)
                else:
                    st.info("Không tìm thấy input.png trong img_tree và input gốc.")
            else:
                st.info("📦 Chưa có dữ liệu img_tree")

        with tabs[2]:
            tail = (status.get("logs_tail") if status else None) or st.session_state.logs[-200:]
            if tail:
                st.code("\n".join(tail), language="bash")
            else:
                st.info("Chưa có log.")

    else:
        st.info("Chưa có kết quả. Upload ảnh và bấm **XỬ LÝ** để bắt đầu.")

    st.markdown("</div>", unsafe_allow_html=True)

if up is not None and start_btn and not st.session_state.processing:
    run_inference(up.name, gpu_id=gpu_id, profile_name=profile_name)
