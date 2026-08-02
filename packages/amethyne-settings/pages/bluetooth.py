from gi.repository import Gtk

from pages.base import SettingsGroup, SettingsPage


class BluetoothPage(SettingsPage):
    def __init__(self) -> None:
        super().__init__(
            "Bluetooth",
            "Manage Bluetooth devices and visibility.",
        )

        bluetooth_group = SettingsGroup("Bluetooth")

        enabled = Gtk.Switch()

        bluetooth_group.add_row(
            "Bluetooth",
            "Enable Bluetooth hardware.",
            enabled,
        )

        bluetooth_group.add_row(
            "Devices",
            "View paired and available devices.",
        )

        self.append(bluetooth_group)
