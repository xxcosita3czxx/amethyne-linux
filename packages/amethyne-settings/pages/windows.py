from gi.repository import Gtk

from pages.base import SettingsGroup, SettingsPage


class WindowsPage(SettingsPage):
    def __init__(self) -> None:
        super().__init__(
            "Windows",
            "Configure window placement and desktop behavior.",
        )

        behavior_group = SettingsGroup("Behavior")

        floating = Gtk.Switch()
        floating.set_active(True)

        behavior_group.add_row(
            "Floating by default",
            "Open normal applications as movable windows.",
            floating,
        )

        remember_position = Gtk.Switch()
        remember_position.set_active(True)

        behavior_group.add_row(
            "Remember positions",
            "Restore window size and position when reopened.",
            remember_position,
        )

        self.append(behavior_group)

        controls_group = SettingsGroup("Window controls")

        minimize = Gtk.Switch()
        minimize.set_active(True)

        controls_group.add_row(
            "Minimize windows",
            "Allow windows to be hidden and restored from the taskbar.",
            minimize,
        )

        snapping = Gtk.Switch()
        snapping.set_active(True)

        controls_group.add_row(
            "Window snapping",
            "Snap windows to screen edges.",
            snapping,
        )

        self.append(controls_group)
