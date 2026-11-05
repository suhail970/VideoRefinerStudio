"""Small reusable widgets for the light UI."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from .theme import C, S, fmt_time, sans


def card(parent, **kwargs) -> ctk.CTkFrame:
    options = {
        "fg_color": C.SURFACE,
        "corner_radius": S.RADIUS,
        "border_width": 1,
        "border_color": C.BORDER,
    }
    options.update(kwargs)
    return ctk.CTkFrame(parent, **options)


class ScrollArea(ctk.CTkFrame):
    """A vertically scrolling area with a scrollbar that hides when unused."""

    def __init__(self, master, *, fg_color: str = C.BG, **kwargs) -> None:
        super().__init__(master, fg_color=fg_color, corner_radius=0, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            bg=fg_color,
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ctk.CTkScrollbar(
            self,
            orientation="vertical",
            width=10,
            command=self.canvas.yview,
            button_color=C.BORDER_STRONG,
            button_hover_color=C.TEXT_MUTED,
            fg_color="transparent",
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        self.body = ctk.CTkFrame(self.canvas, fg_color="transparent", corner_radius=0)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self._visible = False
        self._after = None
        self._updating = False
        self.min_content_height = 0
        self.scrollbar.grid_remove()
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.body.bind("<Configure>", lambda _event: self._schedule())
        self.canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def set_min_content_height(self, value: int) -> None:
        self.min_content_height = max(0, int(value))
        self._schedule()

    def _on_scroll(self, first: str, last: str) -> None:
        self.scrollbar.set(first, last)

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=max(1, event.width))
        self._schedule()

    def _schedule(self) -> None:
        if self._after is not None:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.after(10, self._update)

    def _update(self) -> None:
        self._after = None
        if self._updating:
            return
        viewport_w = self.canvas.winfo_width()
        viewport_h = self.canvas.winfo_height()
        if viewport_w <= 1 or viewport_h <= 1:
            return
        natural = self.body.winfo_reqheight()
        if self.min_content_height:
            height = max(viewport_h, self.min_content_height)
        else:
            height = max(viewport_h, natural)
        needed = height > viewport_h + 1
        self._updating = True
        try:
            self.canvas.itemconfigure(self._window, width=viewport_w, height=height)
            self.canvas.configure(scrollregion=(0, 0, viewport_w, height))
            if needed:
                if not self._visible:
                    self.scrollbar.grid()
                    self._visible = True
            else:
                if self._visible:
                    self.scrollbar.grid_remove()
                    self._visible = False
                self.canvas.yview_moveto(0)
        finally:
            self._updating = False

    def _on_wheel(self, event) -> None:
        if not self._visible:
            return
        try:
            widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        except Exception:
            return
        if widget is None:
            return
        path = str(widget)
        if path != str(self) and not path.startswith(str(self) + "."):
            return
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


def section_title(parent, title: str, subtitle: str = "", **pack) -> ctk.CTkLabel:
    label = ctk.CTkLabel(
        parent,
        text=title,
        font=sans(14, "bold"),
        text_color=C.TEXT,
        anchor="w",
        justify="left",
    )
    label.pack(anchor="w", **pack)
    if subtitle:
        ctk.CTkLabel(
            parent,
            text=subtitle,
            font=sans(11),
            text_color=C.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=300,
        ).pack(anchor="w", pady=(2, 0))
    return label


def kv(parent, key: str, value: str = "-", **pack) -> tuple[ctk.CTkLabel, ctk.CTkLabel]:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", **pack)
    left = ctk.CTkLabel(row, text=key, font=sans(11), text_color=C.TEXT_MUTED, anchor="w")
    left.pack(side="left")
    right = ctk.CTkLabel(row, text=value, font=sans(11, "bold"), text_color=C.TEXT, anchor="e")
    right.pack(side="right")
    return left, right


class Pill(ctk.CTkLabel):
    def __init__(self, parent, text: str = "", kind: str = "neutral", **kwargs):
        super().__init__(
            parent,
            text=text,
            font=sans(10, "bold"),
            corner_radius=99,
            width=92,
            height=22,
            **kwargs,
        )
        self.set(text, kind)

    def set(self, text: str, kind: str = "neutral") -> None:
        colors = {
            "neutral": (C.SURFACE_ALT, C.TEXT_SECONDARY),
            "accent": (C.ACCENT_SOFT, C.ACCENT),
            "success": (C.SUCCESS_SOFT, C.SUCCESS),
            "warning": (C.WARNING_SOFT, C.WARNING),
            "error": (C.ERROR_SOFT, C.ERROR),
        }
        bg, fg = colors.get(kind, colors["neutral"])
        self.configure(text=text, fg_color=bg, text_color=fg)


class ScanTimeline(tk.Canvas):
    """Score coverage, detected ranges and a playhead, with click-to-seek."""

    def __init__(self, parent, *, on_seek: Callable[[float], None] | None = None, **kwargs):
        options = {
            "bg": C.SURFACE,
            "highlightthickness": 0,
            "bd": 0,
            "height": 96,
            "cursor": "hand2",
        }
        options.update(kwargs)
        super().__init__(parent, **options)
        self.on_seek = on_seek
        self._times: tuple[float, ...] = ()
        self._scores: tuple[float, ...] = ()
        self._threshold = 0.35
        self._duration = 0.0
        self._selected: set[int] = set()
        self._playhead = 0.0
        self._hover = None
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)

    def set_data(
        self,
        *,
        times,
        scores,
        threshold: float,
        selected: set[int],
        playhead: float,
        duration: float,
    ) -> None:
        self._times = tuple(times)
        self._scores = tuple(scores)
        self._threshold = float(threshold)
        self._selected = set(selected)
        self._playhead = float(playhead)
        self._duration = max(0.001, float(duration))
        self._draw()

    def set_selected(self, selected: set[int]) -> None:
        self._selected = set(selected)
        self._draw()

    def set_playhead(self, seconds: float) -> None:
        self._playhead = float(seconds)
        self._draw()

    def _plot_box(self):
        return 14, 22, max(30, self.winfo_width() - 14), max(24, self.winfo_height() - 16)

    def _draw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2:
            return
        x0, y0, x1, y1 = self._plot_box()
        self.create_line(x0, y1, x1, y1, fill=C.BORDER, width=1)
        if not self._times:
            self.create_text(
                x0,
                (y0 + y1) / 2,
                text="Run a mosaic scan to build the detection timeline.",
                anchor="w",
                font=sans(11),
                fill=C.TEXT_MUTED,
            )
            return
        duration = self._duration
        span = max(0.001, duration)
        plot_h = max(8, y1 - y0 - 8)
        count = len(self._times)
        step = max(1.5, (x1 - x0) / max(1, count))
        bar_w = max(1.0, min(6.0, step * 0.72))
        for index, (stamp, score) in enumerate(zip(self._times, self._scores)):
            x = x0 + (stamp / span) * (x1 - x0)
            height = max(1.0, min(1.0, float(score)) * plot_h)
            y_top = y1 - 5 - height
            hit = score >= self._threshold
            color = C.ACCENT if hit else "#D7DAE4"
            if index in self._selected:
                color = C.ACCENT
            self.create_rectangle(x, y_top, x + bar_w, y1 - 5, fill=color, outline="")
        # detected bands, one per contiguous above-threshold run
        run_start = None
        for index, (stamp, score) in enumerate(zip(self._times, self._scores)):
            above = score >= self._threshold
            if above and run_start is None:
                run_start = stamp
            if (not above or index == count - 1) and run_start is not None:
                end_stamp = stamp if not above else min(span, stamp + self._times[1] - self._times[0] if count > 1 else stamp)
                x_a = x0 + (run_start / span) * (x1 - x0)
                x_b = x0 + (end_stamp / span) * (x1 - x0)
                self.create_rectangle(x_a, y1, max(x_a + 1, x_b), y1 + 3, fill=C.ACCENT_BORDER, outline="")
                run_start = None
        # playhead
        px = x0 + (max(0.0, min(span, self._playhead)) / span) * (x1 - x0)
        self.create_line(px, 4, px, y1 + 6, fill=C.ACCENT, width=2)
        self.create_oval(px - 3, 1, px + 3, 7, fill=C.ACCENT, outline="")
        # labels
        self.create_text(x0, 6, text="0:00", anchor="w", font=sans(9), fill=C.TEXT_MUTED)
        self.create_text(
            x1,
            6,
            text=fmt_time(duration, tenths=False),
            anchor="e",
            font=sans(9),
            fill=C.TEXT_MUTED,
        )
        if self._hover is not None:
            seconds, x = self._hover
            label = fmt_time(seconds)
            self.create_line(x, y0 - 2, x, y1 + 4, fill=C.BORDER_STRONG, dash=(2, 3))
            self.create_text(
                min(max(x, x0 + 30), x1 - 30),
                11,
                text=label,
                font=sans(9),
                fill=C.TEXT_SECONDARY,
            )

    def _click(self, event) -> None:
        if not self._times or self.on_seek is None:
            return
        x0, _y0, x1, _y1 = self._plot_box()
        fraction = (event.x - x0) / max(1, x1 - x0)
        self.on_seek(max(0.0, min(1.0, fraction)) * self._duration)

    def _motion(self, event) -> None:
        if not self._times:
            return
        x0, _y0, x1, _y1 = self._plot_box()
        fraction = max(0.0, min(1.0, (event.x - x0) / max(1, x1 - x0)))
        self._hover = (fraction * self._duration, event.x)
        self._draw()

    def _leave(self, _event=None) -> None:
        if self._hover is not None:
            self._hover = None
            self._draw()
