# Data, Privacy, and Feed Access

## Source access

The project must use only feeds that are publicly viewable or explicitly authorized for this use. Some government CCTV portals provide a live public viewer while restricting recorded footage or reuse. Treat each source independently and retain the source URL, access terms, and permission status in the camera catalogue.

### Verified pilot source

The official Kota Yogyakarta viewer at `https://cctv.jogjakota.go.id/` publicly provides HLS playback for camera records marked `cctv_status: 0`. On 22 August 2026, the fixed-view `Simpang Mirota V. Barat (FIX)` stream was verified as readable by OpenCV through the public viewer's own displayed playlist. It is configured as the initial live pilot source in `config/cameras.json`.

DIY ATCS recordings are not freely accessible according to the official ATCS page. The software must not circumvent access controls, scrape protected recordings, or retain content beyond any authorization.

## Data minimization

- Retain aggregate counts and traffic indicators by default.
- Generate a single annotated evidence image per user request when needed.
- Delete temporary video frames and downloaded segments automatically after completion.
- Do not perform number-plate recognition or face recognition.
- Restrict local result access to the operator account.

## Quality and transparency

Every result should expose its analysis duration, sample rate, traffic-state rule, calibration availability, and confidence caveats. Camera views, weather, nighttime glare, occlusion, and unusual events can reduce accuracy.
