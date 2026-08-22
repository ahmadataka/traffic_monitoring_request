from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from traffic_monitoring.config import CameraConfig, load_cameras, save_camera
from traffic_monitoring.pipeline import AnalysisOptions, analyze_video


PROJECT_ROOT = Path(__file__).parent
CAMERA_FILE = PROJECT_ROOT / "config" / "cameras.json"


def save_upload(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(uploaded_file.getbuffer())
        return Path(handle.name)


def camera_editor() -> None:
    with st.expander("Add or update camera configuration"):
        with st.form("camera-form", clear_on_submit=True):
            camera_id = st.text_input("Camera ID", placeholder="jogja-example-01")
            name = st.text_input("Camera name", placeholder="Example intersection")
            source_url = st.text_input("Optional public stream URL")
            count_line = st.text_input(
                "Counting line as x1,y1,x2,y2",
                value="120,360,1160,360",
                help="Coordinates use the analysis resolution set below.",
            )
            analysis_width = st.number_input("Analysis width (pixels)", 640, 1920, 960, 32)
            submitted = st.form_submit_button("Save camera")
        if submitted:
            try:
                points = [int(value.strip()) for value in count_line.split(",")]
                if len(points) != 4 or not camera_id or not name:
                    raise ValueError("Provide an ID, a name, and four line coordinates.")
                save_camera(
                    CAMERA_FILE,
                    CameraConfig(
                        id=camera_id,
                        name=name,
                        source_url=source_url or None,
                        count_line=tuple(points),
                        analysis_width=int(analysis_width),
                    ),
                )
                st.success("Camera configuration saved.")
            except ValueError as error:
                st.error(str(error))


def main() -> None:
    st.set_page_config(page_title="Traffic Monitoring Request", page_icon="T", layout="wide")
    st.title("Traffic Monitoring Request")
    st.caption("On-demand vehicle counting and congestion estimation from a selected CCTV clip.")

    cameras = load_cameras(CAMERA_FILE)
    camera_editor()
    cameras = load_cameras(CAMERA_FILE)

    camera_names = {f"{camera.id} — {camera.name}": camera for camera in cameras}
    selected_label = st.selectbox("Choose camera", list(camera_names))
    camera = camera_names[selected_label]

    st.info(
        "Upload a short CCTV clip for the most reliable MVP workflow. A configured public stream URL can be used when the source allows direct access."
    )
    uploaded_video = st.file_uploader("CCTV video clip", type=["mp4", "mov", "avi", "mkv"])

    controls, summary = st.columns([1, 2])
    with controls:
        duration = st.slider("Analysis window (seconds)", 30, 300, 180, 30)
        sample_fps = st.select_slider("Sampling rate (FPS)", options=[1, 2, 3], value=1)
        confidence = st.slider("Detection confidence", 0.10, 0.80, 0.35, 0.05)
        analyze = st.button("Analyze traffic", type="primary", use_container_width=True)
    with summary:
        st.markdown(
            "**What the result includes**  \n"
            "Vehicle classes, directional crossings, road occupancy, congestion label, and an annotated representative frame. "
            "Speed is intentionally deferred until this camera has a validated road calibration."
        )

    if not analyze:
        return

    source_path: str | Path | None = None
    cleanup_path: Path | None = None
    if uploaded_video is not None:
        cleanup_path = save_upload(uploaded_video)
        source_path = cleanup_path
    elif camera.source_url:
        source_path = camera.source_url

    if source_path is None:
        st.error("Upload a video clip or configure a direct public stream URL for this camera.")
        return

    options = AnalysisOptions(
        duration_seconds=duration,
        sample_fps=sample_fps,
        confidence=confidence,
    )
    try:
        with st.spinner("Analyzing sampled frames on this Mac..."):
            result = analyze_video(source_path, camera, options)
    except Exception as error:  # User-facing UI: preserve the actual cause for local troubleshooting.
        st.error(f"Analysis could not be completed: {error}")
        return
    finally:
        if cleanup_path and cleanup_path.exists():
            cleanup_path.unlink()

    result_dir = PROJECT_ROOT / "results" / camera.id
    result_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = result_dir / f"{timestamp}.jpg"
    json_path = result_dir / f"{timestamp}.json"
    result.save(image_path, json_path)

    st.success(f"Analysis complete. Processed {result.sampled_frames} sampled frames.")
    left, right = st.columns([3, 2])
    with left:
        st.image(result.annotated_frame, caption="Representative analyzed frame", channels="BGR", use_container_width=True)
    with right:
        st.metric("Traffic condition", result.traffic_condition.title())
        st.metric("Total vehicles", result.total_vehicles)
        st.metric("Road occupancy", f"{result.occupancy_percent:.0f}%")
        st.metric("Directional crossings", result.directional_crossings)

    st.subheader("Vehicle counts")
    st.dataframe(result.count_table, use_container_width=True, hide_index=True)
    st.caption(f"Saved results: `{image_path.relative_to(PROJECT_ROOT)}` and `{json_path.relative_to(PROJECT_ROOT)}`")


if __name__ == "__main__":
    main()
