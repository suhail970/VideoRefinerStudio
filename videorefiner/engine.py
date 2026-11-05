"""Background workers that wrap the Jasna detection and restoration engine."""

from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from .settings import Settings

LOGGER = logging.getLogger("videorefiner.engine")


def _put(events: queue.Queue, item: tuple) -> None:
    try:
        events.put_nowait(item)
    except queue.Full:
        try:
            events.get_nowait()
        except queue.Empty:
            pass
        try:
            events.put_nowait(item)
        except queue.Full:
            pass


class _QueueLogHandler(logging.Handler):
    def __init__(self, events: queue.Queue) -> None:
        super().__init__(level=logging.INFO)
        self.events = events

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        if record.exc_info:
            message += "\n" + "".join(traceback.format_exception(*record.exc_info))
        _put(self.events, ("log", record.levelname, message))


class _LogCapture:
    def __init__(self, events: queue.Queue) -> None:
        self.handler = _QueueLogHandler(events)
        self.logger = logging.getLogger("jasna")
        self.old_level = self.logger.level
        self.old_propagate = self.logger.propagate

    def __enter__(self) -> "_LogCapture":
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.logger.propagate = False
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.logger.removeHandler(self.handler)
        self.logger.setLevel(self.old_level)
        self.logger.propagate = self.old_propagate


def _device():
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available. Install the NVIDIA build of PyTorch and update the GPU driver."
        )
    return torch.device("cuda:0")


def _decode_backend() -> None:
    os.environ.setdefault("JASNA_DECODE_BACKEND", "pyav-hw")


def _gib(value: float) -> str:
    return f"{value / 1024**3:.1f} GiB"


def _model_dir() -> Path:
    from jasna.engine_paths import model_weights_dir

    return model_weights_dir()


def _resolve_detector(name: str, threshold: float | None):
    from jasna.mosaic.detection_registry import resolve_detection_model

    return resolve_detection_model(name, "", threshold)


def _session_config(
    *,
    video: Path,
    settings: Settings,
    detection_name: str,
    detection_threshold: float,
    codec: str,
):
    from jasna.engine_paths import default_restoration_model_path
    from jasna.media.encoder_settings import encoder_cq_spec
    from jasna.session_config import SessionConfig

    from jasna.accelerator import vendor_for_device

    det_name, det_path, _ = _resolve_detector(detection_name, detection_threshold)
    restoration_path = default_restoration_model_path("basicvsrpp")
    if not restoration_path.is_file():
        restoration_path = _model_dir() / "lada_mosaic_restoration_model_generic_v1.2.pth"
    if not restoration_path.is_file():
        raise FileNotFoundError(
            f"Restoration model not found: {restoration_path}. "
            "Run scripts/download_models.py or place the weight in model_weights/."
        )
    vendor = vendor_for_device("cuda:0")
    spec = encoder_cq_spec(codec, vendor)
    cq = max(spec.minimum, min(spec.maximum, int(settings.cq)))
    overlap = min(max(0, int(settings.temporal_overlap)), max(0, int(settings.max_clip_size) // 2 - 1))
    return SessionConfig(
        device="cuda:0",
        fp16=True,
        batch_size=4,
        detection_model_name=det_name,
        detection_model_path=det_path,
        detection_score_threshold=float(detection_threshold),
        max_detection_gap=2,
        min_detection_duration=2,
        scene_detection=bool(settings.scene_detection),
        restoration_model_name="basicvsrpp",
        restoration_model_path=restoration_path,
        ltx_large_canvas=False,
        ltx_window_hop=8,
        ltx_seed=20260923,
        ltx_fast=False,
        ltx_model="distilled2",
        ltx_trial=False,
        ltx_auto_split_percent=None,
        compile_basicvsrpp=False,
        max_clip_size=int(settings.max_clip_size),
        temporal_overlap=overlap,
        enable_crossfade=True,
        denoise_strength=settings.denoise,
        denoise_step="after_primary",
        secondary_restoration="none",
        tvai_ffmpeg_path="",
        tvai_model="",
        tvai_scale=2,
        tvai_args="",
        tvai_workers=1,
        tvai_denoise=False,
        rtx_scale=2,
        rtx_quality="medium",
        rtx_denoise="none",
        rtx_deblur="none",
        vr_mode="auto",
        vr_projection="auto",
        codec=codec,
        encoder_settings={"cq": cq},
        lut_path=None,
        sharpen_strength=0.0,
        retarget_high_fps=False,
        fmp4=False,
        disable_progress=True,
        working_dir=None,
    )


@dataclass(frozen=True)
class ScanResult:
    times: tuple[float, ...]
    scores: tuple[float, ...]
    sizes: tuple[float, ...]
    stride: float
    duration: float


def segments_for_scan(
    scan: ScanResult, threshold: float, *, pad: float | None = None
):
    from jasna.mosaic_scan import segments_from_scores

    return segments_from_scores(
        scan.times,
        scan.scores,
        threshold=float(threshold),
        stride=max(0.01, scan.stride),
        duration=scan.duration,
        pad=pad,
    )


class ScanWorker(threading.Thread):
    def __init__(
        self,
        video: Path,
        settings: Settings,
        events: queue.Queue,
        *,
        sample_seconds: float = 1.0,
    ) -> None:
        super().__init__(name="VideoRefinerScan", daemon=True)
        self.video = Path(video)
        self.settings = settings
        self.events = events
        self.sample_seconds = max(0.25, float(sample_seconds))
        self._cancel = threading.Event()
        self._detector = None

    def cancel(self) -> None:
        self._cancel.set()

    def _log(self, message: str) -> None:
        _put(self.events, ("log", "INFO", message))

    def run(self) -> None:
        _decode_backend()
        started = time.monotonic()
        try:
            _put(self.events, ("status", "Loading detector", "Preparing the mosaic detector"))
            from jasna.media.probe import get_video_meta_data
            from jasna.mosaic.detection_registry import DEFAULT_DETECTION_MODEL_NAME
            from jasna.mosaic_scan import SCAN_MASK_HW, mosaic_sizes, scan_sample_stride
            from jasna.session_factory import build_compiled_detection_model

            try:
                from jasna.media.video_decoder import VideoReader
            except ImportError as exc:
                raise RuntimeError(f"The Jasna video decoder is unavailable: {exc}") from exc

            device = _device()
            meta = get_video_meta_data(str(self.video))
            if meta.duration <= 0 and meta.num_frames <= 0:
                raise RuntimeError("The video has no readable duration.")
            name = self.settings.detection_model or DEFAULT_DETECTION_MODEL_NAME
            det_name, det_path, det_threshold = _resolve_detector(name, None)
            with _LogCapture(self.events):
                self._detector = build_compiled_detection_model(
                    det_name,
                    det_path,
                    device=device,
                    batch_size=4,
                    fp16=True,
                    score_threshold=det_threshold,
                    log_callback=self._log,
                )
                if self._cancel.is_set():
                    _put(self.events, ("scan_canceled",))
                    return
                _put(
                    self.events,
                    ("status", "Scanning mosaics", "Sampling one frame per second"),
                )
                stride_frames = scan_sample_stride(meta.video_fps, seconds=self.sample_seconds)
                stride_seconds = stride_frames / float(meta.video_fps)
                total = max(1, int(meta.num_frames) // stride_frames)
                times: list[float] = []
                scores: list[float] = []
                sizes: list[float] = []
                import torch

                reader = VideoReader(
                    str(self.video), 4, device, meta, frame_stride=stride_frames
                )
                with reader:
                    for batch, pts in reader.frames():
                        if self._cancel.is_set():
                            break
                        count = len(pts)
                        if count == 0:
                            continue
                        if batch.shape[0] < 4:
                            batch = torch.cat(
                                (batch, batch[-1:].expand(4 - batch.shape[0], -1, -1, -1))
                            )
                        batch_scores, batch_masks = self._detector.scan_scores_masks(
                            batch, mask_hw=SCAN_MASK_HW
                        )
                        times.extend(
                            max(0.0, (pts_item - reader.start_pts) * float(meta.time_base))
                            for pts_item in pts
                        )
                        scores.extend(batch_scores[:count].tolist())
                        sizes.extend(
                            mosaic_sizes(
                                batch_masks[:count].to(torch.uint8).cpu().numpy(),
                                frame_width=int(meta.video_width),
                                frame_height=int(meta.video_height),
                            )
                        )
                        done = len(times)
                        elapsed = max(0.001, time.monotonic() - started)
                        rate = done / elapsed
                        eta = (total - done) / rate if rate > 0 and done < total else 0.0
                        _put(
                            self.events,
                            (
                                "scan_progress",
                                min(1.0, done / max(1, total)),
                                done,
                                total,
                                max(0.0, eta),
                            ),
                        )
            if self._cancel.is_set():
                _put(self.events, ("scan_canceled",))
                return
            if not times:
                raise RuntimeError("No frames could be sampled from this video.")
            result = ScanResult(
                times=tuple(times),
                scores=tuple(scores),
                sizes=tuple(sizes),
                stride=stride_seconds,
                duration=max(float(meta.duration), float(times[-1]) + stride_seconds),
            )
            _put(
                self.events,
                (
                    "scan_done",
                    result,
                    {
                        "width": meta.video_width,
                        "height": meta.video_height,
                        "fps": meta.video_fps,
                        "duration": meta.duration,
                        "frames": meta.num_frames,
                        "codec": meta.codec_name,
                    },
                ),
            )
        except Exception as exc:  # noqa: BLE001 - shown in the UI and log
            LOGGER.exception("Mosaic scan failed")
            _put(self.events, ("scan_error", friendly_error(exc)))
        finally:
            if self._detector is not None:
                try:
                    self._detector.close()
                except Exception:
                    pass
                self._detector = None


class RestoreWorker(threading.Thread):
    def __init__(
        self,
        video: Path,
        settings: Settings,
        events: queue.Queue,
        *,
        output_path: Path,
        segments,
        scope: str,
    ) -> None:
        super().__init__(name="VideoRefinerRestore", daemon=True)
        self.video = Path(video)
        self.settings = settings
        self.events = events
        self.output_path = Path(output_path)
        self.segments = tuple(segments) if segments else None
        self.scope = scope
        self._cancel = threading.Event()
        self._pipeline = None
        self._session = None
        self._last_emit = 0.0
        self._last_percent = -1.0
        self._elapsed = 0.0

    def cancel(self) -> None:
        self._cancel.set()
        pipeline = self._pipeline
        if pipeline is not None:
            try:
                pipeline.cancel()
            except Exception:
                pass

    def _remove_partial(self, output_preexisting: bool) -> None:
        if output_preexisting:
            return
        try:
            if self.output_path.is_file():
                self.output_path.unlink()
        except OSError:
            pass

    def _log(self, message: str) -> None:
        _put(self.events, ("log", "INFO", message))

    def _status(self, title: str, detail: str = "") -> None:
        _put(self.events, ("status", title, detail))

    def _progress(self, percent, fps, eta, done, total, stage) -> None:
        now = time.monotonic()
        if now - self._last_emit < 0.12 and percent < 100:
            return
        if abs(float(percent) - self._last_percent) < 0.05 and percent < 100:
            return
        self._last_emit = now
        self._last_percent = float(percent)
        _put(
            self.events,
            (
                "restore_progress",
                float(percent),
                float(fps or 0.0),
                max(0.0, float(eta or 0.0)),
                int(done or 0),
                int(total or 0),
                stage,
            ),
        )

    def run(self) -> None:
        _decode_backend()
        started = time.monotonic()
        output_preexisting = self.output_path.exists()
        try:
            import torch

            from jasna.media.probe import get_video_meta_data
            from jasna.session_factory import build_pipeline, build_restoration_session

            device = _device()
            torch.cuda.empty_cache()
            free, total_mem = torch.cuda.mem_get_info()
            if free < 0.9 * 1024**3:
                raise RuntimeError(
                    f"Only {_gib(free)} of GPU memory is free. Close other GPU apps and try again."
                )
            if free < 1.8 * 1024**3:
                self._log(
                    f"Low free VRAM ({_gib(free)} of {_gib(total_mem)}); "
                    "the job may fall back to a smaller clip size."
                )
            meta = get_video_meta_data(str(self.video))
            codec = str(self.settings.codec).lower()
            if self.scope == "selected":
                source_codec = str(meta.codec_name).lower()
                if source_codec not in {"h264", "hevc", "av1"}:
                    raise RuntimeError(
                        "Selected-range smart rendering needs an H.264, HEVC, or AV1 source "
                        f"(this file uses {source_codec or 'an unknown codec'}). "
                        "Choose whole-video scope to transcode it."
                    )
                if source_codec != codec:
                    self._log(
                        f"Selected ranges keep the source codec ({source_codec.upper()}); "
                        f"the chosen {codec.upper()} codec applies to whole-video exports."
                    )
                codec = source_codec
            config = _session_config(
                video=self.video,
                settings=self.settings,
                detection_name=self.settings.detection_model,
                detection_threshold=self.settings.threshold,
                codec=codec,
            )
            if not self.output_path.parent.is_dir():
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
            det_name, det_path, _ = _resolve_detector(config.detection_model_name, config.detection_score_threshold)
            from jasna.engine_compiler import EngineCompilationRequest, ensure_engines_compiled

            self._status("Preparing detector", "Compiling or loading the TensorRT detector")
            ensure_engines_compiled(
                EngineCompilationRequest(
                    device=str(device),
                    fp16=True,
                    detection=True,
                    detection_model_name=det_name,
                    detection_model_path=str(det_path),
                    detection_batch_size=4,
                ),
                log_callback=self._log,
            )
            if self._cancel.is_set():
                _put(self.events, ("restore_canceled", self.output_path))
                return
            mode = "selected ranges" if self.scope == "selected" else "whole video"
            self._log(f"Input: {self.video}")
            self._log(f"Output: {self.output_path}")
            self._log(f"Scope: {mode}; codec: {codec.upper()}; CQ: {config.encoder_settings.get('cq')}")
            self._status("Preparing models", "Loading the detector and BasicVSR++")
            with _LogCapture(self.events):
                self._session = build_restoration_session(config, log_callback=self._log)
                if self._cancel.is_set():
                    _put(self.events, ("restore_canceled", self.output_path))
                    return
                self._status("Restoring frames", "Running the mosaic restoration pipeline")
                self._pipeline = build_pipeline(
                    config,
                    self._session,
                    self.video,
                    self.output_path,
                    progress_callback=self._progress,
                    segments=self.segments if self.scope == "selected" else None,
                )
                self._pipeline.run()
                if not self._pipeline.completed or self._cancel.is_set():
                    self._remove_partial(output_preexisting)
                    _put(self.events, ("restore_canceled", self.output_path))
                    return
            self._elapsed = time.monotonic() - started
            if not self.output_path.is_file() or self.output_path.stat().st_size <= 0:
                raise RuntimeError("The pipeline finished but no output file was written.")
            _put(
                self.events,
                (
                    "restore_done",
                    self.output_path,
                    self._elapsed,
                    self.scope,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - shown in the UI and log
            LOGGER.exception("Restoration failed")
            canceled = self._cancel.is_set()
            self._remove_partial(output_preexisting)
            if canceled:
                _put(self.events, ("restore_canceled", self.output_path))
            else:
                _put(self.events, ("restore_error", friendly_error(exc), traceback.format_exc()))
        finally:
            if self._session is not None:
                try:
                    self._session.close()
                except Exception:
                    pass
                self._session = None
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass


def friendly_error(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    if isinstance(exc, MemoryError) or "out of memory" in lowered or "cuda error: out of memory" in lowered:
        return (
            "The GPU ran out of memory. Lower the max clip size (for example 30), "
            "close other GPU applications, and try again."
        )
    if isinstance(exc, FileNotFoundError):
        return text
    if "no module named 'tensorrt'" in lowered:
        return "TensorRT is not installed in this environment. Run the setup command from README.md."
    if "nvenc" in lowered and "not" in lowered:
        return f"The NVIDIA encoder could not start: {text}"
    return text


def build_output_path(
    video: Path,
    settings: Settings,
    *,
    scope: str,
) -> Path:
    video = Path(video)
    folder_text = (settings.output_dir or "").strip()
    folder = Path(folder_text).expanduser() if folder_text else video.parent
    if not folder.is_absolute():
        folder = video.parent / folder
    folder.mkdir(parents=True, exist_ok=True)
    ext = video.suffix if scope == "selected" and video.suffix else ".mp4"
    base = f"{video.stem}{settings.suffix}"
    try:
        from jasna.media.media_files import unique_path

        return unique_path(folder / f"{base}{ext}")
    except Exception:
        candidate = folder / f"{base}{ext}"
        counter = 1
        while candidate.exists():
            candidate = folder / f"{base} ({counter}){ext}"
            counter += 1
        return candidate


def environment_report() -> dict:
    report: dict = {
        "rows": [],
        "errors": [],
        "gpu": "Not detected",
        "gpu_detail": "",
        "torch": "",
        "tensorrt": "",
        "ffmpeg": "",
        "models": [],
        "detectors": [],
        "vlc": "",
    }

    def row(label: str, value: str, status: str = "ok") -> None:
        report["rows"].append({"label": label, "value": value, "status": status})

    report["torch"] = "not installed"
    try:
        import torch

        report["torch"] = torch.__version__
        row("PyTorch", torch.__version__, "ok")
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            free, total = torch.cuda.mem_get_info()
            report["gpu"] = name
            report["gpu_detail"] = (
                f"Compute {props.major}.{props.minor} · {_gib(total)} VRAM · {_gib(free)} free"
            )
            row("GPU", name, "ok")
            row("CUDA runtime", str(torch.version.cuda), "ok")
            row("GPU memory", f"{_gib(free)} free of {_gib(total)}", "ok")
        else:
            report["errors"].append("CUDA is not available in this PyTorch build.")
            row("GPU", "CUDA unavailable", "error")
    except Exception as exc:
        report["errors"].append(f"PyTorch: {exc}")
        row("PyTorch", str(exc), "error")

    try:
        import tensorrt

        report["tensorrt"] = tensorrt.__version__
        row("TensorRT", tensorrt.__version__, "ok")
    except Exception as exc:
        report["tensorrt"] = "not installed"
        row("TensorRT", str(exc), "warn")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        try:
            version = subprocess.run(
                [ffmpeg, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.splitlines()[0]
        except Exception:
            version = ffmpeg
        report["ffmpeg"] = version
        row("FFmpeg", version, "ok")
    else:
        report["errors"].append("FFmpeg and ffprobe must be installed and on PATH.")
        row("FFmpeg", "not found on PATH", "error")

    model_dir = _model_dir()
    expected = [
        ("lada_mosaic_detection_model_v4_fast.pt", "YOLO detector"),
        ("lada_mosaic_restoration_model_generic_v1.2.pth", "BasicVSR++ model"),
    ]
    for filename, label in expected:
        path = model_dir / filename
        if path.is_file():
            report["models"].append({"name": label, "path": str(path), "status": "ok"})
            row(label, f"{path.name} · {path.stat().st_size / 1024**2:.0f} MB", "ok")
        else:
            report["models"].append({"name": label, "path": str(path), "status": "error"})
            report["errors"].append(f"Missing model: {path}")
            row(label, "missing", "error")

    try:
        from jasna.mosaic.detection_registry import discover_available_detection_models

        report["detectors"] = discover_available_detection_models(model_dir)
        row(
            "Detectors",
            ", ".join(report["detectors"]) if report["detectors"] else "none",
            "ok" if report["detectors"] else "error",
        )
        if not report["detectors"]:
            report["errors"].append("No mosaic detector weights were found in model_weights/.")
    except Exception as exc:
        row("Detectors", str(exc), "error")

    try:
        import vlc  # noqa: F401

        from vlc import get_default_instance  # noqa: F401

        report["vlc"] = "python-vlc available"
        row("VLC (optional)", "python-vlc available", "ok")
    except Exception:
        vlc_exe = shutil.which("vlc") or str(Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe"))
        if Path(vlc_exe).is_file():
            report["vlc"] = vlc_exe
            row("VLC (optional)", "installed; preview uses the built-in decoder", "ok")
        else:
            report["vlc"] = ""
            row("VLC (optional)", "not installed", "warn")

    return report
