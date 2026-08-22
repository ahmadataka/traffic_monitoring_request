from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from traffic_monitoring.config import load_cameras
from traffic_monitoring.pipeline import AnalysisOptions, analyze_video


PROJECT_ROOT = Path(__file__).parent
CAMERA_FILE = PROJECT_ROOT / "config" / "cameras.json"
ANALYSIS_PRESET = AnalysisOptions(duration_seconds=30, sample_fps=1, confidence=0.35)


def main() -> None:
    st.set_page_config(page_title="Traffic Monitoring Request", page_icon="T", layout="wide")
    st.title("Traffic Monitoring Request")
    st.caption("Choose an area to get a traffic summary from its public CCTV view.")

    cameras = load_cameras(CAMERA_FILE)
    if not cameras:
        st.error("No public cameras are currently configured.")
        return

    camera_names = {camera.name: camera for camera in cameras}
    selected_label = st.selectbox("Choose area", list(camera_names), index=0)
    camera = camera_names[selected_label]
    st.caption("This checks a short public live-feed window and usually takes about 20-45 seconds.")
    analyze = st.button("Analyze traffic", type="primary", width="stretch")

    if not analyze:
        st.divider()
        st.subheader("Result")
        st.caption("Choose an area above, then select Analyze traffic.")
        return

    if camera.source_url is None:
        st.error("This camera is temporarily unavailable. Please choose another area.")
        return

    try:
        with st.spinner("Analyzing traffic..."):
            result = analyze_video(camera.source_url, camera, ANALYSIS_PRESET)
    except Exception as error:  # User-facing UI: preserve the actual cause for local troubleshooting.
        st.error("This public camera could not be analyzed right now. Please try again or choose another area.")
        with st.expander("Technical details"):
            st.code(str(error))
        return

    result_dir = PROJECT_ROOT / "results" / camera.id
    result_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = result_dir / f"{timestamp}.jpg"
    json_path = result_dir / f"{timestamp}.json"
    result.save(image_path, json_path)

    st.success("Analysis complete")
    st.subheader(f"Result: {camera.name}")
    left, right = st.columns([3, 2])
    with left:
        st.image(result.annotated_frame, caption="Representative CCTV frame", channels="BGR", width="stretch")
    with right:
        st.metric("Traffic condition", result.traffic_condition.title())
        st.metric("Observed vehicles", result.total_vehicles)
        st.metric("Road occupancy", f"{result.occupancy_percent:.0f}%")
        st.metric("Line crossings", result.directional_crossings)

    st.subheader("Vehicle counts")
    st.dataframe(result.count_table, width="stretch", hide_index=True)
    st.caption("The result image and statistics are saved locally for this analysis.")


if __name__ == "__main__":
    main()
