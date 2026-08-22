# Camera Calibration

Speed cannot be inferred reliably from raw image pixels alone because perspective changes scale across the frame. Calibration is therefore optional and camera-specific.

## Eligible cameras

- Fixed viewpoint and stable zoom.
- Road surface visible over a useful distance.
- At least four identifiable road points with measurable real-world coordinates.
- No significant camera movement during analysis.

## One-time procedure

1. Capture a representative frame.
2. Mark four or more points on the road plane.
3. Measure their real-world positions using surveyed references, maps, or on-site measurement.
4. Compute a homography from image coordinates to ground-plane metres.
5. Validate estimated speeds with manual observations or a known-speed reference.
6. Store the calibration with the camera configuration and repeat it after any camera repositioning.

## Formula

For a tracked vehicle, project its ground-contact point from image coordinates to the road plane. Then calculate:

```text
speed_kmh = distance_metres / elapsed_seconds * 3.6
```

Smooth trajectories before calculating speed to reduce bounding-box jitter. Report a robust value such as the median speed of valid tracks, rather than the raw mean of all detections.

