# Traffic Monitoring Request

An on-demand, local-first computer-vision application for estimating traffic conditions from selected public CCTV feeds in Yogyakarta (DIY).

The intended experience is deliberately simple:

```text
Choose CCTV camera -> click Analyze Traffic -> receive an annotated screenshot and traffic statistics
```

The first version runs on a local Apple Silicon Mac. It analyzes a short video window only when requested, avoiding the cost and operational complexity of a 24/7 cloud service.

## Project goals

- Analyze one selected fixed CCTV camera on demand.
- Detect and classify `motorcycle`, `car`, `bus`, and `truck`.
- Count observed vehicles by class and line-crossing flow.
- Estimate traffic condition as `lancar`, `sedang`, `padat`, or `macet`.
- Estimate speed only for cameras that have completed a one-time road calibration.
- Return one representative annotated screenshot and a concise report.
- Preserve privacy by storing aggregated statistics by default, not continuous CCTV footage.

## User flow

1. The user chooses a configured camera from a list.
2. The user clicks **Analyze Traffic**.
3. The application acquires a short analysis window, normally 2-5 minutes, from the approved public feed or an uploaded clip.
4. Frames are sampled at 1-2 FPS and cropped to the road region of interest.
5. The system detects, tracks, and counts vehicles.
6. The interface displays the final result and an annotated representative frame.

Example result:

| Metric | Example |
| --- | --- |
| Traffic condition | Padat |
| Analysis window | 3 minutes |
| Observed vehicles | 186 |
| Motorcycles | 112 |
| Cars | 58 |
| Buses and trucks | 16 |
| Line crossings | 103 |
| Estimated average speed | 22 km/h (calibrated cameras only) |
| Road occupancy | 68% |

## System design

```text
Camera feed or uploaded clip
        |
        v
Acquisition and short-term frame buffer
        |
        v
Sampling (1-2 FPS) + road ROI crop
        |
        v
Vehicle detector -> multi-object tracker
        |
        v
Line crossing, lane occupancy, queue and speed calculations
        |
        v
Traffic classifier and result generator
        |
        v
Annotated screenshot + JSON statistics + local dashboard
```

## Recommended algorithms

| Capability | Recommendation | Reason |
| --- | --- | --- |
| Vehicle detection | YOLO nano-class model, such as YOLO11n or YOLOv8n | Strong accuracy/speed trade-off for local use |
| Local inference | Core ML or ONNX Runtime on Apple Silicon | Uses the Mac GPU/Neural Engine where supported |
| Multi-object tracking | ByteTrack | Reliable and efficient vehicle IDs between sampled frames |
| Counting | Per-camera virtual line crossing | Transparent, easy to audit, direction-aware |
| Queue estimation | Road ROI occupancy plus stopped-track duration | Works without specialized training data |
| Speed | Homography / inverse-perspective mapping and tracked displacement | Converts calibrated image coordinates to metres |
| Traffic classification | Explainable rules initially; optional XGBoost later | Avoids an unnecessary deep model for the MVP |

### Traffic-state logic

The initial classifier should use a rolling 1-5 minute summary of:

- directional flow: vehicles per minute;
- road occupancy: fraction of a configured road polygon covered by vehicles;
- queue length: number of slow or stopped tracked vehicles;
- average speed: only for calibrated fixed cameras.

Thresholds are configured per camera because a narrow street and a major intersection have different normal traffic volumes.

## Camera configuration

Each camera requires a small configuration record:

```yaml
id: jogja-example-01
name: Example intersection
source_type: hls_or_uploaded_video
source_url: https://approved-public-feed.example/stream.m3u8
analysis_duration_seconds: 180
sample_fps: 1
road_roi: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
count_lines:
  - name: northbound
    start: [x1, y1]
    end: [x2, y2]
calibration: optional
```

Use only public or explicitly authorized sources. Public viewing does not automatically grant permission to redistribute, retain, or commercially reuse footage. DIY ATCS recordings are reported as request-only; this project should not attempt to bypass that restriction.

## Local Mac requirements

| Scope | Suggested hardware |
| --- | --- |
| Basic pilot: one camera, 1 FPS, 2-5 minutes | Apple Silicon Mac with 16 GB unified memory |
| Comfortable development and 1080p analysis | M2/M3/M4 Mac with 16-24 GB unified memory |
| Storage | 20-50 GB free SSD space; statistics should be retained instead of raw video |

No dedicated cloud server is required for the on-demand MVP. A modern Apple Silicon Mac should process approximately 120-600 sampled frames per request. Exact time depends on model, resolution, camera quality, and whether the feed needs downloading first.

## Scope and non-goals for the MVP

Included:

- A selectable camera catalogue.
- One-click on-demand analysis.
- Vehicle counts by class and direction.
- Representative annotated screenshot.
- Explainable congestion label.
- Optional calibrated speed for selected cameras.

Deferred:

- 24/7 real-time monitoring.
- Automatic number-plate recognition.
- Vehicle identity persistence across cameras.
- Speed measurement from moving or PTZ cameras.
- Full-video archival.

## Delivery plan

1. **Proof of concept:** one saved CCTV clip, vehicle detection, annotated image, and class counts.
2. **Single-camera MVP:** camera configuration, feed/clip acquisition, ByteTrack, directional counting, and results page.
3. **Traffic estimation:** occupancy, queues, camera-specific thresholds, and four-level congestion output.
4. **Calibrated speed:** one-time road calibration workflow for suitable fixed cameras.
5. **Pilot:** validate against manual counts for 3-5 cameras and refine thresholds.

## Suggested technology stack

- Python 3.11+
- FastAPI for a small local API
- Streamlit or a lightweight React frontend for the local interface
- OpenCV for video handling, overlays, and camera geometry
- Ultralytics YOLO or an exported ONNX/Core ML model for inference
- ByteTrack for multi-object tracking
- SQLite for the MVP; PostgreSQL only if multi-user or long-term analytics is needed

## Run locally

```bash
cd traffic_monitoring_request
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Open the local URL printed by Streamlit, choose `demo-intersection`, upload a short CCTV clip, and select **Analyze traffic**. The first analysis downloads the small YOLO model to the local machine; subsequent analyses reuse it.

On Apple Silicon, the analyzer automatically uses the MPS accelerator when macOS makes it available. It otherwise falls back to CPU without changing the user workflow.

For immediate live testing, choose `jogjakota-simpang-mirota-barat`. This is a fixed-view, public HLS feed shown by the official [Kota Yogyakarta CCTV viewer](https://cctv.jogjakota.go.id/), verified on 22 August 2026. The default counting line is only a starting point and must be visually adjusted after the first result. Do not use the source for redistributing footage, and re-check the public portal's access terms before any operational or commercial deployment.

The current MVP uses a compact IoU tracker designed for sampled on-demand video. Replace it with ByteTrack during the multi-camera validation phase if traffic density or occlusions make track continuity insufficient.

## Success criteria

- A user can analyze a configured camera without command-line steps.
- The result appears as a screenshot plus a readable traffic summary.
- Directional counts agree with manual sampling closely enough for operational use; validate per camera before relying on the result.
- The system runs locally with no recurring compute bill.

## Documentation

- [Architecture details](docs/architecture.md)
- [Camera calibration guide](docs/camera-calibration.md)
- [Data, privacy, and feed-access notes](docs/data-governance.md)
