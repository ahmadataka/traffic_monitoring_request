from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CameraConfig:
    id: str
    name: str
    source_url: str | None
    count_line: tuple[int, int, int, int]
    analysis_width: int = 960


def load_cameras(path: Path) -> list[CameraConfig]:
    if not path.exists():
        return []
    raw_cameras = json.loads(path.read_text())
    return [
        CameraConfig(
            id=item["id"],
            name=item["name"],
            source_url=item.get("source_url"),
            count_line=tuple(item["count_line"]),
            analysis_width=item.get("analysis_width", 960),
        )
        for item in raw_cameras
    ]


def save_camera(path: Path, camera: CameraConfig) -> None:
    cameras = {existing.id: existing for existing in load_cameras(path)}
    cameras[camera.id] = camera
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(item) for item in cameras.values()], indent=2) + "\n")
