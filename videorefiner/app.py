"""VideoRefiner Studio desktop application."""

from __future__ import annotations

import copy
import logging
import os
import queue
import subprocess
import threading
import time
import traceback
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import ImageTk

from . import __version__, engine, media
from .settings import OUTPUT_DIR_PLACEHOLDER, Settings
from .theme import C, S, fmt_bytes, fmt_time, init_fonts, mono, sans
from .widgets import Pill, ScanTimeline, ScrollArea, card, section_title

LOGGER = logging.getLogger("videorefiner.app")

JASNA_URL = "https://github.com/Kruk2/jasna"
AGPL_URL = "https://www.gnu.org/licenses/agpl-3.0.html"
LADA_URL = "https://codeberg.org/ladaapp/lada"
RF_DETR_URL = "https://github.com/roboflow/rf-detr"

VIDEO_TYPES = [
    ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.mts *.flv *.wmv"),
    ("All files", "*.*"),
]


class VideoRefinerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        init_fonts()
        ctk.set_appearance_mode("light")
        self.title("VideoRefiner Studio")
        self.configure(fg_color=C.BG)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self._center_window(1440, 920)

        self.settings = Settings.load()
        self.queue: queue.Queue = queue.Queue(maxsize=2500)
        self.media: media.MediaInfo | None = None
        self.scan: engine.ScanResult | None = None
        self.scan_segments = ()
        self.selected_ranges: set[int] = set()
        self.output_path: Path | None = None
        self.current_time = 0.0
        self.compare = False
        self.compare_mode = "side"
        self.wipe = 0.5
        self._playing = False
        self._playback: media.PlaybackSession | None = None
        self._last_play_time = 0.0
        self._photo = None
        self._static_gen = 0
        self._static_after = None
        self._seek_after = None
        self._wipe_after = None
        self._resize_after = None
        self._resume_after_seek = False
        self._suppress_slider = False
        self._scan_worker: engine.ScanWorker | None = None
        self._restore_worker: engine.RestoreWorker | None = None
        self._env_worker: threading.Thread | None = None
        self._env: dict | None = None
        self._scan_detector = ""
        self._log_lines: list[tuple[str, str, str]] = []
        self._log_window = None
        self._log_text = None
        self._settings_after = None
        self._toast_after = None
        self._view = "import"
        self._range_checks: list[tuple[tk.BooleanVar, int]] = []
        self._settings_widgets: list = []

        self._build_sidebar()
        self._build_main()
        self._build_import_view()
        self._build_workspace()
        self._build_settings_panel()
        self._build_system_view()
        self._build_about_view()
        self._show_view("import")
        self._refresh_recent()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._poll)
        self.after(150, self._run_env_check)
        self._append_log("INFO", f"VideoRefiner Studio {__version__} started")

    def _work_area(self) -> tuple[int, int, int, int]:
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
        return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def _center_window(self, width: int, height: int) -> None:
        scale = self._get_window_scaling() or 1.0
        left, top, right, bottom = self._work_area()
        work_w = int((right - left) / scale)
        work_h = int((bottom - top) / scale)
        work_x = int(left / scale)
        work_y = int(top / scale)
        min_w = min(1120, max(920, work_w - 24))
        min_h = min(740, max(540, work_h - 24))
        width = max(min_w, min(width, work_w - 24))
        height = max(min_h, min(height, work_h - 24))
        x = work_x + max(0, (work_w - width) // 2)
        y = work_y + max(0, (work_h - height) // 2)
        self.minsize(min_w, min_h)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------ layout

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(
            self,
            width=S.SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=C.SIDEBAR,
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar = sidebar

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 18))
        logo = tk.Canvas(brand, width=38, height=38, bg=C.SIDEBAR, highlightthickness=0)
        logo.pack(side="left")
        logo.create_polygon(
            8,
            2,
            30,
            2,
            36,
            8,
            36,
            30,
            30,
            36,
            8,
            36,
            2,
            30,
            2,
            8,
            smooth=True,
            fill=C.ACCENT,
        )
        logo.create_text(19, 19, text="VR", fill="#FFFFFF", font=sans(12, "bold"))
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(
            brand_text,
            text="VideoRefiner",
            font=sans(15, "bold"),
            text_color=C.TEXT,
            anchor="w",
            height=18,
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand_text,
            text="STUDIO",
            font=sans(9, "bold"),
            text_color=C.TEXT_MUTED,
            anchor="w",
            height=12,
        ).pack(anchor="w")

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=10)
        nav.grid_columnconfigure(0, weight=1)
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        items = [
            ("import", "Import", "1"),
            ("workspace", "Workspace", "2"),
            ("compare", "Compare", "3"),
            ("system", "System", "4"),
            ("about", "About", "5"),
        ]
        for row, (key, label, number) in enumerate(items):
            button = ctk.CTkButton(
                nav,
                text=f"  {label}",
                anchor="w",
                height=38,
                corner_radius=8,
                border_spacing=8,
                fg_color="transparent",
                hover_color=C.ACCENT_SOFT_HOVER,
                text_color=C.TEXT_SECONDARY,
                font=sans(13),
                command=lambda k=key: self._show_view(k),
            )
            button.grid(row=row, column=0, sticky="ew", pady=1)
            self._nav_buttons[key] = button

        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=14, pady=(10, 16))
        gpu = ctk.CTkFrame(
            bottom,
            fg_color=C.SURFACE,
            corner_radius=10,
            border_width=1,
            border_color=C.BORDER,
            cursor="hand2",
        )
        gpu.pack(fill="x")
        gpu.bind("<Button-1>", lambda _e: self._show_view("system"))
        top = ctk.CTkFrame(gpu, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        self._gpu_dot = tk.Canvas(top, width=8, height=8, bg=C.SURFACE, highlightthickness=0)
        self._gpu_dot.pack(side="left", pady=(5, 0))
        self._gpu_dot_id = self._gpu_dot.create_oval(1, 1, 7, 7, fill=C.TEXT_MUTED, outline="")
        ctk.CTkLabel(
            top,
            text="LOCAL GPU",
            font=sans(9, "bold"),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).pack(side="left", padx=(6, 0))
        self._gpu_name = ctk.CTkLabel(
            gpu,
            text="Checking GPU…",
            font=sans(11, "bold"),
            text_color=C.TEXT,
            anchor="w",
            wraplength=170,
            justify="left",
        )
        self._gpu_name.pack(anchor="w", padx=12)
        self._gpu_detail = ctk.CTkLabel(
            gpu,
            text="CUDA · TensorRT",
            font=sans(9),
            text_color=C.TEXT_MUTED,
            anchor="w",
            wraplength=170,
            justify="left",
        )
        self._gpu_detail.pack(anchor="w", padx=12, pady=(1, 10))
        ctk.CTkLabel(
            bottom,
            text=f"v{__version__}  ·  local  ·  AGPL-3.0",
            font=sans(9),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", padx=4, pady=(10, 0))

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color=C.BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)
        self.main = main

        header = ctk.CTkFrame(main, fg_color="transparent", height=80)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)
        self.header = header

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        self._header_title = ctk.CTkLabel(
            left,
            text="Workspace",
            font=sans(23, "bold"),
            text_color=C.TEXT,
            anchor="w",
            height=30,
        )
        self._header_title.pack(anchor="w")
        self._header_sub = ctk.CTkLabel(
            left,
            text="",
            font=sans(11),
            text_color=C.TEXT_MUTED,
            anchor="w",
            height=17,
        )
        self._header_sub.pack(anchor="w")
        self._header_note = ctk.CTkLabel(
            left,
            text="",
            font=sans(10, "bold"),
            text_color=C.ACCENT,
            anchor="w",
            height=15,
        )
        self._header_note.pack(anchor="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")
        self._output_folder_btn = ctk.CTkButton(
            actions,
            text="Output folder",
            command=self._open_output_folder,
            width=118,
            height=34,
            corner_radius=8,
            fg_color=C.SURFACE,
            hover_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            text_color=C.TEXT_SECONDARY,
            font=sans(12),
        )
        self._output_folder_btn.pack(side="left", padx=(0, 8))
        self._import_btn = ctk.CTkButton(
            actions,
            text="Import video",
            command=self._choose_video,
            width=124,
            height=34,
            corner_radius=8,
            fg_color=C.ACCENT,
            hover_color=C.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=sans(12, "bold"),
        )
        self._import_btn.pack(side="left")

        content = ctk.CTkFrame(main, fg_color=C.BG, corner_radius=0)
        content.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 18))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        self.content = content

        self.center_stack = ctk.CTkFrame(content, fg_color="transparent")
        self.center_stack.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.center_stack.grid_rowconfigure(0, weight=1)
        self.center_stack.grid_columnconfigure(0, weight=1)
        self.view_scroll = ScrollArea(self.center_stack, fg_color=C.BG)
        self.view_scroll.grid(row=0, column=0, sticky="nsew")
        self.view_host = self.view_scroll.body
        self._build_status_card(main)

        self.settings_panel = ctk.CTkScrollableFrame(
            content,
            width=S.SETTINGS_WIDTH,
            fg_color=C.BG,
            corner_radius=0,
            scrollbar_button_color=C.BORDER_STRONG,
            scrollbar_button_hover_color=C.TEXT_MUTED,
        )
        self.settings_panel.grid(row=0, column=1, sticky="nsew")
        self.settings_panel.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------- import view

    def _build_import_view(self) -> None:
        view = ctk.CTkFrame(self.view_host, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew")
        view.grid_rowconfigure(0, weight=1)
        view.grid_columnconfigure(0, weight=1)
        self.import_view = view

        panel = card(view)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        hero = ctk.CTkFrame(panel, fg_color="transparent")
        hero.grid(row=0, column=0, sticky="ew", padx=44, pady=(38, 10))
        hero.grid_columnconfigure(1, weight=1)

        icon = tk.Canvas(hero, width=74, height=74, bg=C.SURFACE, highlightthickness=0)
        icon.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 22))
        icon.create_polygon(
            14,
            2,
            50,
            2,
            60,
            12,
            60,
            62,
            50,
            72,
            14,
            72,
            4,
            62,
            4,
            12,
            smooth=True,
            fill=C.ACCENT_SOFT,
            outline=C.ACCENT_BORDER,
            width=1,
        )
        icon.create_polygon(30, 26, 30, 48, 47, 37, fill=C.ACCENT, outline="")

        ctk.CTkLabel(
            hero,
            text="Restore your own video, locally",
            font=sans(22, "bold"),
            text_color=C.TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            hero,
            text=(
                "Import a clip, scan the timeline for mosaic regions, then restore the "
                "selected ranges with BasicVSR++. Nothing is uploaded and the source file "
                "is never overwritten."
            ),
            font=sans(12),
            text_color=C.TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=560,
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))

        choose_row = ctk.CTkFrame(panel, fg_color="transparent")
        choose_row.grid(row=1, column=0, sticky="w", padx=44, pady=(18, 6))
        ctk.CTkButton(
            choose_row,
            text="Choose a video…",
            command=self._choose_video,
            width=160,
            height=42,
            corner_radius=9,
            fg_color=C.ACCENT,
            hover_color=C.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=sans(13, "bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            choose_row,
            text="MP4, MKV, MOV, AV1, HEVC · NVIDIA GPU required",
            font=sans(10),
            text_color=C.TEXT_MUTED,
        ).pack(side="left", padx=(14, 0))

        recent_wrap = ctk.CTkFrame(panel, fg_color="transparent")
        recent_wrap.grid(row=2, column=0, sticky="nsew", padx=44, pady=(18, 34))
        recent_wrap.grid_columnconfigure(0, weight=1)
        recent_wrap.grid_rowconfigure(2, weight=1)
        ctk.CTkFrame(recent_wrap, fg_color=C.BORDER, height=1).grid(
            row=0, column=0, sticky="ew", pady=(0, 16)
        )
        ctk.CTkLabel(
            recent_wrap,
            text="RECENT",
            font=sans(10, "bold"),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).grid(row=1, column=0, sticky="nw")
        self.recent_container = ctk.CTkScrollableFrame(
            recent_wrap,
            fg_color=C.SURFACE,
            corner_radius=0,
            scrollbar_button_color=C.BORDER_STRONG,
        )
        self.recent_container.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.recent_container.grid_columnconfigure(0, weight=1)

    # ----------------------------------------------------------- workspace view

    def _build_workspace(self) -> None:
        view = ctk.CTkFrame(self.view_host, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew")
        view.grid_rowconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=0)
        view.grid_rowconfigure(2, weight=0)
        view.grid_columnconfigure(0, weight=1)
        self.workspace_view = view
        self._build_preview_card(view)
        self._build_scan_card(view)

    def _build_preview_card(self, parent) -> None:
        preview = card(parent)
        preview.grid(row=0, column=0, sticky="nsew")
        preview.grid_rowconfigure(1, weight=1)
        preview.grid_columnconfigure(0, weight=1)
        self.preview_card = preview

        head = ctk.CTkFrame(preview, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            head,
            text="Preview",
            font=sans(13, "bold"),
            text_color=C.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self._preview_pill = Pill(head, "SOURCE", "accent")
        self._preview_pill.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.compare_seg = ctk.CTkSegmentedButton(
            head,
            values=["Original", "Compare"],
            command=self._on_compare_seg,
            height=28,
            corner_radius=7,
            font=sans(10, "bold"),
            selected_color=C.ACCENT,
            selected_hover_color=C.ACCENT_HOVER,
            unselected_color=C.SURFACE_ALT,
            unselected_hover_color=C.ACCENT_SOFT,
            fg_color=C.SURFACE_ALT,
            border_width=1,

            text_color=C.TEXT_SECONDARY,
            text_color_disabled=C.TEXT_MUTED,
        )
        self.compare_seg.grid(row=0, column=2, sticky="e")
        self.compare_seg.set("Original")
        self.compare_seg.configure(state="disabled")

        canvas_wrap = ctk.CTkFrame(
            preview,
            fg_color=C.PREVIEW_BG,
            corner_radius=10,
            border_width=0,
            height=240,
        )
        canvas_wrap.grid(row=1, column=0, sticky="nsew", padx=16)
        canvas_wrap.grid_rowconfigure(0, weight=1)
        canvas_wrap.grid_columnconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(
            canvas_wrap,
            bg=C.PREVIEW_BG,
            highlightthickness=0,
            bd=0,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)

        transport = ctk.CTkFrame(preview, fg_color="transparent")
        transport.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 10))
        transport.grid_columnconfigure(3, weight=1)
        self.play_btn = ctk.CTkButton(
            transport,
            text="▶",
            width=34,
            height=30,
            corner_radius=7,
            fg_color=C.ACCENT,
            hover_color=C.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=sans(11, "bold"),
            command=self._toggle_play,
            state="disabled",
        )
        self.play_btn.grid(row=0, column=0, sticky="w")
        self.time_label = ctk.CTkLabel(
            transport,
            text="0:00.0",
            font=mono(10),
            text_color=C.TEXT_SECONDARY,
            width=52,
            anchor="w",
        )
        self.time_label.grid(row=0, column=1, padx=(8, 4))
        self.slider = ctk.CTkSlider(
            transport,
            from_=0,
            to=1,
            height=16,
            fg_color=C.BORDER,
            progress_color=C.ACCENT,
            button_color=C.ACCENT,
            button_hover_color=C.ACCENT_HOVER,
            command=self._on_slider,
        )
        self.slider.grid(row=0, column=3, sticky="ew", padx=4)
        self.slider.set(0)
        self.slider.bind("<ButtonPress-1>", self._on_slider_press)
        self.slider.bind("<ButtonRelease-1>", self._on_slider_release)
        self.duration_label = ctk.CTkLabel(
            transport,
            text="0:00.0",
            font=mono(10),
            text_color=C.TEXT_MUTED,
            width=52,
            anchor="e",
        )
        self.duration_label.grid(row=0, column=4)

        self.compare_bar = ctk.CTkFrame(preview, fg_color="transparent")
        self.compare_bar.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.compare_bar.grid_columnconfigure(3, weight=1)
        self.compare_mode_seg = ctk.CTkSegmentedButton(
            self.compare_bar,
            values=["Side by side", "Wipe"],
            command=self._on_compare_mode,
            height=26,
            corner_radius=6,
            font=sans(10, "bold"),
            selected_color=C.ACCENT,
            selected_hover_color=C.ACCENT_HOVER,
            unselected_color=C.SURFACE_ALT,
            unselected_hover_color=C.ACCENT_SOFT,
            fg_color=C.SURFACE_ALT,
            border_width=1,

            text_color=C.TEXT_SECONDARY,
        )
        self.compare_mode_seg.grid(row=0, column=0, sticky="w")
        self.compare_mode_seg.set("Side by side")
        self.wipe_label = ctk.CTkLabel(
            self.compare_bar,
            text="Wipe 50%",
            font=sans(10),
            text_color=C.TEXT_MUTED,
            width=60,
            anchor="e",
        )
        self.wipe_slider = ctk.CTkSlider(
            self.compare_bar,
            from_=0.05,
            to=0.95,
            number_of_steps=90,
            height=14,
            fg_color=C.BORDER,
            progress_color=C.ACCENT,
            button_color=C.ACCENT,
            button_hover_color=C.ACCENT_HOVER,
            command=self._on_wipe,
        )
        self.wipe_slider.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(10, 4))
        self.wipe_slider.set(self.wipe)
        self.wipe_label.grid(row=0, column=3, sticky="e")
        self.wipe_label.grid_remove()
        self.wipe_slider.grid_remove()
        self.compare_bar.grid_remove()

    def _build_scan_card(self, parent) -> None:
        card_frame = card(parent)
        card_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        card_frame.grid_columnconfigure(0, weight=1)
        self.scan_card = card_frame

        head = ctk.CTkFrame(card_frame, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(11, 4))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            head,
            text="Mosaic timeline",
            font=sans(13, "bold"),
            text_color=C.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.scan_pill = Pill(head, "NOT SCANNED", "neutral")
        self.scan_pill.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.clear_scan_btn = ctk.CTkButton(
            head,
            text="Clear",
            command=self._clear_selection,
            width=62,
            height=28,
            corner_radius=7,
            fg_color="transparent",
            hover_color=C.SURFACE_ALT,
            text_color=C.TEXT_MUTED,
            font=sans(10, "bold"),
        )
        self.clear_scan_btn.grid(row=0, column=2, sticky="e", padx=(0, 2))
        self.select_all_btn = ctk.CTkButton(
            head,
            text="Select all",
            command=self._select_all,
            width=76,
            height=28,
            corner_radius=7,
            fg_color="transparent",
            hover_color=C.SURFACE_ALT,
            text_color=C.TEXT_SECONDARY,
            font=sans(10, "bold"),
        )
        self.select_all_btn.grid(row=0, column=3, sticky="e", padx=(0, 2))
        self.scan_btn = ctk.CTkButton(
            head,
            text="Scan",
            command=self._start_scan,
            width=74,
            height=28,
            corner_radius=7,
            fg_color=C.ACCENT_SOFT,
            hover_color=C.ACCENT_SOFT_HOVER,
            border_width=1,
            border_color=C.ACCENT_BORDER,
            text_color=C.ACCENT,
            font=sans(10, "bold"),
            state="disabled",
        )
        self.scan_btn.grid(row=0, column=4, sticky="e")

        self.timeline = ScanTimeline(
            card_frame,
            on_seek=self._seek_from_timeline,
            height=76,
        )
        self.timeline.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 4))

        self.range_list = ctk.CTkScrollableFrame(
            card_frame,
            height=64,
            fg_color=C.SURFACE_ALT,
            corner_radius=8,
            border_width=1,
            border_color=C.BORDER,
            scrollbar_button_color=C.BORDER_STRONG,
            label_text="",
        )
        self.range_list.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 0))
        self.range_list.grid_columnconfigure(0, weight=1)
        self.range_list._scrollbar.configure(height=64)

        self.scan_summary = ctk.CTkLabel(
            card_frame,
            text="Scan once to find mosaic ranges, then choose what to restore.",
            font=sans(10),
            text_color=C.TEXT_MUTED,
            anchor="w",
        )
        self.scan_summary.grid(row=3, column=0, sticky="w", padx=16, pady=(6, 10))

    def _build_status_card(self, parent) -> None:
        card_frame = card(parent)
        card_frame.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 14))
        card_frame.grid_columnconfigure(1, weight=1)
        self.status_card = card_frame

        self.status_dot = tk.Canvas(
            card_frame, width=12, height=12, bg=C.SURFACE, highlightthickness=0
        )
        self.status_dot.grid(row=0, column=0, sticky="nw", padx=(16, 0), pady=(17, 0))
        self._status_dot_id = self.status_dot.create_oval(
            1, 1, 11, 11, fill=C.TEXT_MUTED, outline=""
        )
        labels = ctk.CTkFrame(card_frame, fg_color="transparent")
        labels.grid(row=0, column=1, sticky="ew", padx=(9, 12), pady=(11, 0))
        self.status_title = ctk.CTkLabel(
            labels,
            text="Ready",
            font=sans(12, "bold"),
            text_color=C.TEXT,
            anchor="w",
            height=18,
        )
        self.status_title.pack(anchor="w")
        self.status_detail = ctk.CTkLabel(
            labels,
            text="Import a video to begin.",
            font=sans(10),
            text_color=C.TEXT_SECONDARY,
            anchor="w",
            height=15,
            wraplength=540,
            justify="left",
        )
        self.status_detail.pack(anchor="w")

        right = ctk.CTkFrame(card_frame, fg_color="transparent")
        right.grid(row=0, column=2, sticky="ne", padx=(0, 12), pady=(10, 0))
        self.start_btn = ctk.CTkButton(
            right,
            text="Start restoration",
            command=self._start_restore,
            width=138,
            height=32,
            corner_radius=7,
            fg_color=C.ACCENT,
            hover_color=C.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=sans(11, "bold"),
            state="disabled",
        )
        self.start_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = ctk.CTkButton(
            right,
            text="Cancel",
            command=self._cancel_processing,
            width=72,
            height=26,
            corner_radius=6,
            fg_color=C.ERROR_SOFT,
            hover_color="#FEE2E2",
            text_color=C.ERROR,
            font=sans(10, "bold"),
        )
        self.cancel_btn.pack(side="left", padx=(0, 4))
        self.cancel_btn.pack_forget()
        self.log_btn = ctk.CTkButton(
            right,
            text="View log",
            command=self._show_log,
            width=74,
            height=26,
            corner_radius=6,
            fg_color="transparent",
            hover_color=C.SURFACE_ALT,
            text_color=C.TEXT_MUTED,
            font=sans(10, "bold"),
        )
        self.log_btn.pack(side="left", padx=(4, 0))

        self.progress = ctk.CTkProgressBar(
            card_frame,
            height=6,
            corner_radius=99,
            fg_color=C.SURFACE_ALT,
            progress_color=C.ACCENT,
            border_width=1,
            border_color=C.BORDER,
        )
        self.progress.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16, pady=(8, 0))
        self.progress.set(0)

        footer = ctk.CTkFrame(card_frame, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=(7, 10))
        footer.grid_columnconfigure(0, weight=1)
        self.status_stats = ctk.CTkLabel(
            footer,
            text="",
            font=mono(9),
            text_color=C.TEXT_MUTED,
            anchor="w",
        )
        self.status_stats.grid(row=0, column=0, sticky="w")
        actions = ctk.CTkFrame(footer, fg_color="transparent", width=1, height=26)
        actions.grid(row=0, column=1, sticky="e")
        self.action_compare = ctk.CTkButton(
            actions,
            text="Compare",
            command=lambda: self._show_compare(True),
            width=74,
            height=26,
            corner_radius=6,
            fg_color=C.ACCENT_SOFT,
            hover_color=C.ACCENT_SOFT_HOVER,
            border_width=1,
            border_color=C.ACCENT_BORDER,
            text_color=C.ACCENT,
            font=sans(10, "bold"),
        )
        self.action_open = ctk.CTkButton(
            actions,
            text="Open video",
            command=self._open_output,
            width=82,
            height=26,
            corner_radius=6,
            fg_color=C.ACCENT,
            hover_color=C.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=sans(10, "bold"),
        )
        self.action_folder = ctk.CTkButton(
            actions,
            text="Show in folder",
            command=self._reveal_output,
            width=94,
            height=26,
            corner_radius=6,
            fg_color="transparent",
            hover_color=C.SURFACE_ALT,
            text_color=C.TEXT_SECONDARY,
            font=sans(10, "bold"),
        )
        for widget in (self.action_compare, self.action_open, self.action_folder):
            widget.pack(side="left", padx=(4, 0))
            widget.pack_forget()

    # ------------------------------------------------------------------ settings

    def _build_settings_panel(self) -> None:
        settings_card = card(self.settings_panel)
        settings_card.pack(fill="x", padx=(0, 4), pady=(0, 18))
        settings_card.grid_columnconfigure(0, weight=1)
        self.settings_card = settings_card

        pad = 16
        header = ctk.CTkFrame(settings_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=pad, pady=(16, 0))
        ctk.CTkLabel(
            header,
            text="Restoration settings",
            font=sans(14, "bold"),
            text_color=C.TEXT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="BasicVSR++ · local NVIDIA pipeline",
            font=sans(10),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        row = 1
        row = self._settings_detection(settings_card, row, pad)
        row = self._settings_export(settings_card, row, pad)
        row = self._settings_scope(settings_card, row, pad)

        self.restore_summary = ctk.CTkLabel(
            settings_card,
            text="Scan a video to choose ranges.",
            font=sans(10),
            text_color=C.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=300,
        )
        self.restore_summary.grid(row=row, column=0, sticky="w", padx=pad, pady=(12, 6))
        row += 1
        ctk.CTkLabel(
            settings_card,
            text="The source video is never modified. Existing files are never overwritten.",
            font=sans(9),
            text_color=C.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=300,
        ).grid(row=row, column=0, sticky="w", padx=pad, pady=(2, 16))

    def _divider(self, parent, row: int, pad: int) -> int:
        ctk.CTkFrame(parent, fg_color=C.BORDER, height=1).grid(
            row=row, column=0, sticky="ew", padx=pad, pady=(14, 12)
        )
        return row + 1

    def _settings_detection(self, parent, row: int, pad: int) -> int:
        row = self._divider(parent, row, pad)
        ctk.CTkLabel(
            parent,
            text="DETECTION",
            font=sans(9, "bold"),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=pad)
        row += 1

        value = self._field_row(parent, row, "Detector", pad)
        self.detector_combo = ctk.CTkComboBox(
            parent,
            values=[self.settings.detection_model],
            command=self._on_detector_change,
            height=32,
            corner_radius=7,
            font=sans(11),
            dropdown_font=sans(11),
            fg_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            button_color=C.SURFACE_ALT,
            button_hover_color=C.ACCENT_SOFT,
            dropdown_fg_color=C.SURFACE,
            dropdown_hover_color=C.ACCENT_SOFT,
            dropdown_text_color=C.TEXT,
            text_color=C.TEXT,
        )
        self.detector_combo.grid(row=row + 1, column=0, sticky="ew", padx=pad, pady=(4, 2))
        self.detector_combo.set(self.settings.detection_model)
        self._settings_widgets.append(self.detector_combo)
        self._settings_hint(
            parent,
            row + 2,
            "RF-DETR is more accurate but compiles on first use; Lada YOLO is fast.",
            pad,
        )
        row += 3

        self.threshold_slider, self.threshold_value = self._slider_row(
            parent,
            row,
            "Confidence",
            "0.05",
            "0.95",
            90,
            self.settings.threshold,
            self._on_threshold,
            pad,
            fmt="{:.2f}",
        )
        row += 3
        self._settings_hint(
            parent,
            row,
            "Higher values detect fewer false regions.",
            pad,
        )
        row += 1

        self.clip_slider, self.clip_value = self._slider_row(
            parent,
            row,
            "Max clip size",
            "12",
            "180",
            168,
            self.settings.max_clip_size,
            self._on_clip_size,
            pad,
            fmt="{:.0f} frames",
            integer=True,
        )
        row += 3
        self._settings_hint(
            parent,
            row,
            "Frames per BasicVSR++ clip. Lower it if the GPU runs out of memory.",
            pad,
        )
        row += 1

        self.overlap_slider, self.overlap_value = self._slider_row(
            parent,
            row,
            "Temporal overlap",
            "0",
            "40",
            40,
            self.settings.temporal_overlap,
            self._on_overlap,
            pad,
            fmt="{:.0f} frames",
            integer=True,
        )
        row += 3

        value = self._field_row(parent, row, "Denoise", pad)
        self.denoise_combo = ctk.CTkComboBox(
            parent,
            values=["None", "Low", "Medium", "High"],
            command=self._on_denoise,
            height=30,
            corner_radius=7,
            font=sans(11),
            dropdown_font=sans(11),
            fg_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            button_color=C.SURFACE_ALT,
            button_hover_color=C.ACCENT_SOFT,
            dropdown_fg_color=C.SURFACE,
            dropdown_hover_color=C.ACCENT_SOFT,
            dropdown_text_color=C.TEXT,
            text_color=C.TEXT,
        )
        self.denoise_combo.grid(row=row + 1, column=0, sticky="ew", padx=pad, pady=(4, 0))
        self.denoise_combo.set(self.settings.denoise.capitalize())
        self._settings_widgets.append(self.denoise_combo)
        row += 2

        self.scene_switch = ctk.CTkSwitch(
            parent,
            text="Scene-cut detection",
            font=sans(11),
            text_color=C.TEXT_SECONDARY,
            progress_color=C.ACCENT,
            button_color=C.SURFACE,
            button_hover_color=C.SURFACE,
            fg_color=C.BORDER_STRONG,
            command=self._on_scene,
        )
        self.scene_switch.grid(row=row, column=0, sticky="w", padx=pad, pady=(10, 0))
        if self.settings.scene_detection:
            self.scene_switch.select()
        self._settings_widgets.append(self.scene_switch)
        row += 1
        return row

    def _settings_export(self, parent, row: int, pad: int) -> int:
        row = self._divider(parent, row, pad)
        ctk.CTkLabel(
            parent,
            text="EXPORT",
            font=sans(9, "bold"),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=pad)
        row += 1

        self._field_row(parent, row, "Codec", pad)
        self.codec_seg = ctk.CTkSegmentedButton(
            parent,
            values=["H.264", "HEVC", "AV1"],
            command=self._on_codec,
            height=30,
            corner_radius=7,
            font=sans(10, "bold"),
            selected_color=C.ACCENT,
            selected_hover_color=C.ACCENT_HOVER,
            unselected_color=C.SURFACE_ALT,
            unselected_hover_color=C.ACCENT_SOFT,
            fg_color=C.SURFACE_ALT,
            border_width=1,

            text_color=C.TEXT_SECONDARY,
        )
        self.codec_seg.grid(row=row + 1, column=0, sticky="ew", padx=pad, pady=(4, 0))
        self.codec_seg.set({"h264": "H.264", "hevc": "HEVC", "av1": "AV1"}[self.settings.codec])
        self._settings_widgets.append(self.codec_seg)
        row += 2

        max_cq = 63 if self.settings.codec == "av1" else 51
        self.cq_slider, self.cq_value = self._slider_row(
            parent,
            row,
            "Quality (CQ)",
            "1",
            str(max_cq),
            max_cq - 1,
            min(self.settings.cq, max_cq),
            self._on_cq,
            pad,
            fmt="{:.0f}",
            integer=True,
        )
        row += 3
        self.codec_hint = self._settings_hint(
            parent,
            row,
            "Selected ranges always keep the source codec; this choice applies to whole-video export.",
            pad,
        )
        row += 1

        self._field_row(parent, row, "Filename suffix", pad)
        self.suffix_entry = ctk.CTkEntry(
            parent,
            height=30,
            corner_radius=7,
            fg_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            text_color=C.TEXT,
            font=sans(11),
        )
        self.suffix_entry.grid(row=row + 1, column=0, sticky="ew", padx=pad, pady=(4, 0))
        self.suffix_entry.insert(0, self.settings.suffix)
        self.suffix_entry.bind("<KeyRelease>", self._on_suffix)
        self.suffix_entry.bind("<FocusOut>", self._on_suffix)
        self._settings_widgets.append(self.suffix_entry)
        row += 2

        self._field_row(parent, row, "Output folder", pad, hint_text="")
        folder_row = ctk.CTkFrame(parent, fg_color="transparent")
        folder_row.grid(row=row + 1, column=0, sticky="ew", padx=pad, pady=(4, 0))
        folder_row.grid_columnconfigure(0, weight=1)
        self.output_entry = ctk.CTkEntry(
            folder_row,
            height=30,
            corner_radius=7,
            fg_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            text_color=C.TEXT,
            font=sans(10),
            placeholder_text=OUTPUT_DIR_PLACEHOLDER,
        )
        self.output_entry.grid(row=0, column=0, sticky="ew")
        if self.settings.output_dir:
            self.output_entry.insert(0, self.settings.output_dir)
        self.output_entry.bind("<KeyRelease>", self._on_output_dir)
        self._settings_widgets.append(self.output_entry)
        browse = ctk.CTkButton(
            folder_row,
            text="Browse",
            command=self._browse_output,
            width=64,
            height=30,
            corner_radius=7,
            fg_color=C.SURFACE,
            hover_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            text_color=C.TEXT_SECONDARY,
            font=sans(10, "bold"),
        )
        browse.grid(row=0, column=1, padx=(6, 0))
        self._settings_widgets.append(browse)
        row += 2
        return row

    def _settings_scope(self, parent, row: int, pad: int) -> int:
        row = self._divider(parent, row, pad)
        ctk.CTkLabel(
            parent,
            text="SCOPE",
            font=sans(9, "bold"),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=pad)
        row += 1
        self.scope_seg = ctk.CTkSegmentedButton(
            parent,
            values=["Selected ranges", "Whole video"],
            command=self._on_scope,
            height=30,
            corner_radius=7,
            font=sans(10, "bold"),
            selected_color=C.ACCENT,
            selected_hover_color=C.ACCENT_HOVER,
            unselected_color=C.SURFACE_ALT,
            unselected_hover_color=C.ACCENT_SOFT,
            fg_color=C.SURFACE_ALT,
            border_width=1,

            text_color=C.TEXT_SECONDARY,
        )
        self.scope_seg.grid(row=row, column=0, sticky="ew", padx=pad, pady=(4, 0))
        self.scope_seg.set("Selected ranges" if self.settings.scope == "selected" else "Whole video")
        self._settings_widgets.append(self.scope_seg)
        row += 1
        return row

    def _field_row(self, parent, row: int, label: str, pad: int, hint_text: str = ""):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=pad, pady=(8, 0))
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame,
            text=label,
            font=sans(11),
            text_color=C.TEXT_SECONDARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        value = ctk.CTkLabel(
            frame,
            text=hint_text,
            font=sans(10, "bold"),
            text_color=C.TEXT_MUTED,
            anchor="e",
        )
        value.grid(row=0, column=1, sticky="e")
        return value

    def _settings_hint(self, parent, row: int, text: str, pad: int):
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=sans(9),
            text_color=C.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=300,
        )
        label.grid(row=row, column=0, sticky="w", padx=pad, pady=(4, 0))
        return label

    def _slider_row(
        self,
        parent,
        row: int,
        label: str,
        from_: str,
        to: str,
        steps: int,
        initial: float,
        command,
        pad: int,
        *,
        fmt: str,
        integer: bool = False,
    ):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.grid(row=row, column=0, sticky="ew", padx=pad, pady=(9, 0))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head,
            text=label,
            font=sans(11),
            text_color=C.TEXT_SECONDARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        value = ctk.CTkLabel(
            head,
            text=fmt.format(initial),
            font=sans(10, "bold"),
            text_color=C.TEXT,
            anchor="e",
        )
        value.grid(row=0, column=1, sticky="e")
        slider = ctk.CTkSlider(
            parent,
            from_=float(from_),
            to=float(to),
            number_of_steps=int(steps),
            height=16,
            fg_color=C.BORDER,
            progress_color=C.ACCENT,
            button_color=C.ACCENT,
            button_hover_color=C.ACCENT_HOVER,
            command=command,
        )
        slider.grid(row=row + 1, column=0, sticky="ew", padx=pad, pady=(2, 0))
        slider.set(float(initial))
        self._settings_widgets.append(slider)
        return slider, value

    # ------------------------------------------------------------------- system

    def _build_system_view(self) -> None:
        view = ctk.CTkFrame(self.view_host, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew")
        view.grid_rowconfigure(0, weight=1)
        view.grid_columnconfigure(0, weight=1)
        self.system_view = view

        panel = card(view)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        head.grid_columnconfigure(0, weight=1)
        head_left = ctk.CTkFrame(head, fg_color="transparent")
        head_left.grid(row=0, column=0, sticky="w")
        section_title(
            head_left,
            "Environment check",
            "Everything runs on this machine. No account, license key, or upload is used.",
        )
        ctk.CTkButton(
            head,
            text="Re-run check",
            command=self._run_env_check,
            width=92,
            height=30,
            corner_radius=7,
            fg_color=C.SURFACE,
            hover_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            text_color=C.TEXT_SECONDARY,
            font=sans(10, "bold"),
        ).grid(row=0, column=1, sticky="e")
        self.env_rows = ctk.CTkScrollableFrame(
            panel,
            fg_color=C.SURFACE,
            scrollbar_button_color=C.BORDER_STRONG,
        )
        self.env_rows.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.env_rows.grid_columnconfigure(0, weight=1)
        self._env_placeholder = ctk.CTkLabel(
            self.env_rows,
            text="Checking this machine…",
            font=sans(11),
            text_color=C.TEXT_MUTED,
            anchor="w",
        )
        self._env_placeholder.grid(row=0, column=0, sticky="w", padx=8, pady=12)

    def _rebuild_env_rows(self, report: dict) -> None:
        for child in self.env_rows.winfo_children():
            child.destroy()
        for index, item in enumerate(report.get("rows", [])):
            row = ctk.CTkFrame(self.env_rows, fg_color="transparent")
            row.grid(row=index, column=0, sticky="ew", padx=6, pady=3)
            row.grid_columnconfigure(1, weight=1)
            dot = tk.Canvas(row, width=8, height=8, bg=C.SURFACE, highlightthickness=0)
            dot.grid(row=0, column=0, sticky="w", padx=(2, 8))
            color = {
                "ok": C.SUCCESS,
                "warn": C.WARNING,
                "error": C.ERROR,
            }.get(item.get("status"), C.TEXT_MUTED)
            dot.create_oval(1, 1, 7, 7, fill=color, outline="")
            ctk.CTkLabel(
                row,
                text=item.get("label", ""),
                font=sans(11),
                text_color=C.TEXT_SECONDARY,
                anchor="w",
                width=132,
            ).grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(
                row,
                text=item.get("value", ""),
                font=sans(11, "bold"),
                text_color=C.TEXT if item.get("status") == "ok" else color,
                anchor="w",
                justify="left",
                wraplength=500,
            ).grid(row=0, column=2, sticky="w", padx=(8, 4))
        if report.get("errors"):
            row = ctk.CTkFrame(
                self.env_rows,
                fg_color=C.ERROR_SOFT,
                corner_radius=8,
            )
            row.grid(row=len(report.get("rows", [])), column=0, sticky="ew", padx=6, pady=(10, 4))
            ctk.CTkLabel(
                row,
                text="\n".join(report["errors"]),
                font=sans(10),
                text_color=C.ERROR,
                anchor="w",
                justify="left",
                wraplength=560,
            ).pack(anchor="w", padx=12, pady=10)
        else:
            row = ctk.CTkFrame(self.env_rows, fg_color=C.SUCCESS_SOFT, corner_radius=8)
            row.grid(row=len(report.get("rows", [])), column=0, sticky="ew", padx=6, pady=(10, 4))
            ctk.CTkLabel(
                row,
                text="All required components are present. The first run may compile TensorRT engines.",
                font=sans(10),
                text_color=C.SUCCESS,
                anchor="w",
                justify="left",
                wraplength=560,
            ).pack(anchor="w", padx=12, pady=10)

    def _build_about_view(self) -> None:
        view = ctk.CTkFrame(self.view_host, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew")
        view.grid_rowconfigure(0, weight=1)
        view.grid_columnconfigure(0, weight=1)
        self.about_view = view

        panel = card(view)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 8))
        ctk.CTkLabel(
            head,
            text="VideoRefiner Studio",
            font=sans(22, "bold"),
            text_color=C.TEXT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            head,
            text=f"Version {__version__} · AGPL-3.0-only · free and offline",
            font=sans(11),
            text_color=C.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        text = ctk.CTkTextbox(
            panel,
            fg_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            corner_radius=8,
            text_color=C.TEXT_SECONDARY,
            font=sans(11),
            wrap="word",
        )
        text.grid(row=1, column=0, sticky="nsew", padx=26, pady=(8, 10))
        text.insert(
            "end",
            ABOUT_TEXT,
        )
        text.configure(state="disabled")

        links = ctk.CTkFrame(panel, fg_color="transparent")
        links.grid(row=2, column=0, sticky="w", padx=26, pady=(0, 20))
        for label, url in (
            ("Jasna source", JASNA_URL),
            ("AGPL-3.0 license", AGPL_URL),
            ("Lada models", LADA_URL),
            ("RF-DETR", RF_DETR_URL),
        ):
            ctk.CTkButton(
                links,
                text=label,
                command=lambda u=url: webbrowser.open(u),
                width=112,
                height=30,
                corner_radius=7,
                fg_color=C.SURFACE,
                hover_color=C.SURFACE_ALT,
                border_width=1,
                border_color=C.BORDER,
                text_color=C.TEXT_SECONDARY,
                font=sans(10, "bold"),
            ).pack(side="left", padx=(0, 7))

    # ------------------------------------------------------------------- views

    def _show_view(self, name: str) -> None:
        if name == "workspace" and self.media is None:
            name = "import"
        if name == "compare":
            if self.media is None:
                name = "import"
            else:
                self._show_view("workspace")
                self._show_compare(True)
                return
        if name not in {"import", "workspace", "system", "about"}:
            name = "import"
        self._view = name
        for frame in (
            self.import_view,
            self.workspace_view,
            self.system_view,
            self.about_view,
        ):
            frame.grid_remove()
        target = {
            "import": self.import_view,
            "workspace": self.workspace_view,
            "system": self.system_view,
            "about": self.about_view,
        }[name]
        target.grid(row=0, column=0, sticky="nsew")
        if name == "workspace":
            self.settings_panel.grid()
            self.view_scroll.set_min_content_height(560)
        else:
            self.settings_panel.grid_remove()
            self.view_scroll.set_min_content_height(0)
        titles = {
            "import": ("Import", "Local video restoration with mosaic detection and BasicVSR++."),
            "workspace": ("Workspace", "Scan, select, restore, and compare."),
            "system": ("System check", "GPU, runtime, FFmpeg, and model diagnostics."),
            "about": ("About", "Licenses, attribution, and project links."),
        }
        title, subtitle = titles[name]
        if name == "workspace" and self.media is not None:
            subtitle = f"{self.media.path.name} · {self._meta_text(self.media)}"
        self._header_title.configure(text=title)
        self._header_sub.configure(text=subtitle)
        active_key = name
        for key, button in self._nav_buttons.items():
            active = key == active_key
            button.configure(
                fg_color=C.ACCENT_SOFT if active else "transparent",
                text_color=C.ACCENT if active else C.TEXT_SECONDARY,
                font=sans(13, "bold") if active else sans(13),
            )
        if name == "workspace":
            self._request_static()
        if name == "system" and self._env is not None:
            self._rebuild_env_rows(self._env)

    def _notify(self, text: str, kind: str = "accent") -> None:
        color = {
            "accent": C.ACCENT,
            "success": C.SUCCESS,
            "warning": C.WARNING,
            "error": C.ERROR,
        }.get(kind, C.ACCENT)
        self._header_note.configure(text=text, text_color=color)
        if self._toast_after is not None:
            self.after_cancel(self._toast_after)
        self._toast_after = self.after(5000, lambda: self._header_note.configure(text=""))

    # ------------------------------------------------------------------- media

    def _choose_video(self) -> None:
        initial = self.settings.last_dir or (str(self.media.path.parent) if self.media else "")
        path = filedialog.askopenfilename(
            parent=self,
            title="Import a video",
            initialdir=initial or None,
            filetypes=VIDEO_TYPES,
        )
        if path:
            self._load_video(Path(path))

    def _load_video(self, path: Path) -> None:
        if self._processing:
            self._notify("A job is running. Cancel it before importing another video.", "warning")
            return
        try:
            info = media.probe_video(path)
        except media.MediaError as exc:
            messagebox.showerror("Cannot open video", str(exc), parent=self)
            self._append_log("ERROR", f"Could not open {path}: {exc}")
            return
        self._stop_playback(update_ui=False)
        self.media = info
        self.scan = None
        self.scan_segments = ()
        self.selected_ranges = set()
        self.output_path = None
        self.current_time = 0.0
        self.compare = False
        self.compare_mode = "side"
        self._range_checks = []
        self._scan_detector = ""
        self.compare_seg.configure(state="disabled")
        self.compare_seg.set("Original")
        self.compare_bar.grid_remove()
        self._preview_pill.set("SOURCE", "accent")
        self._hide_output_actions()
        self.play_btn.configure(state="normal")
        self.slider.configure(to=max(0.1, info.duration))
        self._set_time(0.0)
        self.duration_label.configure(text=fmt_time(info.duration))
        self._scan_pill_reset()
        self.scan_pill.set("NOT SCANNED", "neutral")
        self.scan_summary.configure(
            text="Scan once to find mosaic ranges, then choose what to restore."
        )
        self._rebuild_ranges([])
        self.timeline.set_data(
            times=(), scores=(), threshold=self.settings.threshold, selected=set(), playhead=0, duration=info.duration
        )
        self.scan_btn.configure(state="normal")
        self._sync_codec_controls()
        self._set_status(
            "idle",
            "Ready to scan",
            f"{info.width}×{info.height} · {info.fps:.2f} fps · {fmt_time(info.duration)} · {info.codec.upper()}"
            + (" · audio" if info.has_audio else " · no audio"),
        )
        self.status_stats.configure(text="")
        self._set_progress(0)
        self.settings.add_recent(path)
        self.settings.save()
        self._refresh_recent()
        self._scan_detector = self.settings.detection_model
        self._update_start_state()
        self._update_restore_summary()
        self._show_view("workspace")
        self._set_time(0.0)
        self._request_static(immediate=True)
        self._append_log("INFO", f"Loaded {path} ({info.width}x{info.height}, {info.duration:.2f}s)")

    def _meta_text(self, info: media.MediaInfo) -> str:
        audio = "audio" if info.has_audio else "no audio"
        return (
            f"{info.width}×{info.height} · {info.fps:.2f} fps · "
            f"{fmt_time(info.duration)} · {info.codec.upper()} · {audio}"
        )

    def _refresh_recent(self) -> None:
        for child in self.recent_container.winfo_children():
            child.destroy()
        if not self.settings.recent:
            ctk.CTkLabel(
                self.recent_container,
                text="No recent videos yet. Imported files appear here.",
                font=sans(11),
                text_color=C.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=4, pady=10)
            return
        for index, item in enumerate(self.settings.recent):
            path = Path(item)
            text = f"{path.name}    {path.parent}"
            button = ctk.CTkButton(
                self.recent_container,
                text=text,
                anchor="w",
                height=36,
                corner_radius=7,
                fg_color=C.SURFACE,
                hover_color=C.ACCENT_SOFT,
                text_color=C.TEXT_SECONDARY,
                font=sans(10),
                command=lambda p=path: self._open_recent(p),
            )
            button.grid(row=index, column=0, sticky="ew", padx=2, pady=1)

    def _open_recent(self, path: Path) -> None:
        if not path.is_file():
            self.settings.recent = [item for item in self.settings.recent if item != str(path)]
            self.settings.save()
            self._refresh_recent()
            messagebox.showwarning("File not found", f"{path} is no longer available.", parent=self)
            return
        self._load_video(path)

    # ----------------------------------------------------------------- scanning

    def _start_scan(self) -> None:
        if self._processing or self.media is None:
            return
        self._stop_playback()
        self._static_gen += 1
        self.scan = None
        self.scan_segments = ()
        self.selected_ranges = set()
        self.output_path = None
        self.compare = False
        self.compare_seg.configure(state="disabled")
        self.compare_seg.set("Original")
        self.compare_bar.grid_remove()
        self._preview_pill.set("SOURCE", "accent")
        self._hide_output_actions()
        self._rebuild_ranges([])
        self.timeline.set_data(
            times=(),
            scores=(),
            threshold=self.settings.threshold,
            selected=set(),
            playhead=self.current_time,
            duration=self.media.duration,
        )
        self.scan_pill.set("SCANNING", "accent")
        self._append_log("INFO", f"Starting mosaic scan with {self.settings.detection_model}")
        self._scan_worker = engine.ScanWorker(
            self.media.path, copy.deepcopy(self.settings), self.queue, sample_seconds=1.0
        )
        self._scan_worker.start()
        self._scan_detector = self.settings.detection_model
        self._set_processing(True)
        self._set_status(
            "working",
            "Loading detector",
            "The detector is prepared once; later scans start immediately.",
        )
        self._set_progress(None, indeterminate=True)
        self.status_stats.configure(text="")

    def _handle_scan_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "scan_progress":
            _, fraction, done, total, eta = event
            self._set_progress(max(0.0, min(1.0, float(fraction))))
            self._set_status("working", "Scanning mosaics", "Sampling one frame per second.")
            stats = f"{done}/{total} samples"
            if done:
                stats += f" · ETA {fmt_time(eta, tenths=False)}"
            self.status_stats.configure(text=stats)
        elif kind == "scan_done":
            _, result, meta = event
            self._scan_worker = None
            self.scan = result
            self._scan_detector = self.settings.detection_model
            self.scan_segments = engine.segments_for_scan(result, self.settings.threshold)
            self.selected_ranges = set(range(len(self.scan_segments)))
            self._set_progress(1.0)
            self._set_processing(False)
            self._rebuild_ranges(self.scan_segments)
            self.timeline.set_data(
                times=result.times,
                scores=result.scores,
                threshold=self.settings.threshold,
                selected=self.selected_ranges,
                playhead=self.current_time,
                duration=result.duration,
            )
            self._update_scan_summary()
            self._update_restore_summary()
            count = len(self.scan_segments)
            if count:
                self.scan_pill.set(f"{count} RANGE{'S' if count != 1 else ''}", "accent")
                self.scan_btn.configure(text="Rescan")
                self._set_status(
                    "success",
                    "Scan complete",
                    f"Found {count} mosaic range{'s' if count != 1 else ''} across {fmt_time(result.duration)}. "
                    "Adjust the confidence slider or the range list.",
                )
                self._append_log("INFO", f"Scan found {count} ranges")
                self._notify(f"Scan complete: {count} range{'s' if count != 1 else ''}.")
            else:
                self.scan_pill.set("NO MOSAICS", "warning")
                self.scan_btn.configure(text="Rescan")
                self._set_status(
                    "warning",
                    "No mosaic regions found",
                    "Try lowering the confidence, or restore the whole video instead.",
                )
                self._append_log("WARNING", "Scan found no mosaic ranges")
                self.settings.scope = "whole"
                self.scope_seg.set("Whole video")
                self._notify("No mosaic regions found; switched to whole-video scope.", "warning")
            self.status_stats.configure(
                text=f"{len(result.times)} samples · {fmt_time(result.duration)} · threshold {self.settings.threshold:.2f}"
            )
            self._update_start_state()
        elif kind == "scan_canceled":
            self._scan_worker = None
            self._set_processing(False)
            self._set_progress(0)
            self.scan_pill.set("CANCELED", "neutral")
            self._set_status("warning", "Scan canceled", "Nothing was changed.")
            self.status_stats.configure(text="")
            self._append_log("WARNING", "Scan canceled")
            self._update_start_state()
        elif kind == "scan_error":
            self._scan_worker = None
            self._set_processing(False)
            self._set_progress(0)
            message = event[1]
            self.scan_pill.set("SCAN FAILED", "error")
            self._set_status("error", "Scan failed", message)
            self._append_log("ERROR", f"Scan failed: {message}")
            self._update_start_state()
            messagebox.showerror("Mosaic scan failed", message, parent=self)

    # ----------------------------------------------------------------- restoring

    def _start_restore(self) -> None:
        if self._processing or self.media is None:
            return
        scope = self.settings.scope
        segments = ()
        if scope == "selected":
            if not self.scan_segments:
                self._notify("Run a scan first, or choose whole-video scope.", "warning")
                return
            segments = tuple(
                self.scan_segments[index]
                for index in sorted(self.selected_ranges)
                if 0 <= index < len(self.scan_segments)
            )
            if not segments:
                self._notify("Select at least one range to restore.", "warning")
                return
        output = engine.build_output_path(self.media.path, self.settings, scope=scope)
        self._stop_playback()
        self.compare = False
        self.compare_seg.configure(state="disabled")
        self.compare_seg.set("Original")
        self.compare_bar.grid_remove()
        self._preview_pill.set("SOURCE", "accent")
        self._hide_output_actions()
        self.output_path = None
        self._restore_worker = engine.RestoreWorker(
            self.media.path,
            copy.deepcopy(self.settings),
            self.queue,
            output_path=output,
            segments=segments,
            scope=scope,
        )
        self._restore_worker.start()
        self._set_processing(True)
        self._set_status(
            "working",
            "Preparing models",
            f"Writing to {output.name}. The app loads BasicVSR++ and prepares the detector.",
        )
        self._set_progress(None, indeterminate=True)
        self.status_stats.configure(text="")
        self._append_log(
            "INFO",
            f"Starting restoration ({scope}) -> {output}",
        )

    def _handle_restore_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "restore_progress":
            _, percent, fps, eta, done, total, stage = event
            self._set_progress(max(0.0, min(1.0, percent / 100.0)))
            detail = "Restoring mosaic ranges with BasicVSR++."
            if percent >= 99.5:
                detail = "Finishing the file and muxing audio."
            self._set_status("working", "Restoring", detail)
            pieces = []
            if fps:
                pieces.append(f"{fps:.1f} fps")
            if eta:
                pieces.append(f"ETA {fmt_time(eta, tenths=False)}")
            if total:
                pieces.append(f"{done}/{total} frames")
            if percent:
                pieces.append(f"{percent:.0f}%")
            self.status_stats.configure(text="  ·  ".join(pieces))
        elif kind == "restore_done":
            _, path, elapsed, scope = event
            self._restore_worker = None
            self.output_path = Path(path)
            self._set_processing(False)
            self._set_progress(1.0)
            self.compare_seg.configure(state="normal")
            self._show_output_actions()
            self.status_stats.configure(
                text=f"Finished in {fmt_time(elapsed, tenths=False)} · {fmt_bytes(self.output_path.stat().st_size)}"
            )
            self._set_status(
                "success",
                "Restoration complete",
                f"Saved {self.output_path.name}. Compare the result with the source.",
            )
            self._append_log("INFO", f"Restoration complete: {self.output_path} in {elapsed:.1f}s")
            self._notify("Restoration complete. Showing the before/after view.", "success")
            self._update_start_state()
            self._preview_pill.set("RESTORED", "success")
            self._show_compare(True)
        elif kind == "restore_error":
            _, message, detail = event
            self._restore_worker = None
            self.output_path = None
            self._set_processing(False)
            self._set_progress(0)
            self._set_status("error", "Restoration failed", message)
            self.status_stats.configure(text="")
            self._append_log("ERROR", f"Restoration failed: {message}\n{detail}")
            self._update_start_state()
            messagebox.showerror("Restoration failed", message, parent=self)
        elif kind == "restore_canceled":
            self._restore_worker = None
            self.output_path = None
            self._set_processing(False)
            self._set_progress(0)
            self._set_status(
                "warning",
                "Restoration canceled",
                "The partial output was removed. Your source file is untouched.",
            )
            self.status_stats.configure(text="")
            self._append_log("WARNING", "Restoration canceled; partial output removed")
            self._update_start_state()

    # ---------------------------------------------------------------- compare

    def _show_compare(self, active: bool) -> None:
        if self.output_path is None:
            if active:
                self._notify("Restore a video first to unlock comparison.", "warning")
            return
        self.compare = bool(active)
        self.compare_seg.set("Compare" if active else "Original")
        self.compare_bar.grid() if active else self.compare_bar.grid_remove()
        self._preview_pill.set("RESTORED" if active else "SOURCE", "success" if active else "accent")
        if self._playing:
            self._start_playback(self.current_time)
        else:
            self._request_static(immediate=True)
        if active:
            self._notify("Drag the wipe slider or switch between before/after modes.")

    def _on_compare_seg(self, value: str) -> None:
        self._show_compare(value == "Compare")

    def _on_compare_mode(self, value: str) -> None:
        self.compare_mode = "wipe" if value == "Wipe" else "side"
        if self.compare_mode == "wipe":
            self.wipe_label.grid()
            self.wipe_slider.grid()
        else:
            self.wipe_label.grid_remove()
            self.wipe_slider.grid_remove()
        if self._playing:
            self._start_playback(self.current_time)
        else:
            self._request_static(immediate=True)

    def _on_wipe(self, value: float) -> None:
        self.wipe = max(0.02, min(0.98, float(value)))
        self.wipe_label.configure(text=f"Wipe {self.wipe * 100:.0f}%")
        if self._wipe_after is not None:
            self.after_cancel(self._wipe_after)
        self._wipe_after = self.after(180, self._apply_wipe)

    def _apply_wipe(self) -> None:
        self._wipe_after = None
        if self._playing:
            self._start_playback(self.current_time)
        else:
            self._request_static()

    # ----------------------------------------------------------------- playback

    @property
    def _processing(self) -> bool:
        return self._scan_worker is not None or self._restore_worker is not None

    def _canvas_size(self) -> tuple[int, int]:
        width = self.preview_canvas.winfo_width()
        height = self.preview_canvas.winfo_height()
        if width < 120 or height < 80:
            return 860, 480
        return max(320, width - 8), max(180, height - 8)

    def _on_canvas_resize(self, _event=None) -> None:
        if self.media is None:
            self._draw_placeholder("Import a video to preview the source and restored result.")
            return
        if self._playing:
            if self._resize_after is not None:
                self.after_cancel(self._resize_after)
            self._resize_after = self.after(320, self._restart_after_resize)
        else:
            self._request_static()

    def _restart_after_resize(self) -> None:
        self._resize_after = None
        if self._playing:
            self._start_playback(self.current_time)
        else:
            self._request_static(immediate=True)

    def _request_static(self, immediate: bool = False) -> None:
        if self.media is None:
            return
        self._static_gen += 1
        generation = self._static_gen
        if self._static_after is not None:
            self.after_cancel(self._static_after)
            self._static_after = None
        delay = 0 if immediate else 90
        self._static_after = self.after(delay, lambda: self._load_static(generation))

    def _load_static(self, generation: int) -> None:
        self._static_after = None
        if self.media is None or generation != self._static_gen:
            return
        if not self.compare:
            mode = "original"
            restored = None
        else:
            mode = self.compare_mode
            restored = self.output_path
        width, height = self._canvas_size()
        source = self.media.path
        seconds = self.current_time
        wipe = self.wipe
        queue_ = self.queue

        def work() -> None:
            try:
                image = media.load_static_frame(
                    source,
                    restored,
                    seconds,
                    mode=mode,
                    wipe=wipe,
                    width=width,
                    height=height,
                )
                queue_.put(("static_frame", generation, image, seconds))
            except Exception as exc:  # noqa: BLE001 - surfaced in the log
                queue_.put(("static_error", generation, str(exc)))

        threading.Thread(target=work, name="VideoRefinerFrame", daemon=True).start()

    def _show_image(self, image) -> None:
        if image is None:
            self._draw_placeholder("No frame available at this position.")
            return
        self._photo = ImageTk.PhotoImage(image)
        self.preview_canvas.delete("all")
        width = self.preview_canvas.winfo_width()
        height = self.preview_canvas.winfo_height()
        self.preview_canvas.create_image(width // 2, height // 2, image=self._photo, anchor="center")
        if self.compare and self.output_path is not None:
            self._draw_compare_labels()

    def _draw_compare_labels(self) -> None:
        if self.compare_mode == "side":
            self._canvas_tag(10, 10, "ORIGINAL", "w")
            self._canvas_tag(self.preview_canvas.winfo_width() - 10, 10, "RESTORED", "e")
        else:
            self._canvas_tag(10, 10, "ORIGINAL", "w")
            self._canvas_tag(self.preview_canvas.winfo_width() - 10, 10, "RESTORED", "e")

    def _canvas_tag(self, x: int, y: int, text: str, anchor: str) -> None:
        self.preview_canvas.create_rectangle(
            x - 2 if anchor == "w" else x - 72,
            y - 2,
            x + 64 if anchor == "w" else x + 2,
            y + 16,
            fill="#0B0D13",
            outline="",
        )
        self.preview_canvas.create_text(
            x + 4 if anchor == "w" else x - 4,
            y + 7,
            text=text,
            anchor=anchor,
            fill="#E5E7EB",
            font=sans(9, "bold"),
        )

    def _draw_placeholder(self, text: str) -> None:
        self.preview_canvas.delete("all")
        width = max(200, self.preview_canvas.winfo_width())
        height = max(120, self.preview_canvas.winfo_height())
        cx, cy = width // 2, height // 2
        self.preview_canvas.create_rectangle(
            cx - 23,
            cy - 44,
            cx + 23,
            cy + 4,
            outline=C.PREVIEW_MUTED,
            width=2,
        )
        self.preview_canvas.create_polygon(
            cx - 6, cy - 28, cx - 6, cy - 12, cx + 8, cy - 20,
            fill=C.PREVIEW_MUTED, outline="",
        )
        self.preview_canvas.create_text(
            cx,
            cy + 28,
            text=text,
            fill="#9CA3AF",
            font=sans(11),
            width=max(260, width - 80),
            justify="center",
        )

    def _toggle_play(self) -> None:
        if self.media is None:
            return
        if self._playing:
            self._stop_playback()
            self._request_static(immediate=True)
            return
        if self.current_time >= self.media.duration - 0.05:
            self.current_time = 0.0
        self._start_playback(self.current_time)

    def _start_playback(self, seconds: float) -> None:
        if self.media is None:
            return
        self._stop_playback(update_ui=False)
        width, height = self._canvas_size()
        mode = "original"
        restored = None
        if self.compare and self.output_path is not None:
            mode = self.compare_mode
            restored = self.output_path
        session = media.PlaybackSession(
            self.media.path,
            restored,
            start=seconds,
            mode=mode,
            wipe=self.wipe,
            width=width,
            height=height,
            events=self.queue,
        )
        self._playback = session
        self._playing = True
        self._last_play_time = seconds
        self.play_btn.configure(text="❚❚")
        session.start()

    def _stop_playback(self, update_ui: bool = True) -> None:
        session, self._playback = self._playback, None
        if session is not None:
            try:
                session.stop()
            except Exception:
                pass
        self._playing = False
        if update_ui:
            self.play_btn.configure(text="▶")
            self._set_time(self._last_play_time)

    def _on_slider_press(self, _event=None) -> None:
        self._resume_after_seek = self._playing
        if self._playing:
            self._stop_playback(update_ui=False)

    def _on_slider(self, value: float) -> None:
        if self._suppress_slider or self.media is None:
            return
        self.current_time = max(0.0, min(self.media.duration, float(value)))
        self._set_time(self.current_time)
        self.timeline.set_playhead(self.current_time)
        if self._seek_after is not None:
            self.after_cancel(self._seek_after)
        self._seek_after = self.after(110, self._request_static)

    def _on_slider_release(self, _event=None) -> None:
        if self._resume_after_seek:
            self._resume_after_seek = False
            self._start_playback(self.current_time)

    def _seek_from_timeline(self, seconds: float) -> None:
        if self.media is None:
            return
        was_playing = self._playing
        if was_playing:
            self._stop_playback(update_ui=False)
        self.current_time = max(0.0, min(self.media.duration, float(seconds)))
        self._set_time(self.current_time)
        self.timeline.set_playhead(self.current_time)
        if was_playing:
            self._start_playback(self.current_time)
        else:
            self._request_static(immediate=True)

    def _set_time(self, seconds: float) -> None:
        self._suppress_slider = True
        try:
            self.slider.set(max(0.0, min(seconds, self.media.duration if self.media else seconds)))
        finally:
            self._suppress_slider = False
        self.time_label.configure(text=fmt_time(seconds))

    # ------------------------------------------------------------------- scan UI

    def _rebuild_ranges(self, segments) -> None:
        for child in self.range_list.winfo_children():
            child.destroy()
        self._range_checks = []
        if not segments:
            self._range_placeholder = ctk.CTkLabel(
                self.range_list,
                text="No ranges selected.",
                font=sans(10),
                text_color=C.TEXT_MUTED,
                anchor="w",
            )
            self._range_placeholder.grid(row=0, column=0, sticky="w", padx=6, pady=7)
            return
        limit = 80
        for index, segment in enumerate(segments[:limit]):
            variable = tk.BooleanVar(value=index in self.selected_ranges)
            label = f"{fmt_time(segment.start)} – {fmt_time(segment.end)}"
            check = ctk.CTkCheckBox(
                self.range_list,
                text=label,
                variable=variable,
                onvalue=True,
                offvalue=False,
                command=lambda i=index, v=variable: self._on_range_toggle(i, v),
                width=160,
                height=24,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=4,
                border_width=1,
                fg_color=C.ACCENT,
                hover_color=C.ACCENT_HOVER,
                border_color=C.BORDER_STRONG,
                checkmark_color="#FFFFFF",
                text_color=C.TEXT_SECONDARY,
                font=sans(10),
            )
            check.grid(row=index, column=0, sticky="w", padx=8, pady=2)
            duration_label = ctk.CTkLabel(
                self.range_list,
                text=f"{segment.duration:.1f}s",
                font=sans(9),
                text_color=C.TEXT_MUTED,
                anchor="e",
                width=40,
            )
            duration_label.grid(row=index, column=1, sticky="e", padx=(0, 8))
            self._range_checks.append((variable, index))
        if len(segments) > limit:
            ctk.CTkLabel(
                self.range_list,
                text=f"+ {len(segments) - limit} more ranges (selected by default)",
                font=sans(9),
                text_color=C.TEXT_MUTED,
                anchor="w",
            ).grid(row=limit, column=0, sticky="w", padx=8, pady=4)

    def _on_range_toggle(self, index: int, variable: tk.BooleanVar) -> None:
        if variable.get():
            self.selected_ranges.add(index)
        else:
            self.selected_ranges.discard(index)
        self.timeline.set_selected(self.selected_ranges)
        self._update_scan_summary()
        self._update_restore_summary()
        self._update_start_state()

    def _select_all(self) -> None:
        self.selected_ranges = set(range(len(self.scan_segments)))
        for variable, _index in self._range_checks:
            variable.set(True)
        self.timeline.set_selected(self.selected_ranges)
        self._update_scan_summary()
        self._update_restore_summary()
        self._update_start_state()

    def _clear_selection(self) -> None:
        self.selected_ranges.clear()
        for variable, _index in self._range_checks:
            variable.set(False)
        self.timeline.set_selected(self.selected_ranges)
        self._update_scan_summary()
        self._update_restore_summary()
        self._update_start_state()

    def _update_scan_summary(self) -> None:
        total = len(self.scan_segments)
        if not total:
            if self.scan is not None:
                self.scan_summary.configure(
                    text=f"No mosaic ranges at confidence {self.settings.threshold:.2f}."
                )
            return
        seconds = sum(segment.duration for segment in self.scan_segments)
        selected = len(self.selected_ranges)
        self.scan_summary.configure(
            text=(
                f"{total} range{'s' if total != 1 else ''} · {fmt_time(seconds)} detected · "
                f"{selected} selected"
            )
        )

    def _scan_pill_reset(self) -> None:
        self.scan_btn.configure(text="Scan", state="normal" if self.media else "disabled")

    # -------------------------------------------------------------- settings UI

    def _on_detector_change(self, value: str) -> None:
        self.settings.detection_model = value
        if self.scan is not None and value != self._scan_detector:
            self._notify("Detector changed — rescan to refresh the timeline.", "warning")
            self.scan_pill.set("RESCAN NEEDED", "warning")
        self._save_later()

    def _on_threshold(self, value: float) -> None:
        self.settings.threshold = max(0.05, min(0.95, float(value)))
        self.threshold_value.configure(text=f"{self.settings.threshold:.2f}")
        if self.scan is not None:
            self.scan_segments = engine.segments_for_scan(self.scan, self.settings.threshold)
            self.selected_ranges = set(range(len(self.scan_segments)))
            self._rebuild_ranges(self.scan_segments)
            self.timeline.set_data(
                times=self.scan.times,
                scores=self.scan.scores,
                threshold=self.settings.threshold,
                selected=self.selected_ranges,
                playhead=self.current_time,
                duration=self.scan.duration,
            )
            self.scan_pill.set(
                f"{len(self.scan_segments)} RANGE{'S' if len(self.scan_segments) != 1 else ''}"
                if self.scan_segments
                else "NO MOSAICS",
                "accent" if self.scan_segments else "warning",
            )
            self._update_scan_summary()
        self._update_restore_summary()
        self._update_start_state()
        self._save_later()

    def _on_clip_size(self, value: float) -> None:
        self.settings.max_clip_size = max(12, int(round(float(value))))
        self.clip_value.configure(text=f"{self.settings.max_clip_size:.0f} frames")
        max_overlap = max(0, self.settings.max_clip_size // 2 - 1)
        if self.settings.temporal_overlap > max_overlap:
            self.settings.temporal_overlap = max_overlap
            self.overlap_slider.set(max_overlap)
            self.overlap_value.configure(text=f"{max_overlap:.0f} frames")
        self._save_later()

    def _on_overlap(self, value: float) -> None:
        max_overlap = max(0, self.settings.max_clip_size // 2 - 1)
        self.settings.temporal_overlap = min(max_overlap, max(0, int(round(float(value)))))
        self.overlap_value.configure(text=f"{self.settings.temporal_overlap:.0f} frames")
        self._save_later()

    def _on_denoise(self, value: str) -> None:
        self.settings.denoise = value.lower()
        self._save_later()

    def _on_scene(self) -> None:
        self.settings.scene_detection = bool(self.scene_switch.get())
        self._save_later()

    def _source_codec(self) -> str:
        return self.media.codec.lower() if self.media is not None else ""

    def _selected_codec_supported(self) -> bool:
        return self._source_codec() in {"h264", "hevc", "av1"}

    def _effective_codec(self) -> str:
        if self.settings.scope == "selected" and self.media is not None:
            source = self._source_codec()
            if source in {"h264", "hevc", "av1"}:
                return source
        return self.settings.codec

    def _effective_cq(self) -> int:
        limit = 63 if self._effective_codec() == "av1" else 51
        return max(1, min(limit, int(self.settings.cq)))

    def _sync_codec_controls(self) -> None:
        if not hasattr(self, "codec_seg"):
            return
        selected_scope = self.settings.scope == "selected" and self.media is not None
        source = self._source_codec()
        if selected_scope:
            display = {"h264": "H.264", "hevc": "HEVC", "av1": "AV1"}.get(source)
            if display is not None:
                self.codec_seg.set(display)
            self.codec_seg.configure(state="disabled")
            if display is None:
                text = (
                    f"Selected-range smart rendering needs H.264, HEVC, or AV1; "
                    f"this file is {source.upper() or 'unknown'}. Choose whole video."
                )
            else:
                text = (
                    f"Selected ranges use the source {source.upper()} codec. "
                    "Codec choice applies to whole-video export."
                )
            if hasattr(self, "codec_hint"):
                self.codec_hint.configure(text=text)
        else:
            self.codec_seg.set(
                {"h264": "H.264", "hevc": "HEVC", "av1": "AV1"}[self.settings.codec]
            )
            self.codec_seg.configure(state="disabled" if self._processing else "normal")
            if hasattr(self, "codec_hint"):
                self.codec_hint.configure(
                    text="Lower CQ means higher quality and a larger file."
                )
        effective = self._effective_codec()
        limit = 63 if effective == "av1" else 51
        self.cq_slider.configure(to=limit, number_of_steps=limit - 1)
        cq = self._effective_cq()
        self.cq_slider.set(cq)
        self.cq_value.configure(text=f"{cq:.0f}")

    def _on_codec(self, value: str) -> None:
        self.settings.codec = {"H.264": "h264", "HEVC": "hevc", "AV1": "av1"}[value]
        max_cq = 63 if self.settings.codec == "av1" else 51
        self.cq_slider.configure(to=max_cq, number_of_steps=max_cq - 1)
        if self.settings.cq > max_cq:
            self.settings.cq = max_cq
            self.cq_slider.set(max_cq)
            self.cq_value.configure(text=f"{max_cq:.0f}")
        self._update_restore_summary()
        self._save_later()

    def _on_cq(self, value: float) -> None:
        self.settings.cq = max(1, int(round(float(value))))
        self.cq_value.configure(text=f"{self._effective_cq():.0f}")
        self._update_restore_summary()
        self._save_later()

    def _on_suffix(self, _event=None) -> None:
        text = self.suffix_entry.get().strip() or "_restored"
        text = "".join(ch for ch in text if ch not in '<>:"/\\|?*')[:40] or "_restored"
        self.settings.suffix = text
        self._save_later()

    def _on_output_dir(self, _event=None) -> None:
        text = self.output_entry.get().strip()
        if text.casefold() == OUTPUT_DIR_PLACEHOLDER.casefold():
            text = ""
        self.settings.output_dir = text
        self._save_later()

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(
            parent=self,
            title="Choose the output folder",
            initialdir=self.settings.output_dir or (str(self.media.path.parent) if self.media else ""),
        )
        if folder:
            self.settings.output_dir = folder
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder)
            self._save_later()

    def _on_scope(self, value: str) -> None:
        self.settings.scope = "selected" if value == "Selected ranges" else "whole"
        self._sync_codec_controls()
        self._update_restore_summary()
        self._update_start_state()
        self._save_later()

    def _update_restore_summary(self) -> None:
        if self.media is None:
            self.restore_summary.configure(text="Scan a video to choose ranges.")
            return
        if self.settings.scope == "whole":
            self.restore_summary.configure(
                text=(
                    f"Whole video · {fmt_time(self.media.duration)} · "
                    f"{self.settings.codec.upper()} CQ {self._effective_cq()}"
                )
            )
            return
        if not self._selected_codec_supported():
            self.restore_summary.configure(
                text="This source codec cannot be smart-rendered by range. Choose whole video."
            )
            return
        if not self.scan_segments:
            self.restore_summary.configure(text="Run a scan to find mosaic ranges.")
            return
        selected = [
            self.scan_segments[index]
            for index in sorted(self.selected_ranges)
            if 0 <= index < len(self.scan_segments)
        ]
        if not selected:
            self.restore_summary.configure(text="Select at least one range to restore.")
            return
        seconds = sum(segment.duration for segment in selected)
        self.restore_summary.configure(
            text=(
                f"{len(selected)} range{'s' if len(selected) != 1 else ''} · "
                f"{fmt_time(seconds)} · source {self._effective_codec().upper()} "
                f"CQ {self._effective_cq()}"
            )
        )

    def _update_start_state(self) -> None:
        if self.media is None or self._processing:
            self.start_btn.configure(state="disabled")
            return
        if self.settings.scope == "selected":
            if not self._selected_codec_supported():
                self.start_btn.configure(state="disabled")
                return
            if not self.selected_ranges:
                self.start_btn.configure(state="disabled")
                return
        self.start_btn.configure(state="normal")

    def _set_processing(self, active: bool) -> None:
        for widget in self._settings_widgets:
            try:
                widget.configure(state="disabled" if active else "normal")
            except Exception:
                pass
        self.scan_btn.configure(state="disabled" if active or self.media is None else "normal")
        self.select_all_btn.configure(state="disabled" if active else "normal")
        self.clear_scan_btn.configure(state="disabled" if active else "normal")
        self._import_btn.configure(state="disabled" if active else "normal")
        if active:
            self.cancel_btn.pack(side="left", padx=(0, 4), before=self.log_btn)
            self.cancel_btn.configure(state="normal")
        else:
            self.cancel_btn.pack_forget()
        self._sync_codec_controls()
        self._update_start_state()

    def _set_status(self, kind: str, title: str, detail: str = "") -> None:
        colors = {
            "idle": C.TEXT_MUTED,
            "working": C.ACCENT,
            "success": C.SUCCESS,
            "warning": C.WARNING,
            "error": C.ERROR,
        }
        self.status_dot.itemconfigure(
            self._status_dot_id, fill=colors.get(kind, C.TEXT_MUTED)
        )
        self.status_title.configure(text=title)
        self.status_detail.configure(text=detail)

    def _set_progress(self, value: float | None, *, indeterminate: bool = False) -> None:
        try:
            if indeterminate:
                self.progress.configure(mode="indeterminate")
                self.progress.start()
                return
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(0 if value is None else max(0.0, min(1.0, float(value))))
        except Exception:
            pass

    def _show_output_actions(self) -> None:
        for widget in (self.action_compare, self.action_open, self.action_folder):
            widget.pack(side="left", padx=(4, 0))

    def _hide_output_actions(self) -> None:
        for widget in (self.action_compare, self.action_open, self.action_folder):
            widget.pack_forget()

    def _cancel_processing(self) -> None:
        if self._scan_worker is not None:
            self._scan_worker.cancel()
            self.cancel_btn.configure(state="disabled")
            self._set_status("warning", "Canceling scan", "The current sample is finishing.")
            self._append_log("WARNING", "Scan cancel requested")
        elif self._restore_worker is not None:
            self._restore_worker.cancel()
            self.cancel_btn.configure(state="disabled")
            self._set_status(
                "warning",
                "Canceling restoration",
                "Stopping workers and removing the partial output.",
            )
            self._append_log("WARNING", "Restoration cancel requested")

    # ------------------------------------------------------------------ actions

    def _open_output(self) -> None:
        if self.output_path and Path(self.output_path).is_file():
            self._open_path(self.output_path)

    def _reveal_output(self) -> None:
        if self.output_path is None:
            return
        path = Path(self.output_path)
        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
        except OSError:
            self._open_path(path.parent)

    def _open_output_folder(self) -> None:
        folder = None
        if self.output_path is not None:
            folder = Path(self.output_path).parent
        elif self.settings.output_dir:
            folder = Path(self.settings.output_dir).expanduser()
            if not folder.is_absolute() and self.media is not None:
                folder = self.media.path.parent / folder
        elif self.media is not None:
            folder = self.media.path.parent
        if folder is not None and folder.is_dir():
            self._open_path(folder)
        else:
            self._notify("Choose an output folder first.", "warning")

    def _open_path(self, path: Path) -> None:
        try:
            os.startfile(str(path))
        except OSError as exc:
            messagebox.showerror("Could not open", str(exc), parent=self)

    # -------------------------------------------------------------------- logs

    def _append_log(self, level: str, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        for line in str(message).splitlines() or [""]:
            self._log_lines.append((stamp, level.upper(), line))
        if len(self._log_lines) > 3000:
            self._log_lines = self._log_lines[-3000:]
        if self._log_text is not None:
            try:
                self._log_text.configure(state="normal")
                self._log_text.insert("end", f"[{stamp}] {level.upper():<7} {message}\n")
                self._log_text.see("end")
                self._log_text.configure(state="disabled")
            except Exception:
                self._log_text = None

    def _show_log(self) -> None:
        if self._log_window is not None and self._log_window.winfo_exists():
            self._log_window.deiconify()
            self._log_window.lift()
            return
        window = ctk.CTkToplevel(self)
        window.title("VideoRefiner Studio — log")
        window.geometry("920x540")
        window.configure(fg_color=C.BG)
        self._log_window = window
        window.grid_rowconfigure(0, weight=1)
        window.grid_columnconfigure(0, weight=1)

        frame = card(window)
        frame.grid(row=0, column=0, sticky="nsew", padx=14, pady=(14, 8))
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 6))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head,
            text="Engine log",
            font=sans(12, "bold"),
            text_color=C.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            head,
            text="Copy",
            command=self._copy_log,
            width=64,
            height=26,
            corner_radius=6,
            fg_color=C.SURFACE,
            hover_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            text_color=C.TEXT_SECONDARY,
            font=sans(10, "bold"),
        ).grid(row=0, column=1, sticky="e", padx=(0, 6))
        ctk.CTkButton(
            head,
            text="Clear",
            command=self._clear_log,
            width=64,
            height=26,
            corner_radius=6,
            fg_color=C.SURFACE,
            hover_color=C.SURFACE_ALT,
            border_width=1,
            border_color=C.BORDER,
            text_color=C.TEXT_SECONDARY,
            font=sans(10, "bold"),
        ).grid(row=0, column=2, sticky="e")

        text = tk.Text(
            frame,
            bg="#0F1117",
            fg="#D1D5DB",
            insertbackground="#D1D5DB",
            relief="flat",
            bd=0,
            wrap="word",
            font=mono(9),
            padx=12,
            pady=10,
        )
        text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        scroll = ctk.CTkScrollbar(
            frame,
            command=text.yview,
            button_color=C.BORDER_STRONG,
            button_hover_color=C.TEXT_MUTED,
        )
        scroll.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=(0, 12))
        text.configure(yscrollcommand=scroll.set)
        self._log_text = text
        text.configure(state="normal")
        for stamp, level, line in self._log_lines[-1500:]:
            text.insert("end", f"[{stamp}] {level:<7} {line}\n")
        text.see("end")
        text.configure(state="disabled")
        window.protocol("WM_DELETE_WINDOW", self._close_log)

    def _close_log(self) -> None:
        if self._log_window is not None:
            try:
                self._log_window.destroy()
            except Exception:
                pass
        self._log_window = None
        self._log_text = None

    def _copy_log(self) -> None:
        text = "\n".join(f"[{stamp}] {level:<7} {line}" for stamp, level, line in self._log_lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._notify("Log copied to the clipboard.", "success")

    def _clear_log(self) -> None:
        self._log_lines = []
        if self._log_text is not None:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", "end")
            self._log_text.configure(state="disabled")

    # ------------------------------------------------------------- environment

    def _run_env_check(self) -> None:
        if self._env_worker is not None and self._env_worker.is_alive():
            return
        try:
            self._env_placeholder.configure(text="Checking GPU, FFmpeg, TensorRT, and models…")
        except Exception:
            pass

        def work() -> None:
            try:
                report = engine.environment_report()
                self.queue.put(("env_done", report))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("env_error", str(exc)))

        self._env_worker = threading.Thread(target=work, name="VideoRefinerEnv", daemon=True)
        self._env_worker.start()

    def _handle_env(self, report: dict) -> None:
        self._env = report
        name = report.get("gpu") or "GPU unavailable"
        short = name.replace("NVIDIA ", "", 1) if name.startswith("NVIDIA ") else name
        self._gpu_name.configure(text=short)
        detail = report.get("gpu_detail") or f"PyTorch {report.get('torch', '?')}"
        self._gpu_detail.configure(text=detail)
        ok = not report.get("errors")
        self._gpu_dot.itemconfigure(
            self._gpu_dot_id,
            fill=C.SUCCESS if ok else C.WARNING,
        )
        detectors = report.get("detectors") or ["lada-yolo-v4"]
        self.detector_combo.configure(values=detectors)
        if self.settings.detection_model not in detectors:
            replacement = "lada-yolo-v4" if "lada-yolo-v4" in detectors else detectors[0]
            self.settings.detection_model = replacement
            self.detector_combo.set(replacement)
        self._rebuild_env_rows(report)
        if report.get("errors"):
            self._append_log("WARNING", "Environment check: " + "; ".join(report["errors"]))
        else:
            self._append_log(
                "INFO",
                f"Environment ready: {name}, TensorRT {report.get('tensorrt', '?')}, "
                f"{len(detectors)} detector(s)",
            )
        self._notify(
            "GPU ready." if ok else "Environment check found issues; open System.",
            "success" if ok else "warning",
        )
        self._update_start_state()

    # ------------------------------------------------------------------ events

    def _poll(self) -> None:
        handled = 0
        while handled < 160:
            try:
                event = self.queue.get_nowait()
            except queue.Empty:
                break
            handled += 1
            self._handle_event(event)
        self.after(24 if handled >= 160 else 40, self._poll)

    def _handle_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "log":
            self._append_log(event[1], event[2])
        elif kind == "status":
            if self._restore_worker is not None:
                self._set_status("working", event[1], event[2])
        elif kind.startswith("scan_"):
            self._handle_scan_event(event)
        elif kind.startswith("restore_"):
            self._handle_restore_event(event)
        elif kind == "env_done":
            self._handle_env(event[1])
        elif kind == "env_error":
            self._append_log("ERROR", f"Environment check failed: {event[1]}")
            try:
                self._env_placeholder.configure(text=f"Environment check failed: {event[1]}")
            except Exception:
                pass
        elif kind == "static_frame":
            _, generation, image, seconds = event
            if generation == self._static_gen and not self._playing:
                self._show_image(image)
                self._set_time(seconds)
                self.timeline.set_playhead(seconds)
        elif kind == "static_error":
            _, generation, message = event
            if generation == self._static_gen:
                self._append_log("ERROR", f"Preview frame failed: {message}")
        elif kind == "playback_frame":
            _, image, seconds = event
            if self._playing:
                self._show_image(image)
                self._last_play_time = seconds
                self._set_time(seconds)
                self.timeline.set_playhead(seconds)
        elif kind == "playback_end":
            self._stop_playback(update_ui=True)
        elif kind == "playback_error":
            self._stop_playback(update_ui=True)
            self._append_log("ERROR", f"Preview playback failed: {event[1]}")

    # ------------------------------------------------------------------- misc

    def _bind_shortcuts(self) -> None:
        self.bind("<space>", self._space_pressed)
        self.bind("<Control-o>", lambda _e: self._choose_video())
        self.bind("<Control-l>", lambda _e: self._show_log())
        self.bind("<Escape>", lambda _e: self._cancel_processing() if self._processing else None)

    def _space_pressed(self, _event=None):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text)):
            return None
        if self._view == "workspace" and not self._processing and self.media is not None:
            self._toggle_play()
            return "break"
        return None

    def _save_later(self) -> None:
        if self._settings_after is not None:
            self.after_cancel(self._settings_after)
        self._settings_after = self.after(600, self._save_settings)

    def _save_settings(self) -> None:
        self._settings_after = None
        self.settings.save()

    def _on_close(self) -> None:
        if self._processing:
            if not messagebox.askyesno(
                "Quit while processing?",
                "A job is still running. Cancel it and quit? The partial output will be removed.",
                parent=self,
            ):
                return
            if self._scan_worker is not None:
                self._scan_worker.cancel()
            if self._restore_worker is not None:
                self._restore_worker.cancel()
        self._stop_playback(update_ui=False)
        self.settings.save()
        self.destroy()


ABOUT_TEXT = f"""VideoRefiner Studio is a free, offline desktop front end for Jasna, an open-source mosaic detection and restoration engine.

WHAT IT DOES
• Samples a video once per second to find mosaic-censored regions.
• Restores selected ranges (or the whole video) with BasicVSR++ on the local NVIDIA GPU.
• Preserves the source audio and never overwrites the source file.
• Smart-renders ranges: only the restored ranges are re-encoded, untouched scenes are streamed from the source.

WHAT IT DOES NOT DO
• No cloud processing, telemetry, accounts, or paid API calls.
• No LTX, UNet 4x, or SD 1.5 models. Those are separate supporter/activation models and are not part of this build.
• No audio preview playback; the audio is decoded and muxed into the export, not played in the comparison view.

LICENSES
VideoRefiner Studio is licensed under AGPL-3.0-only because it incorporates Jasna (AGPL-3.0-only). The complete license is in LICENSE and the attribution summary is in NOTICE and THIRD_PARTY_NOTICES.md.
• Jasna: Copyright 2026 Kruk2 and contributors — {JASNA_URL}
• Lada models: AGPL-3.0 — {LADA_URL}
• RF-DETR architecture: Apache-2.0 — {RF_DETR_URL}
• BasicVSR++ / MMagic components: Apache-2.0, as documented in vendor/jasna.
• FFmpeg, PyAV, PyTorch, TensorRT, CustomTkinter, and other dependencies keep their own licenses.

PRIVACY
All video decoding, detection, restoration, encoding, and comparison happen on this computer. The app only writes the output file and its own settings under %LOCALAPPDATA%\\VideoRefinerStudio.

Version {__version__}
"""
