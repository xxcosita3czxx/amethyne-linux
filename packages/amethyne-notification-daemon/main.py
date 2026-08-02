#!/usr/bin/env python3

from __future__ import annotations

import itertools
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402
except ValueError:
    LayerShell = None

USE_LAYER_SHELL = False


def configure_layer_shell_mode() -> str:
    global USE_LAYER_SHELL

    gdk_backend = os.environ.get("GDK_BACKEND", "").lower()
    if gdk_backend == "x11":
        USE_LAYER_SHELL = False
        return "X11/debug normal-window (GDK_BACKEND=x11)"

    if LayerShell is None:
        USE_LAYER_SHELL = False
        return "normal-window (Gtk4LayerShell GI bindings missing)"

    if not LayerShell.is_supported():
        display = Gdk.Display.get_default()
        display_name = display.__class__.__name__ if display is not None else "none"
        USE_LAYER_SHELL = False
        return f"normal-window (layer-shell unsupported on display {display_name})"

    USE_LAYER_SHELL = True
    return "Wayland layer-shell"

APP_ID = "cz.cosita.NotificationDaemon"
BUS_NAME = "org.freedesktop.Notifications"
OBJECT_PATH = "/org/freedesktop/Notifications"
INTERFACE_NAME = "org.freedesktop.Notifications"

INTROSPECTION_XML = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="Notify">
      <arg name="app_name" type="s" direction="in"/>
      <arg name="replaces_id" type="u" direction="in"/>
      <arg name="app_icon" type="s" direction="in"/>
      <arg name="summary" type="s" direction="in"/>
      <arg name="body" type="s" direction="in"/>
      <arg name="actions" type="as" direction="in"/>
      <arg name="hints" type="a{sv}" direction="in"/>
      <arg name="expire_timeout" type="i" direction="in"/>
      <arg name="id" type="u" direction="out"/>
    </method>
    <method name="CloseNotification">
      <arg name="id" type="u" direction="in"/>
    </method>
    <method name="GetCapabilities">
      <arg name="capabilities" type="as" direction="out"/>
    </method>
    <method name="GetServerInformation">
      <arg name="name" type="s" direction="out"/>
      <arg name="vendor" type="s" direction="out"/>
      <arg name="version" type="s" direction="out"/>
      <arg name="spec_version" type="s" direction="out"/>
    </method>
    <signal name="NotificationClosed">
      <arg name="id" type="u"/>
      <arg name="reason" type="u"/>
    </signal>
    <signal name="ActionInvoked">
      <arg name="id" type="u"/>
      <arg name="action_key" type="s"/>
    </signal>
  </interface>
</node>
"""

CLOSED_EXPIRED = 1
CLOSED_DISMISSED = 2
CLOSED_REQUESTED = 3

WINDOW_WIDTH = 360
WINDOW_MARGIN = 12
WINDOW_VERTICAL_STRIDE = 128


@dataclass
class Notification:
    id: int
    app_name: str
    app_icon: str
    summary: str
    body: str
    actions: list[str]
    hints: dict[str, Any]
    expire_timeout: int


class NotificationWindow(Gtk.ApplicationWindow):
    def __init__(self, daemon: "NotificationDaemon", notification: Notification) -> None:
        super().__init__(application=daemon.app)
        self.daemon = daemon
        self.notification = notification
        self.timeout_source_id: int | None = None

        self.set_title(notification.summary or "Notification")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(WINDOW_WIDTH, -1)
        self.add_css_class("notification-window")
        self._configure_layer_shell()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(header)

        title = Gtk.Label(label=notification.summary or notification.app_name or "Notification")
        title.add_css_class("summary")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.set_wrap(True)
        header.append(title)

        close_button = Gtk.Button(label="×")
        close_button.add_css_class("close-button")
        close_button.connect("clicked", self._on_close_clicked)
        header.append(close_button)

        if notification.body:
            body = Gtk.Label(label=notification.body)
            body.add_css_class("body")
            body.set_xalign(0)
            body.set_wrap(True)
            root.append(body)

        action_pairs = list(zip(notification.actions[0::2], notification.actions[1::2]))
        if action_pairs:
            actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            actions_box.add_css_class("actions")
            root.append(actions_box)

            for action_key, action_label in action_pairs:
                button = Gtk.Button(label=action_label)
                button.connect("clicked", self._on_action_clicked, action_key)
                actions_box.append(button)

        self.connect("close-request", self._on_close_request)
        self._schedule_expiry()

    def _configure_layer_shell(self) -> None:
        if not USE_LAYER_SHELL:
            return

        assert LayerShell is not None
        LayerShell.init_for_window(self)
        if not LayerShell.is_layer_window(self):
            raise RuntimeError("Gtk4LayerShell did not initialize this notification as a layer window")

        self.set_focusable(False)
        LayerShell.set_namespace(self, "amethyne-notification-daemon")
        LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.NONE)
        LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
        LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, False)
        LayerShell.set_anchor(self, LayerShell.Edge.LEFT, False)
        LayerShell.set_margin(self, LayerShell.Edge.TOP, WINDOW_MARGIN)
        LayerShell.set_margin(self, LayerShell.Edge.RIGHT, WINDOW_MARGIN)

    def _schedule_expiry(self) -> None:
        timeout = self.notification.expire_timeout

        if timeout == 0:
            return

        if timeout < 0:
            timeout = 5000

        self.timeout_source_id = GLib.timeout_add(timeout, self._on_expired)

    def _cancel_expiry(self) -> None:
        if self.timeout_source_id is not None:
            GLib.source_remove(self.timeout_source_id)
            self.timeout_source_id = None

    def _on_expired(self) -> bool:
        self.timeout_source_id = None
        self.daemon.close_notification(self.notification.id, CLOSED_EXPIRED)
        return GLib.SOURCE_REMOVE

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        self.daemon.close_notification(self.notification.id, CLOSED_DISMISSED)

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self.daemon.close_notification(self.notification.id, CLOSED_DISMISSED)
        return True

    def _on_action_clicked(self, _button: Gtk.Button, action_key: str) -> None:
        self.daemon.emit_action_invoked(self.notification.id, action_key)
        self.daemon.close_notification(self.notification.id, CLOSED_DISMISSED)

    def set_stack_index(self, index: int) -> None:
        if not USE_LAYER_SHELL:
            return

        assert LayerShell is not None
        LayerShell.set_margin(
            self,
            LayerShell.Edge.TOP,
            WINDOW_MARGIN + (index * WINDOW_VERTICAL_STRIDE),
        )

    def close_without_signal(self) -> None:
        self._cancel_expiry()
        self.destroy()


class NotificationDaemon:
    def __init__(self, app: Gtk.Application) -> None:
        self.app = app
        self.connection: Gio.DBusConnection | None = None
        self.registration_id: int | None = None
        self.owns_notification_bus_name = False
        self.next_id = itertools.count(1)
        self.windows: dict[int, NotificationWindow] = {}
        self.introspection = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)

    def start(self) -> None:
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        interface_info = self.introspection.interfaces[0]

        self.registration_id = self.connection.register_object(
            OBJECT_PATH,
            interface_info,
            self._handle_method_call,
            None,
            None,
        )

        request_result = self.connection.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "RequestName",
            GLib.Variant("(su)", (BUS_NAME, 0)),
            GLib.VariantType.new("(u)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        ).unpack()[0]

        # DBus RequestName replies: 1 = primary owner, 4 = already owner.
        if request_result not in (1, 4):
            raise RuntimeError(
                f"Could not own {BUS_NAME}; another notification daemon is probably running"
            )

        self.owns_notification_bus_name = True
        print(f"Acquired D-Bus name: {BUS_NAME}", flush=True)

    def stop(self) -> None:
        for notification_id in list(self.windows):
            self.close_notification(notification_id, CLOSED_REQUESTED)

        if self.connection and self.registration_id:
            self.connection.unregister_object(self.registration_id)
            self.registration_id = None

        if self.connection and self.owns_notification_bus_name:
            self.connection.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ReleaseName",
                GLib.Variant("(s)", (BUS_NAME,)),
                GLib.VariantType.new("(u)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            self.owns_notification_bus_name = False



    def _handle_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        try:
            if method_name == "Notify":
                notification_id = self._notify(parameters.unpack())
                invocation.return_value(GLib.Variant("(u)", (notification_id,)))
            elif method_name == "CloseNotification":
                notification_id = parameters.unpack()[0]
                self.close_notification(notification_id, CLOSED_REQUESTED)
                invocation.return_value(None)
            elif method_name == "GetCapabilities":
                invocation.return_value(GLib.Variant("(as)", (["actions", "body"],)))
            elif method_name == "GetServerInformation":
                invocation.return_value(
                    GLib.Variant(
                        "(ssss)",
                        (
                            "Amethyne Notification Daemon",
                            "Amethyne Linux",
                            "0.1.0",
                            "1.2",
                        ),
                    )
                )
            else:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Unknown method: {method_name}",
                )
        except Exception as error:  # pragma: no cover - defensive D-Bus boundary
            invocation.return_dbus_error(
                "cz.cosita.NotificationDaemon.Error",
                str(error),
            )

    def _notify(self, values: tuple[Any, ...]) -> int:
        (
            app_name,
            replaces_id,
            app_icon,
            summary,
            body,
            actions,
            hints,
            expire_timeout,
        ) = values

        notification_id = int(replaces_id) if replaces_id else next(self.next_id)

        if notification_id in self.windows:
            self.windows[notification_id].close_without_signal()
            del self.windows[notification_id]

        notification = Notification(
            id=notification_id,
            app_name=app_name,
            app_icon=app_icon,
            summary=summary,
            body=body,
            actions=list(actions),
            hints=dict(hints),
            expire_timeout=expire_timeout,
        )

        window = NotificationWindow(self, notification)
        self.windows[notification_id] = window
        self._reflow_windows()
        window.present()
        return notification_id

    def close_notification(self, notification_id: int, reason: int) -> None:
        window = self.windows.pop(notification_id, None)

        if window is None:
            return

        window.close_without_signal()
        self._reflow_windows()
        self.emit_notification_closed(notification_id, reason)

    def _reflow_windows(self) -> None:
        for index, window in enumerate(self.windows.values()):
            window.set_stack_index(index)

    def emit_notification_closed(self, notification_id: int, reason: int) -> None:
        if self.connection is None:
            return

        self.connection.emit_signal(
            None,
            OBJECT_PATH,
            INTERFACE_NAME,
            "NotificationClosed",
            GLib.Variant("(uu)", (notification_id, reason)),
        )

    def emit_action_invoked(self, notification_id: int, action_key: str) -> None:
        if self.connection is None:
            return

        self.connection.emit_signal(
            None,
            OBJECT_PATH,
            INTERFACE_NAME,
            "ActionInvoked",
            GLib.Variant("(us)", (notification_id, action_key)),
        )


def load_css() -> None:
    css_provider = Gtk.CssProvider()
    css_path = Path(__file__).with_name("style.gtk.css")

    if not css_path.is_file():
        return

    css_provider.load_from_path(str(css_path))
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def main() -> int:
    Gtk.init()
    load_css()

    mode = configure_layer_shell_mode()
    print(f"Starting Amethyne Notification Daemon in {mode} mode", flush=True)

    app = Gtk.Application(
        application_id=APP_ID,
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)

    daemon = NotificationDaemon(app)
    daemon.start()

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        daemon.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
