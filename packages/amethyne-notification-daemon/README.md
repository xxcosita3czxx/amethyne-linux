# Amethyne Notification Daemon

A small Python/GTK notification daemon for Amethyne Linux.

On Wayland, notification windows use `gtk4-layer-shell` so Hyprland treats them as overlay surfaces instead of normal tiled windows. On X11, the daemon intentionally falls back to normal GTK windows for debugging.

It implements the standard Freedesktop notification D-Bus service:

```text
org.freedesktop.Notifications
```

## Runtime dependencies

```text
python
python-gobject
gtk4
gtk4-layer-shell  # Wayland mode only
```

## Run from source

```bash
python3 main.py
```

In another terminal, test it with:

```bash
notify-send "Hello from Amethyne" "This notification came through org.freedesktop.Notifications"
```

## Implemented

- `Notify`
- `CloseNotification`
- `GetCapabilities`
- `GetServerInformation`
- `NotificationClosed` signal
- `ActionInvoked` signal
- Basic notification expiry
- Basic action buttons
- Wayland layer-shell overlay windows
- X11 normal-window debug fallback
- Top-right anchoring on Wayland
- Basic stacked notification positioning on Wayland

## Current limitations

This is still an early prototype. In X11 sessions, notifications are normal debug windows. In Wayland sessions, it requires `gtk4-layer-shell` and uses a fixed vertical stride for stacking notifications instead of measuring each popup's final rendered height, so mixed-size notifications may leave uneven gaps or overlap if they are very tall.

A future version should add configurable positioning, per-monitor support, history, animations, richer icon/image support, and smarter dynamic stacking.

## Build package

```bash
../../package-builder.py amethyne-notification-daemon --clean
```

The resulting pacman package is written to:

```text
packages/amethyne-notification-daemon/packages/
```
