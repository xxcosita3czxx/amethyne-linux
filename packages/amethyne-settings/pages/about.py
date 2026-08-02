from pages.base import SettingsGroup, SettingsPage


class AboutPage(SettingsPage):
    def __init__(self) -> None:
        super().__init__(
            "About",
            "View system information and software versions.",
        )

        system_group = SettingsGroup("System")

        system_group.add_row(
            "Desktop environment",
            "Custom GTK desktop.",
        )

        system_group.add_row(
            "Compositor",
            "Hyprland.",
        )

        system_group.add_row(
            "Toolkit",
            "GTK 4 with PyGObject.",
        )

        self.append(system_group)
