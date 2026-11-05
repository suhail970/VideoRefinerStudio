"""Small JSON settings store under %LOCALAPPDATA%."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


OUTPUT_DIR_PLACEHOLDER = "Same folder as the source"


def config_dir() -> Path:
    override = os.environ.get("VIDEOREFINER_CONFIG_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "VideoRefinerStudio"
    return Path.home() / ".videorefinerstudio"


@dataclass
class Settings:
    detection_model: str = "lada-yolo-v4"
    threshold: float = 0.35
    max_clip_size: int = 60
    temporal_overlap: int = 10
    denoise: str = "none"
    scene_detection: bool = True
    codec: str = "h264"
    cq: int = 25
    suffix: str = "_restored"
    output_dir: str = ""
    scope: str = "selected"
    recent: list[str] = field(default_factory=list)
    last_dir: str = ""

    @classmethod
    def load(cls) -> "Settings":
        path = config_dir() / "settings.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {item.name for item in fields(cls)}
        data = {key: value for key, value in raw.items() if key in known}
        settings = cls()
        for key, value in data.items():
            current = getattr(settings, key)
            try:
                if isinstance(current, bool):
                    setattr(settings, key, bool(value))
                elif isinstance(current, int):
                    setattr(settings, key, int(value))
                elif isinstance(current, float):
                    setattr(settings, key, float(value))
                elif isinstance(current, list):
                    setattr(settings, key, [str(item) for item in value if isinstance(item, str)])
                else:
                    setattr(settings, key, str(value))
            except (TypeError, ValueError):
                continue
        settings.sanitize()
        return settings

    def sanitize(self) -> None:
        detector = str(self.detection_model).strip().lower()
        self.detection_model = detector or "lada-yolo-v4"
        if self.codec not in {"h264", "hevc", "av1"}:
            self.codec = "h264"
        if self.denoise not in {"none", "low", "medium", "high"}:
            self.denoise = "none"
        if self.scope not in {"selected", "whole"}:
            self.scope = "selected"
        self.threshold = min(0.95, max(0.05, float(self.threshold)))
        self.max_clip_size = min(300, max(12, int(self.max_clip_size)))
        self.temporal_overlap = min(
            40, self.max_clip_size // 2 - 1, max(0, int(self.temporal_overlap))
        )
        self.cq = min(63, max(0, int(self.cq)))
        suffix = self.suffix.strip() or "_restored"
        suffix = "".join(ch for ch in suffix if ch not in '<>:"/\\|?*')
        self.suffix = suffix[:40] or "_restored"
        output_dir = str(self.output_dir).strip()
        if output_dir.casefold() == OUTPUT_DIR_PLACEHOLDER.casefold():
            output_dir = ""
        self.output_dir = output_dir
        self.recent = [item for item in self.recent if item][:8]

    def save(self) -> None:
        self.sanitize()
        directory = config_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / "settings.json"
            temp = target.with_suffix(".tmp")
            temp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            temp.replace(target)
        except OSError:
            pass

    def add_recent(self, path: str | Path) -> None:
        text = str(Path(path))
        self.recent = [text] + [item for item in self.recent if item != text]
        self.recent = self.recent[:8]
        self.last_dir = str(Path(path).parent)
