# Architecture

## Design principle

This is a request-driven system. Compute is consumed only after the user requests an analysis, then released when the result is ready.

## Request lifecycle

1. Validate that the camera source is configured and approved.
2. Fetch or receive a short analysis window (default: 180 seconds).
3. Decode and sample frames at 1 FPS by default.
4. Crop to the configured road region to reduce inference cost and false detections.
5. Run vehicle detection and ByteTrack tracking.
6. Convert track trajectories into line-crossing and occupancy events.
7. Calculate aggregates and, when calibrated, speed in km/h.
8. Select a clear representative frame and draw detections, tracks, road ROI, and count lines.
9. Store a result record, annotated image, and optional short-lived debug artefacts.

## Output contract

```json
{
  "camera_id": "jogja-example-01",
  "analysis_started_at": "2026-08-22T10:00:00+07:00",
  "analysis_duration_seconds": 180,
  "traffic_condition": "padat",
  "counts": {
    "motorcycle": 112,
    "car": 58,
    "bus": 4,
    "truck": 12
  },
  "directional_counts": {
    "northbound": 103,
    "southbound": 83
  },
  "road_occupancy_percent": 68,
  "average_speed_kmh": 22.0,
  "speed_available": true,
  "annotated_image_path": "results/jogja-example-01/2026-08-22T100000+0700.jpg"
}
```

`average_speed_kmh` must be `null` when the camera lacks valid calibration.

## Efficiency controls

- Default to 1 FPS. Increase only for fast traffic or a camera with frequent occlusion.
- Downscale before inference when vehicle detail remains adequate.
- Use a road ROI and exclude sidewalks, sky, and parked areas.
- Run a nano detector at fixed input resolution.
- Persist numerical results, not raw CCTV video.
- Delete temporary video segments after successful analysis unless explicitly retained for validation.

