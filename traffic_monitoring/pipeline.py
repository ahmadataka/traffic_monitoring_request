from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

from traffic_monitoring.config import CameraConfig


VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass(frozen=True)
class AnalysisOptions:
    duration_seconds: int = 180
    sample_fps: int = 1
    confidence: float = 0.35
    model_name: str = "yolo11n.pt"


@dataclass
class Track:
    id: int
    class_name: str
    box: np.ndarray
    center: tuple[int, int]
    previous_center: tuple[int, int] | None = None
    missed_frames: int = 0
    counted: bool = False


class IoUTracker:
    """A compact local tracker for sampled on-demand footage.

    ByteTrack can replace this adapter later without changing the pipeline API.
    """

    def __init__(self, max_missed_frames: int = 3, min_iou: float = 0.2):
        self.max_missed_frames = max_missed_frames
        self.min_iou = min_iou
        self.next_id = 1
        self.tracks: dict[int, Track] = {}

    @staticmethod
    def _iou(left: np.ndarray, right: np.ndarray) -> float:
        x1 = max(left[0], right[0])
        y1 = max(left[1], right[1])
        x2 = min(left[2], right[2])
        y2 = min(left[3], right[3])
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        union = (left[2] - left[0]) * (left[3] - left[1]) + (right[2] - right[0]) * (right[3] - right[1]) - intersection
        return intersection / union if union else 0.0

    def update(self, detections: list[tuple[str, np.ndarray]]) -> list[Track]:
        unmatched_track_ids = set(self.tracks)
        unmatched_detections = set(range(len(detections)))
        candidates: list[tuple[float, int, int]] = []
        for track_id, track in self.tracks.items():
            for index, (class_name, box) in enumerate(detections):
                if class_name == track.class_name:
                    candidates.append((self._iou(track.box, box), track_id, index))

        for score, track_id, index in sorted(candidates, reverse=True):
            if score < self.min_iou or track_id not in unmatched_track_ids or index not in unmatched_detections:
                continue
            track = self.tracks[track_id]
            box = detections[index][1]
            track.previous_center = track.center
            track.box = box
            track.center = _center(box)
            track.missed_frames = 0
            unmatched_track_ids.remove(track_id)
            unmatched_detections.remove(index)

        for track_id in unmatched_track_ids:
            self.tracks[track_id].missed_frames += 1
        self.tracks = {track_id: track for track_id, track in self.tracks.items() if track.missed_frames <= self.max_missed_frames}

        for index in unmatched_detections:
            class_name, box = detections[index]
            self.tracks[self.next_id] = Track(self.next_id, class_name, box, _center(box))
            self.next_id += 1
        return list(self.tracks.values())


@dataclass
class AnalysisResult:
    camera_id: str
    sampled_frames: int
    total_vehicles: int
    directional_crossings: int
    occupancy_percent: float
    traffic_condition: str
    class_counts: dict[str, int]
    annotated_frame: np.ndarray

    @property
    def count_table(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"vehicle_class": name, "count": self.class_counts.get(name, 0)} for name in ("motorcycle", "car", "bus", "truck")]
        )

    def save(self, image_path: Path, json_path: Path) -> None:
        cv2.imwrite(str(image_path), self.annotated_frame)
        payload = asdict(self)
        payload.pop("annotated_frame")
        json_path.write_text(json.dumps(payload, indent=2) + "\n")


def _center(box: np.ndarray) -> tuple[int, int]:
    return (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))


def _line_side(point: tuple[int, int], line: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = line
    return (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)


def _crossed_line(track: Track, line: tuple[int, int, int, int]) -> bool:
    if track.previous_center is None:
        return False
    previous_side = _line_side(track.previous_center, line)
    current_side = _line_side(track.center, line)
    return previous_side * current_side < 0


def _traffic_condition(total: int, occupancy_percent: float, duration_seconds: int) -> str:
    flow_per_minute = total / max(duration_seconds / 60, 1)
    if occupancy_percent >= 65 or flow_per_minute >= 45:
        return "padat"
    if occupancy_percent >= 35 or flow_per_minute >= 20:
        return "sedang"
    return "lancar"


def _resize(frame: np.ndarray, width: int) -> np.ndarray:
    current_height, current_width = frame.shape[:2]
    if current_width == width:
        return frame
    height = int(current_height * width / current_width)
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def analyze_video(source: str | Path, camera: CameraConfig, options: AnalysisOptions) -> AnalysisResult:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open this source. Use an uploaded MP4 or a direct compatible video stream URL.")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 25
    frame_step = max(1, int(source_fps / options.sample_fps))
    maximum_frames = options.duration_seconds * options.sample_fps
    model = YOLO(options.model_name)
    tracker = IoUTracker()
    class_counts: Counter[str] = Counter()
    occupancy_samples: list[float] = []
    sampled_frames = 0
    frame_index = 0
    representative_frame: np.ndarray | None = None
    representative_tracks: list[Track] = []

    while sampled_frames < maximum_frames:
        available, frame = capture.read()
        if not available:
            break
        if frame_index % frame_step != 0:
            frame_index += 1
            continue
        frame_index += 1
        frame = _resize(frame, camera.analysis_width)
        prediction = model(frame, conf=options.confidence, verbose=False)[0]
        detections: list[tuple[str, np.ndarray]] = []
        if prediction.boxes is not None:
            for box, class_id in zip(prediction.boxes.xyxy.cpu().numpy(), prediction.boxes.cls.cpu().numpy().astype(int)):
                if class_id in VEHICLE_CLASSES:
                    detections.append((VEHICLE_CLASSES[class_id], box.astype(int)))

        tracks = tracker.update(detections)
        occupied_area = sum(max(0, track.box[2] - track.box[0]) * max(0, track.box[3] - track.box[1]) for track in tracks)
        occupancy_samples.append(min(100.0, occupied_area / (frame.shape[0] * frame.shape[1]) * 100))
        for track in tracks:
            if not track.counted and _crossed_line(track, camera.count_line):
                track.counted = True
                class_counts[track.class_name] += 1
        sampled_frames += 1
        if representative_frame is None or len(tracks) >= len(representative_tracks):
            representative_frame = frame.copy()
            representative_tracks = [Track(**vars(track)) for track in tracks]

    capture.release()
    if representative_frame is None:
        raise RuntimeError("The source did not provide any frames in the selected analysis window.")

    annotated = representative_frame.copy()
    x1, y1, x2, y2 = camera.count_line
    cv2.line(annotated, (x1, y1), (x2, y2), (0, 200, 255), 3)
    for track in representative_tracks:
        left, top, right, bottom = track.box.astype(int)
        cv2.rectangle(annotated, (left, top), (right, bottom), (0, 220, 0), 2)
        cv2.putText(annotated, f"{track.class_name} #{track.id}", (left, max(20, top - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 2)

    total = sum(class_counts.values())
    occupancy = float(np.mean(occupancy_samples)) if occupancy_samples else 0.0
    return AnalysisResult(
        camera_id=camera.id,
        sampled_frames=sampled_frames,
        total_vehicles=total,
        directional_crossings=total,
        occupancy_percent=occupancy,
        traffic_condition=_traffic_condition(total, occupancy, options.duration_seconds),
        class_counts=dict(class_counts),
        annotated_frame=annotated,
    )
