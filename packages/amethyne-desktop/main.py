#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
from ctypes import CDLL
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# gtk4-layer-shell needs to be linked before libwayland-client is pulled in by
# GTK/GDK, otherwise the GI binding can load but report layer-shell unsupported.
try:
    CDLL("libgtk4-layer-shell.so")
except OSError:
    pass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell
except ValueError:
    LayerShell = None

APP_ID = "cz.cosita.AmethyneDesktop"
CSS_PATHS = [
    Path("/usr/share/amethyne/desktop/style.gtk.css"),
    Path(__file__).with_name("style.gtk.css"),
]
DESKTOP_DIR = Path.home() / "Desktop"
CONFIG_DIR = Path.home() / ".config" / "amethyne-desktop"
CONFIG_PATH = CONFIG_DIR / "config.json"
POSITIONS_PATH = CONFIG_DIR / "desktop-positions.json"
RESERVED_AREA_POLL_SECONDS = 1
DEBUG = os.environ.get("AMETHYNE_DESKTOP_DEBUG") == "1"


@dataclass(frozen=True)
class DesktopConfig:
    padding_top: int = 28
    padding_right: int = 28
    padding_bottom: int = 28
    padding_left: int = 28
    grid_width: int = 110
    grid_height: int = 122
    icon_width: int = 96
    icon_height: int = 108
    icon_size: int = 38
    label_max_width_chars: int = 10
    label_lines: int = 2
    snap_to_grid: bool = True
    fill_direction: str = "vertical"


@dataclass(frozen=True)
class DesktopIcon:
    id: str
    label: str
    icon_name: str
    path: Path | None = None
    command: list[str] | None = None


@dataclass
class IconView:
    icon: DesktopIcon
    widget: Gtk.Widget
    grid_x: int
    grid_y: int
    pixel_x: int = 0
    pixel_y: int = 0
    drag_origin_grid_x: int = 0
    drag_origin_grid_y: int = 0
    drag_origin_pixel_x: int = 0
    drag_origin_pixel_y: int = 0


class DesktopWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app)
        self.config = self._load_config()
        self.desktop_monitor: Gio.FileMonitor | None = None
        self.reserved_margins: tuple[int, int, int, int] | None = None  # top, right, bottom, left
        self.monitor_size: tuple[int, int] | None = None
        self.selected_icon_ids: set[str] = set()
        self.icon_views: dict[str, IconView] = {}
        self.dragging_icon_id: str | None = None
        self.drag_pointer_offset: tuple[int, int] = (0, 0)
        self.drag_started = False
        self.selection_rect: Gtk.Widget | None = None
        self.selection_start: tuple[int, int] | None = None
        self.selection_bounds: tuple[int, int, int, int] | None = None
        self.selection_extend = False
        self.positions = self._load_positions()

        self.set_title("Amethyne Desktop")
        self.set_decorated(False)
        self.set_resizable(False)
        self.add_css_class("amethyne-desktop")

        self.canvas = Gtk.Fixed()
        self.canvas.set_halign(Gtk.Align.FILL)
        self.canvas.set_valign(Gtk.Align.FILL)
        self.canvas.set_hexpand(True)
        self.canvas.set_vexpand(True)
        self.canvas.add_css_class("desktop-canvas")

        background_click = Gtk.GestureClick()
        background_click.set_button(Gdk.BUTTON_PRIMARY)
        background_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        background_click.connect("pressed", self._on_background_click_pressed)
        background_click.connect("released", self._on_canvas_click_released)
        self.canvas.add_controller(background_click)

        pointer_motion = Gtk.EventControllerMotion()
        pointer_motion.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        pointer_motion.connect("motion", self._on_canvas_motion)
        self.canvas.add_controller(pointer_motion)

        self._configure_layer_shell()
        self.set_child(self.canvas)
        self._setup_desktop_monitor()
        self._update_reserved_margins()
        self._refresh_icons()
        GLib.timeout_add_seconds(RESERVED_AREA_POLL_SECONDS, self._poll_reserved_margins)

    def _configure_layer_shell(self) -> None:
        if LayerShell is None or not LayerShell.is_supported():
            print("amethyne-desktop: layer-shell unavailable, using normal window fallback", flush=True)
            return

        LayerShell.init_for_window(self)
        LayerShell.set_namespace(self, "amethyne-desktop")
        LayerShell.set_layer(self, LayerShell.Layer.BACKGROUND)
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.NONE)
        LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
        LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, True)
        LayerShell.set_anchor(self, LayerShell.Edge.LEFT, True)
        LayerShell.set_margin(self, LayerShell.Edge.TOP, 0)
        LayerShell.set_margin(self, LayerShell.Edge.RIGHT, 0)
        LayerShell.set_margin(self, LayerShell.Edge.BOTTOM, 0)
        LayerShell.set_margin(self, LayerShell.Edge.LEFT, 0)
        LayerShell.set_exclusive_zone(self, -1)

    def _setup_desktop_monitor(self) -> None:
        DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
        desktop_file = Gio.File.new_for_path(str(DESKTOP_DIR))
        try:
            self.desktop_monitor = desktop_file.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        except GLib.Error as error:
            print(f"amethyne-desktop: failed to monitor {DESKTOP_DIR}: {error.message}", flush=True)
            return

        self.desktop_monitor.connect("changed", self._on_desktop_changed)

    def _on_desktop_changed(
        self,
        _monitor: Gio.FileMonitor,
        _file: Gio.File,
        _other_file: Gio.File | None,
        _event_type: Gio.FileMonitorEvent,
    ) -> None:
        GLib.idle_add(self._refresh_icons)

    def _refresh_icons(self) -> bool:
        self.selected_icon_ids.clear()
        while child := self.canvas.get_first_child():
            self.canvas.remove(child)

        self.icon_views.clear()
        occupied: set[tuple[int, int]] = set()

        for index, icon in enumerate(self._desktop_icons()):
            grid_x, grid_y = self._grid_position_for_icon(icon, index, occupied)
            occupied.add((grid_x, grid_y))
            widget = self._build_icon(icon)
            self.icon_views[icon.id] = IconView(icon=icon, widget=widget, grid_x=grid_x, grid_y=grid_y)
            self.canvas.put(widget, 0.0, 0.0)

        self._layout_icons()
        self._save_positions()
        return GLib.SOURCE_REMOVE

    def _desktop_icons(self) -> list[DesktopIcon]:
        icons = [DesktopIcon("builtin:home", "Home", "user-home-symbolic", Path.home())]

        if not DESKTOP_DIR.is_dir():
            return icons

        for path in sorted(DESKTOP_DIR.iterdir(), key=lambda item: item.name.casefold()):
            if path.name.startswith("."):
                continue
            icon = self._icon_for_path(path)
            if icon is not None:
                icons.append(icon)

        return icons

    def _icon_for_path(self, path: Path) -> DesktopIcon | None:
        icon_id = f"file:{path.name}"
        if path.suffix == ".desktop":
            return self._desktop_entry_icon(path, icon_id)

        if path.is_dir():
            return DesktopIcon(icon_id, path.name, "folder-symbolic", path)

        return DesktopIcon(icon_id, path.name, "text-x-generic-symbolic", path)

    def _desktop_entry_icon(self, path: Path, icon_id: str) -> DesktopIcon | None:
        app_info = Gio.DesktopAppInfo.new_from_filename(str(path))
        if app_info is None:
            return DesktopIcon(icon_id, path.stem, "application-x-executable-symbolic", path)

        if app_info.get_nodisplay():
            return None

        icon_name = "application-x-executable-symbolic"
        icon = app_info.get_icon()
        if isinstance(icon, Gio.ThemedIcon):
            names = icon.get_names()
            if names:
                icon_name = names[0]

        return DesktopIcon(icon_id, app_info.get_display_name() or path.stem, icon_name, path)

    def _grid_position_for_icon(
        self,
        icon: DesktopIcon,
        index: int,
        occupied: set[tuple[int, int]],
    ) -> tuple[int, int]:
        saved = self.positions.get(icon.id)
        if isinstance(saved, dict):
            try:
                grid_x = int(saved.get("grid_x", saved.get("x", 0)))
                grid_y = int(saved.get("grid_y", saved.get("y", 0)))
                grid_x, grid_y = self._nearest_free_grid_position(max(0, grid_x), max(0, grid_y), occupied)
                self.positions[icon.id] = {"grid_x": grid_x, "grid_y": grid_y}
                return grid_x, grid_y
            except (TypeError, ValueError):
                pass

        grid_x, grid_y = self._auto_grid_position(index, occupied)
        self.positions[icon.id] = {"grid_x": grid_x, "grid_y": grid_y}
        return grid_x, grid_y

    def _auto_grid_position(self, index: int, occupied: set[tuple[int, int]]) -> tuple[int, int]:
        columns, rows = self._grid_capacity()
        columns = max(1, columns)
        rows = max(1, rows)

        if self.config.fill_direction == "horizontal":
            grid_x = index % columns
            grid_y = index // columns
        else:
            grid_x = index // rows
            grid_y = index % rows

        return self._nearest_free_grid_position(grid_x, grid_y, occupied)

    def _next_free_grid_position(
        self,
        grid_x: int,
        grid_y: int,
        occupied: set[tuple[int, int]],
    ) -> tuple[int, int]:
        columns, rows = self._grid_capacity()
        columns = max(1, columns)
        rows = max(1, rows)

        while (grid_x, grid_y) in occupied:
            if self.config.fill_direction == "horizontal":
                grid_x += 1
                if grid_x >= columns:
                    grid_x = 0
                    grid_y += 1
            else:
                grid_y += 1
                if grid_y >= rows:
                    grid_y = 0
                    grid_x += 1

        return self._nearest_free_grid_position(grid_x, grid_y, occupied)

    def _nearest_free_grid_position(
        self,
        grid_x: int,
        grid_y: int,
        occupied: set[tuple[int, int]],
    ) -> tuple[int, int]:
        grid_x, grid_y = self._clamp_grid_position(grid_x, grid_y)
        if (grid_x, grid_y) not in occupied:
            return grid_x, grid_y

        columns, rows = self._grid_capacity()
        max_radius = max(columns, rows)
        for radius in range(1, max_radius + 1):
            candidates: list[tuple[int, int]] = []
            for x in range(grid_x - radius, grid_x + radius + 1):
                candidates.append((x, grid_y - radius))
                candidates.append((x, grid_y + radius))
            for y in range(grid_y - radius + 1, grid_y + radius):
                candidates.append((grid_x - radius, y))
                candidates.append((grid_x + radius, y))

            candidates.sort(key=lambda point: abs(point[0] - grid_x) + abs(point[1] - grid_y))
            for candidate_x, candidate_y in candidates:
                clamped = self._clamp_grid_position(candidate_x, candidate_y)
                if clamped not in occupied:
                    return clamped

        return grid_x, grid_y

    def _build_icon(self, icon: DesktopIcon) -> Gtk.Widget:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.add_css_class("desktop-icon")
        root.set_size_request(self.config.icon_width, self.config.icon_height)
        root.set_halign(Gtk.Align.START)
        root.set_valign(Gtk.Align.START)
        root.set_tooltip_text(icon.label)

        image = Gtk.Image.new_from_icon_name(icon.icon_name)
        image.set_pixel_size(self.config.icon_size)
        image.set_halign(Gtk.Align.CENTER)
        root.append(image)

        label = Gtk.Label(label=icon.label)
        label.set_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_max_width_chars(self.config.label_max_width_chars)
        label.set_lines(self.config.label_lines)
        root.append(label)

        click = Gtk.GestureClick()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_icon_click_pressed, root, icon)
        click.connect("released", self._on_icon_click_released, root, icon)
        root.add_controller(click)

        return root

    def _on_icon_click_pressed(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        widget: Gtk.Widget,
        icon: DesktopIcon,
    ) -> None:
        modifiers = _gesture.get_current_event_state()
        if modifiers & Gdk.ModifierType.CONTROL_MASK:
            self._toggle_icon_selection(icon.id)
        elif modifiers & Gdk.ModifierType.SHIFT_MASK:
            self._select_icon(icon.id, extend=True)
        elif icon.id not in self.selected_icon_ids:
            self._select_icon(icon.id)

        if icon.id not in self.selected_icon_ids:
            self.dragging_icon_id = None
            return

        self.dragging_icon_id = icon.id
        self.drag_pointer_offset = (int(_x), int(_y))
        self.drag_started = False
        self._begin_selected_drag()
        if n_press >= 2:
            self.dragging_icon_id = None
            self._launch_icon(icon)

    def _on_icon_click_released(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        _widget: Gtk.Widget,
        icon: DesktopIcon,
    ) -> None:
        if self.dragging_icon_id == icon.id:
            self._finish_drag(icon.id)

    def _on_background_click_pressed(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        picked = self.canvas.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is self.canvas:
            self.dragging_icon_id = None
            modifiers = _gesture.get_current_event_state()
            self.selection_extend = bool(
                modifiers & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
            )
            if not self.selection_extend:
                self._clear_selection()
            self._begin_selection_rect(int(x), int(y))

    def _on_canvas_click_released(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        if self.selection_rect is not None:
            self._finish_selection_rect()
        elif self.dragging_icon_id is not None:
            self._finish_drag(self.dragging_icon_id)

    def _on_canvas_motion(self, _controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        if self.selection_rect is not None:
            self._update_selection_rect(int(x), int(y))
            return

        if self.dragging_icon_id is None:
            return

        view = self.icon_views.get(self.dragging_icon_id)
        if view is None:
            return

        pointer_offset_x, pointer_offset_y = self.drag_pointer_offset
        active_x, active_y = self._clamp_pixels(int(x) - pointer_offset_x, int(y) - pointer_offset_y)
        delta_x = active_x - view.drag_origin_pixel_x
        delta_y = active_y - view.drag_origin_pixel_y

        for selected_view in self._selected_views():
            new_x, new_y = self._clamp_pixels(
                selected_view.drag_origin_pixel_x + delta_x,
                selected_view.drag_origin_pixel_y + delta_y,
            )
            selected_view.pixel_x = new_x
            selected_view.pixel_y = new_y
            self.canvas.move(selected_view.widget, float(new_x), float(new_y))

        self.drag_started = True

    def _begin_selection_rect(self, x: int, y: int) -> None:
        self.selection_start = (x, y)
        self.selection_bounds = (x, y, 1, 1)
        self.selection_rect = Gtk.Box()
        self.selection_rect.add_css_class("selection-rectangle")
        self.selection_rect.set_can_target(False)
        self.selection_rect.set_size_request(1, 1)
        self.canvas.put(self.selection_rect, float(x), float(y))

    def _update_selection_rect(self, x: int, y: int) -> None:
        if self.selection_rect is None or self.selection_start is None:
            return

        start_x, start_y = self.selection_start
        rect_x = min(start_x, x)
        rect_y = min(start_y, y)
        rect_width = max(1, abs(x - start_x))
        rect_height = max(1, abs(y - start_y))
        self.selection_bounds = (rect_x, rect_y, rect_width, rect_height)
        self.selection_rect.set_size_request(rect_width, rect_height)
        self.canvas.move(self.selection_rect, float(rect_x), float(rect_y))

    def _finish_selection_rect(self) -> None:
        rect = self.selection_bounds
        selection_rect = self.selection_rect
        self.selection_rect = None
        self.selection_start = None
        self.selection_bounds = None

        if selection_rect is not None:
            self.canvas.remove(selection_rect)

        if rect is None:
            return

        rect_x, rect_y, rect_width, rect_height = rect
        if rect_width < 4 and rect_height < 4:
            if not self.selection_extend:
                self._clear_selection()
            return

        if not self.selection_extend:
            self._clear_selection()

        for icon_id, view in self.icon_views.items():
            if self._rects_intersect(
                rect_x,
                rect_y,
                rect_width,
                rect_height,
                view.pixel_x,
                view.pixel_y,
                self.config.icon_width,
                self.config.icon_height,
            ):
                self._select_icon(icon_id, extend=True)

    def _rects_intersect(
        self,
        ax: int,
        ay: int,
        aw: int,
        ah: int,
        bx: int,
        by: int,
        bw: int,
        bh: int,
    ) -> bool:
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    def _select_icon(self, icon_id: str, extend: bool = False) -> None:
        if not extend:
            self._clear_selection()

        view = self.icon_views.get(icon_id)
        if view is None:
            return

        self.selected_icon_ids.add(icon_id)
        view.widget.add_css_class("selected")

    def _toggle_icon_selection(self, icon_id: str) -> None:
        view = self.icon_views.get(icon_id)
        if view is None:
            return

        if icon_id in self.selected_icon_ids:
            self.selected_icon_ids.remove(icon_id)
            view.widget.remove_css_class("selected")
        else:
            self.selected_icon_ids.add(icon_id)
            view.widget.add_css_class("selected")

    def _clear_selection(self) -> None:
        for icon_id in list(self.selected_icon_ids):
            view = self.icon_views.get(icon_id)
            if view is not None:
                view.widget.remove_css_class("selected")
        self.selected_icon_ids.clear()

    def _launch_icon(self, icon: DesktopIcon) -> None:
        if icon.path is not None and icon.path.suffix == ".desktop":
            app_info = Gio.DesktopAppInfo.new_from_filename(str(icon.path))
            if app_info is not None:
                try:
                    app_info.launch([], None)
                    return
                except GLib.Error as error:
                    print(f"amethyne-desktop: failed to launch {icon.path}: {error.message}", flush=True)

        command = icon.command or ["xdg-open", str(icon.path or Path.home())]
        try:
            subprocess.Popen(command)
        except OSError as error:
            print(f"amethyne-desktop: failed to launch {icon.label}: {error}", flush=True)

    def _begin_selected_drag(self) -> None:
        for view in self._selected_views():
            view.drag_origin_grid_x = view.grid_x
            view.drag_origin_grid_y = view.grid_y
            view.drag_origin_pixel_x = view.pixel_x
            view.drag_origin_pixel_y = view.pixel_y

    def _finish_drag(self, icon_id: str) -> None:
        self.dragging_icon_id = None
        dragged_ids = self.selected_icon_ids if icon_id in self.selected_icon_ids else {icon_id}
        dragged_views = [self.icon_views[selected_id] for selected_id in dragged_ids if selected_id in self.icon_views]
        if not dragged_views:
            return

        occupied = self._occupied_grid_positions(excluding_icon_ids={view.icon.id for view in dragged_views})
        for view in dragged_views:
            current_x, current_y = self._current_icon_pixels(view)
            desired_grid_x, desired_grid_y = self._pixels_to_grid(current_x, current_y)
            view.grid_x, view.grid_y = self._nearest_free_grid_position(desired_grid_x, desired_grid_y, occupied)
            occupied.add((view.grid_x, view.grid_y))
            self._move_icon_view(view)
            self.positions[view.icon.id] = {"grid_x": view.grid_x, "grid_y": view.grid_y}

        self._save_positions()

    def _poll_reserved_margins(self) -> bool:
        self._update_reserved_margins()
        return GLib.SOURCE_CONTINUE

    def _update_reserved_margins(self) -> None:
        margins = self._hyprland_reserved_margins()
        if margins == self.reserved_margins:
            return

        self.reserved_margins = margins
        self._layout_icons()

    def _layout_icons(self) -> None:
        occupied: set[tuple[int, int]] = set()
        for view in self.icon_views.values():
            view.grid_x, view.grid_y = self._nearest_free_grid_position(view.grid_x, view.grid_y, occupied)
            occupied.add((view.grid_x, view.grid_y))
            self.positions[view.icon.id] = {"grid_x": view.grid_x, "grid_y": view.grid_y}
            self._move_icon_view(view)
        self.canvas.queue_resize()

    def _move_icon_view(self, view: IconView) -> None:
        x, y = self._grid_to_pixels(view.grid_x, view.grid_y)
        view.pixel_x = x
        view.pixel_y = y
        self.canvas.move(view.widget, float(x), float(y))

    def _current_icon_pixels(self, view: IconView) -> tuple[int, int]:
        return (view.pixel_x, view.pixel_y)

    def _grid_to_pixels(self, grid_x: int, grid_y: int) -> tuple[int, int]:
        top, _right, _bottom, left = self.reserved_margins or (0, 0, 0, 0)
        return (
            left + self.config.padding_left + (grid_x * self.config.grid_width),
            top + self.config.padding_top + (grid_y * self.config.grid_height),
        )

    def _pixels_to_grid(self, x: int, y: int) -> tuple[int, int]:
        top, _right, _bottom, left = self.reserved_margins or (0, 0, 0, 0)
        origin_x = left + self.config.padding_left
        origin_y = top + self.config.padding_top
        return self._clamp_grid_position(
            round((x - origin_x) / self.config.grid_width),
            round((y - origin_y) / self.config.grid_height),
        )

    def _clamp_pixels(self, x: int, y: int) -> tuple[int, int]:
        top, right, bottom, left = self.reserved_margins or (0, 0, 0, 0)
        width, height = self.monitor_size or (0, 0)
        if width <= 0 or height <= 0:
            return (max(0, x), max(0, y))

        min_x = left + self.config.padding_left
        min_y = top + self.config.padding_top
        max_x = max(min_x, width - right - self.config.padding_right - self.config.icon_width)
        max_y = max(min_y, height - bottom - self.config.padding_bottom - self.config.icon_height)
        return (min(max(x, min_x), max_x), min(max(y, min_y), max_y))

    def _selected_views(self) -> list[IconView]:
        return [
            self.icon_views[icon_id]
            for icon_id in self.selected_icon_ids
            if icon_id in self.icon_views
        ]

    def _occupied_grid_positions(
        self,
        excluding_icon_ids: set[str] | None = None,
    ) -> set[tuple[int, int]]:
        excluded = excluding_icon_ids or set()
        return {
            (view.grid_x, view.grid_y)
            for icon_id, view in self.icon_views.items()
            if icon_id not in excluded
        }

    def _clamp_grid_position(self, grid_x: int, grid_y: int) -> tuple[int, int]:
        columns, rows = self._grid_capacity()
        return (
            min(max(0, grid_x), max(0, columns - 1)),
            min(max(0, grid_y), max(0, rows - 1)),
        )

    def _grid_capacity(self) -> tuple[int, int]:
        top, right, bottom, left = self.reserved_margins or (0, 0, 0, 0)
        width, height = self.monitor_size or (1920, 1080)
        usable_width = max(1, width - left - right - self.config.padding_left - self.config.padding_right)
        usable_height = max(1, height - top - bottom - self.config.padding_top - self.config.padding_bottom)
        return (
            max(1, usable_width // max(1, self.config.grid_width)),
            max(1, usable_height // max(1, self.config.grid_height)),
        )

    def _hyprland_reserved_margins(self) -> tuple[int, int, int, int]:
        monitors = self._hyprctl_json("monitors")
        if not isinstance(monitors, list):
            self.monitor_size = None
            return (0, 0, 0, 0)

        monitor = self._active_monitor(monitors)
        if monitor is None:
            self.monitor_size = None
            return (0, 0, 0, 0)

        monitor_x = int(monitor.get("x", 0) or 0)
        monitor_y = int(monitor.get("y", 0) or 0)
        monitor_width = int(monitor.get("width", 0) or 0)
        monitor_height = int(monitor.get("height", 0) or 0)
        self.monitor_size = (monitor_width, monitor_height)

        margins = self._monitor_reserved_margins(monitor)
        layer_margins = self._layer_reserved_margins(monitor.get("name"), monitor_x, monitor_y, monitor_width, monitor_height)
        margins = tuple(max(a, b) for a, b in zip(margins, layer_margins))

        if DEBUG:
            print(f"amethyne-desktop: reserved margins top/right/bottom/left = {margins}", flush=True)
        return margins

    def _hyprctl_json(self, command: str) -> object | None:
        try:
            result = subprocess.run(
                ["hyprctl", "-j", command],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
            )
            return json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
            if DEBUG:
                print(f"amethyne-desktop: failed to query hyprctl {command}: {error}", flush=True)
            return None

    def _active_monitor(self, monitors: list[object]) -> dict[str, object] | None:
        dict_monitors = [monitor for monitor in monitors if isinstance(monitor, dict)]
        if not dict_monitors:
            return None

        for monitor in dict_monitors:
            if monitor.get("focused") is True:
                return monitor

        return dict_monitors[0]

    def _monitor_reserved_margins(self, monitor: dict[str, object]) -> tuple[int, int, int, int]:
        reserved = monitor.get("reserved")
        if not isinstance(reserved, list) or len(reserved) != 4:
            return (0, 0, 0, 0)

        values = [max(0, int(value)) for value in reserved]
        # Hyprland has used top/bottom/left/right for addreserved-style data.
        return (values[0], values[3], values[1], values[2])

    def _layer_reserved_margins(
        self,
        monitor_name: object,
        monitor_x: int,
        monitor_y: int,
        monitor_width: int,
        monitor_height: int,
    ) -> tuple[int, int, int, int]:
        layers = self._hyprctl_json("layers")
        if not isinstance(layers, dict) or not isinstance(monitor_name, str):
            return (0, 0, 0, 0)

        monitor_layers = layers.get(monitor_name)
        if not isinstance(monitor_layers, dict):
            return (0, 0, 0, 0)

        top = right = bottom = left = 0
        for layer in self._iter_layer_surfaces(monitor_layers):
            exclusive_zone = int(layer.get("exclusiveZone", layer.get("exclusive", 0)) or 0)
            if exclusive_zone <= 0:
                continue

            geometry = layer.get("geometry")
            if not isinstance(geometry, dict):
                continue

            x = int(geometry.get("x", 0) or 0)
            y = int(geometry.get("y", 0) or 0)
            width = int(geometry.get("w", geometry.get("width", 0)) or 0)
            height = int(geometry.get("h", geometry.get("height", 0)) or 0)
            if width <= 0 or height <= 0:
                continue

            threshold = 8
            is_horizontal = width >= height
            if is_horizontal:
                if y <= monitor_y + threshold:
                    top = max(top, height, exclusive_zone)
                if y + height >= monitor_y + monitor_height - threshold:
                    bottom = max(bottom, height, exclusive_zone)
            else:
                if x <= monitor_x + threshold:
                    left = max(left, width, exclusive_zone)
                if x + width >= monitor_x + monitor_width - threshold:
                    right = max(right, width, exclusive_zone)

        return (top, right, bottom, left)

    def _iter_layer_surfaces(self, monitor_layers: dict[str, object]):
        levels = monitor_layers.get("levels", monitor_layers)
        if not isinstance(levels, dict):
            return

        for surfaces in levels.values():
            if isinstance(surfaces, list):
                for surface in surfaces:
                    if isinstance(surface, dict):
                        yield surface

    def _load_config(self) -> DesktopConfig:
        defaults = DesktopConfig()
        data: dict[str, Any] = {}
        if CONFIG_PATH.is_file():
            try:
                loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError) as error:
                print(f"amethyne-desktop: failed to read {CONFIG_PATH}: {error}", flush=True)

        config = DesktopConfig(
            padding_top=self._config_int(data, "padding_top", defaults.padding_top, minimum=0),
            padding_right=self._config_int(data, "padding_right", defaults.padding_right, minimum=0),
            padding_bottom=self._config_int(data, "padding_bottom", defaults.padding_bottom, minimum=0),
            padding_left=self._config_int(data, "padding_left", defaults.padding_left, minimum=0),
            grid_width=self._config_int(data, "grid_width", defaults.grid_width),
            grid_height=self._config_int(data, "grid_height", defaults.grid_height),
            icon_width=self._config_int(data, "icon_width", defaults.icon_width),
            icon_height=self._config_int(data, "icon_height", defaults.icon_height),
            icon_size=self._config_int(data, "icon_size", defaults.icon_size),
            label_max_width_chars=self._config_int(data, "label_max_width_chars", defaults.label_max_width_chars),
            label_lines=self._config_int(data, "label_lines", defaults.label_lines),
            snap_to_grid=bool(data.get("snap_to_grid", defaults.snap_to_grid)),
            fill_direction=str(data.get("fill_direction", defaults.fill_direction)),
        )
        self._write_default_config(config)
        return config

    def _config_int(self, data: dict[str, Any], key: str, default: int, minimum: int = 1) -> int:
        try:
            return max(minimum, int(data.get(key, default)))
        except (TypeError, ValueError):
            return default

    def _write_default_config(self, config: DesktopConfig) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_PATH.exists():
            return

        data = {
            "padding_top": config.padding_top,
            "padding_right": config.padding_right,
            "padding_bottom": config.padding_bottom,
            "padding_left": config.padding_left,
            "grid_width": config.grid_width,
            "grid_height": config.grid_height,
            "icon_width": config.icon_width,
            "icon_height": config.icon_height,
            "icon_size": config.icon_size,
            "label_max_width_chars": config.label_max_width_chars,
            "label_lines": config.label_lines,
            "snap_to_grid": config.snap_to_grid,
            "fill_direction": config.fill_direction,
        }
        try:
            CONFIG_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"amethyne-desktop: failed to write {CONFIG_PATH}: {error}", flush=True)

    def _load_positions(self) -> dict[str, dict[str, int]]:
        try:
            with POSITIONS_PATH.open("r", encoding="utf-8") as positions_file:
                data = json.load(positions_file)
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}

        positions = data.get("positions", data)
        return positions if isinstance(positions, dict) else {}

    def _save_positions(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "positions": self.positions,
        }
        try:
            with POSITIONS_PATH.open("w", encoding="utf-8") as positions_file:
                json.dump(data, positions_file, indent=2, sort_keys=True)
                positions_file.write("\n")
        except OSError as error:
            print(f"amethyne-desktop: failed to save {POSITIONS_PATH}: {error}", flush=True)


def load_css() -> None:
    css_path = next((path for path in CSS_PATHS if path.is_file()), None)
    if css_path is None:
        return

    provider = Gtk.CssProvider()
    provider.load_from_path(str(css_path))
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def main() -> int:
    app = Gtk.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)

    def on_activate(application: Gtk.Application) -> None:
        load_css()
        window = DesktopWindow(application)
        window.present()

    app.connect("activate", on_activate)
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
