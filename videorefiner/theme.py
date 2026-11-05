"""Light theme tokens and small styling helpers."""

from __future__ import annotations

import tkinter.font as tkfont


class C:
    BG = "#F4F5F8"
    SURFACE = "#FFFFFF"
    SURFACE_ALT = "#FAFBFD"
    SIDEBAR = "#FBFBFE"
    BORDER = "#E5E7EF"
    BORDER_STRONG = "#D6D9E4"

    TEXT = "#171A23"
    TEXT_SECONDARY = "#5B6172"
    TEXT_MUTED = "#8A90A2"

    ACCENT = "#4F46E5"
    ACCENT_HOVER = "#4338CA"
    ACCENT_SOFT = "#EEF0FF"
    ACCENT_SOFT_HOVER = "#E3E6FF"
    ACCENT_BORDER = "#C7CBFB"

    SUCCESS = "#047857"
    SUCCESS_SOFT = "#ECFDF5"
    WARNING = "#B45309"
    WARNING_SOFT = "#FFFBEB"
    ERROR = "#B91C1C"
    ERROR_SOFT = "#FEF2F2"

    PREVIEW_BG = "#11131A"
    PREVIEW_MUTED = "#6B7280"


class S:
    RADIUS = 12
    RADIUS_SMALL = 8
    PAD = 18
    PAD_SMALL = 10
    SIDEBAR_WIDTH = 232
    SETTINGS_WIDTH = 360


_FONT_SANS = "Segoe UI"
_FONT_MONO = "Consolas"


def init_fonts() -> None:
    """Pick fonts that exist on this machine."""
    global _FONT_SANS, _FONT_MONO
    try:
        families = set(tkfont.families())
    except Exception:
        return
    for candidate in ("Segoe UI", "Inter", "Arial", "Segoe UI Variable Text"):
        if candidate in families:
            _FONT_SANS = candidate
            break
    for candidate in ("Cascadia Mono", "Consolas", "Courier New"):
        if candidate in families:
            _FONT_MONO = candidate
            break


def sans(size: int = 13, weight: str = "normal") -> tuple[str, int, str]:
    return (_FONT_SANS, size, weight)


def mono(size: int = 12) -> tuple[str, int, str]:
    return (_FONT_MONO, size, "normal")


def fmt_time(seconds: float, tenths: bool = True) -> str:
    seconds = max(0.0, float(seconds))
    total = seconds
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:05.2f}" if tenths else f"{hours}:{minutes:02d}:{int(secs):02d}"
    if tenths:
        return f"{minutes}:{secs:04.1f}"
    return f"{minutes}:{int(secs):02d}"


def fmt_bytes(value: int) -> str:
    value = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"
