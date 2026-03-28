from __future__ import annotations

import signal
from datetime import datetime

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSColor,
    NSFont,
    NSMakeRect,
    NSScreen,
    NSTextField,
    NSVisualEffectView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
)
from PyObjCTools import AppHelper

from pm.overlay.data import OverlayProject, fetch_overlay_data

WINDOW_WIDTH = 300
ROW_HEIGHT = 44
HEADER_HEIGHT = 30
FOOTER_HEIGHT = 24
PADDING = 12
CORNER_RADIUS = 12
POLL_INTERVAL = 30.0

STATUS_COLORS = {
    "ok": (0.35, 0.78, 0.35, 1.0),
    "warn": (1.0, 0.75, 0.2, 1.0),
    "error": (1.0, 0.3, 0.3, 1.0),
}


def _make_label(text, frame, font_size=12, color=None, bold=False, alignment=0):
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    if bold:
        label.setFont_(NSFont.boldSystemFontOfSize_(font_size))
    else:
        label.setFont_(NSFont.systemFontOfSize_(font_size))
    if color:
        label.setTextColor_(color)
    else:
        label.setTextColor_(NSColor.whiteColor())
    label.setAlignment_(alignment)
    return label


def _status_dot(status, frame):
    dot = NSTextField.alloc().initWithFrame_(frame)
    r, g, b, a = STATUS_COLORS.get(status, STATUS_COLORS["ok"])
    dot.setStringValue_("\u25CF")
    dot.setBezeled_(False)
    dot.setDrawsBackground_(False)
    dot.setEditable_(False)
    dot.setSelectable_(False)
    dot.setFont_(NSFont.systemFontOfSize_(10))
    dot.setTextColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a))
    return dot


def _calc_window_height(project_count):
    content = max(project_count, 1) * ROW_HEIGHT
    return HEADER_HEIGHT + content + FOOTER_HEIGHT + PADDING


def _window_origin(position, width, height):
    screen = NSScreen.mainScreen()
    if screen is None:
        return (100, 100)
    frame = screen.visibleFrame()
    sx, sy = frame.origin.x, frame.origin.y
    sw, sh = frame.size.width, frame.size.height
    margin = 16
    if position == "top-right":
        return (sx + sw - width - margin, sy + sh - height - margin)
    elif position == "top-left":
        return (sx + margin, sy + sh - height - margin)
    elif position == "bottom-left":
        return (sx + margin, sy + margin)
    else:  # bottom-right
        return (sx + sw - width - margin, sy + margin)


class OverlayWindow:
    def __init__(self):
        self.window = None
        self.content_view = None
        self.labels = []
        self.footer_label = None
        self.position = "bottom-right"
        self.opacity = 70

    def create(self, projects, settings):
        self.position = settings.get("position", "bottom-right")
        self.opacity = settings.get("opacity", 70)

        height = _calc_window_height(len(projects))
        ox, oy = _window_origin(self.position, WINDOW_WIDTH, height)

        rect = NSMakeRect(ox, oy, WINDOW_WIDTH, height)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setLevel_(25)  # NSStatusWindowLevel
        self.window.setOpaque_(False)
        self.window.setAlphaValue_(self.opacity / 100.0)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setHasShadow_(True)
        self.window.setMovableByWindowBackground_(True)

        behaviors = (
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
        self.window.setCollectionBehavior_(behaviors)

        # Visual effect view for native vibrancy
        effect = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, WINDOW_WIDTH, height)
        )
        effect.setMaterial_(8)  # NSVisualEffectMaterialDark
        effect.setBlendingMode_(0)  # behind window
        effect.setState_(1)  # active
        effect.setWantsLayer_(True)
        effect.layer().setCornerRadius_(CORNER_RADIUS)
        effect.layer().setMasksToBounds_(True)

        self.content_view = effect
        self.window.setContentView_(effect)

        self._build_ui(projects)
        self.window.orderFrontRegardless()

    def _build_ui(self, projects):
        for label in self.labels:
            label.removeFromSuperview()
        self.labels = []
        if self.footer_label:
            self.footer_label.removeFromSuperview()
            self.footer_label = None

        view = self.content_view
        height = view.frame().size.height
        gray = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.6, 0.6, 0.6, 1.0)

        # Header
        header = _make_label(
            "PPM",
            NSMakeRect(PADDING, height - HEADER_HEIGHT - 2, WINDOW_WIDTH - PADDING * 2, 20),
            font_size=13,
            bold=True,
        )
        view.addSubview_(header)
        self.labels.append(header)

        # Separator line (thin)
        sep = NSTextField.alloc().initWithFrame_(
            NSMakeRect(PADDING, height - HEADER_HEIGHT - 4, WINDOW_WIDTH - PADDING * 2, 1)
        )
        sep.setBezeled_(False)
        sep.setEditable_(False)
        sep.setSelectable_(False)
        sep.setDrawsBackground_(True)
        sep.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.15)
        )
        sep.setStringValue_("")
        view.addSubview_(sep)
        self.labels.append(sep)

        if not projects:
            empty = _make_label(
                "No project data",
                NSMakeRect(PADDING, height - HEADER_HEIGHT - ROW_HEIGHT, WINDOW_WIDTH - PADDING * 2, 20),
                font_size=11,
                color=gray,
            )
            view.addSubview_(empty)
            self.labels.append(empty)
        else:
            y_offset = height - HEADER_HEIGHT - 8
            for proj in projects:
                y_offset -= 4
                # Status dot + project name
                dot = _status_dot(proj.status, NSMakeRect(PADDING, y_offset - 16, 14, 16))
                view.addSubview_(dot)
                self.labels.append(dot)

                name_label = _make_label(
                    proj.name,
                    NSMakeRect(PADDING + 14, y_offset - 16, 170, 16),
                    font_size=12,
                    bold=True,
                )
                view.addSubview_(name_label)
                self.labels.append(name_label)

                time_label = _make_label(
                    proj.last_activity,
                    NSMakeRect(WINDOW_WIDTH - PADDING - 90, y_offset - 16, 90, 16),
                    font_size=10,
                    color=gray,
                    alignment=2,  # right-aligned
                )
                view.addSubview_(time_label)
                self.labels.append(time_label)

                # Summary line
                summary_text = proj.summary
                if len(summary_text) > 40:
                    summary_text = summary_text[:38] + "..."
                summary_label = _make_label(
                    summary_text,
                    NSMakeRect(PADDING + 14, y_offset - 32, WINDOW_WIDTH - PADDING * 2 - 14, 14),
                    font_size=10,
                    color=gray,
                )
                view.addSubview_(summary_label)
                self.labels.append(summary_label)

                y_offset -= ROW_HEIGHT

        # Footer
        now_str = datetime.now().strftime("%H:%M:%S")
        self.footer_label = _make_label(
            f"Updated {now_str}",
            NSMakeRect(PADDING, 6, WINDOW_WIDTH - PADDING * 2, 14),
            font_size=9,
            color=gray,
            alignment=2,  # right-aligned
        )
        view.addSubview_(self.footer_label)
        self.labels.append(self.footer_label)

    def update(self, projects, settings):
        if self.window is None:
            return

        new_height = _calc_window_height(len(projects))
        old_frame = self.window.frame()

        # Reposition if height changed
        if abs(old_frame.size.height - new_height) > 1:
            self.position = settings.get("position", self.position)
            ox, oy = _window_origin(self.position, WINDOW_WIDTH, new_height)
            self.window.setFrame_display_(
                NSMakeRect(ox, oy, WINDOW_WIDTH, new_height), True
            )
            self.content_view.setFrame_(NSMakeRect(0, 0, WINDOW_WIDTH, new_height))

        opacity = settings.get("opacity", self.opacity)
        if opacity != self.opacity:
            self.opacity = opacity
            self.window.setAlphaValue_(self.opacity / 100.0)

        self._build_ui(projects)


_overlay = None


def _poll_and_update(_timer=None):
    global _overlay
    if _overlay is None:
        return
    projects, settings = fetch_overlay_data()
    _overlay.update(projects, settings)


def main():
    global _overlay

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    projects, settings = fetch_overlay_data()

    _overlay = OverlayWindow()
    _overlay.create(projects, settings)

    # Poll for data updates using AppHelper.callLater
    def _schedule_poll():
        _poll_and_update()
        AppHelper.callLater(POLL_INTERVAL, _schedule_poll)

    AppHelper.callLater(POLL_INTERVAL, _schedule_poll)

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, lambda *_: AppHelper.stopEventLoop())
    signal.signal(signal.SIGTERM, lambda *_: AppHelper.stopEventLoop())

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
