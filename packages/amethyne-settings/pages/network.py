from gi.repository import Gtk

from pages.base import SettingsGroup, SettingsPage


class NetworkPage(SettingsPage):
    def __init__(self) -> None:
        super().__init__(
            "Network",
            "Configure wired, wireless and VPN connections.",
        )

        network_group = SettingsGroup("Connections")

        wifi = Gtk.Switch()
        wifi.set_active(True)

        network_group.add_row(
            "Wi-Fi",
            "Enable wireless networking.",
            wifi,
        )

        airplane = Gtk.Switch()

        network_group.add_row(
            "Airplane mode",
            "Disable wireless communication.",
            airplane,
        )

        self.append(network_group)
