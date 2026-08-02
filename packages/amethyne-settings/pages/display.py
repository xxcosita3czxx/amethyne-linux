from pages.base import SettingsGroup, SettingsPage


class DisplayPage(SettingsPage):
    def __init__(self) -> None:
        super().__init__(
            "Displays",
            "Configure monitors, scaling and orientation.",
        )

        display_group = SettingsGroup("Display configuration")

        display_group.add_row(
            "Primary display",
            "Choose which display contains the main panel.",
        )

        display_group.add_row(
            "Scaling",
            "Adjust the size of text and interface elements.",
        )

        display_group.add_row(
            "Refresh rate",
            "Configure the display refresh rate.",
        )

        self.append(display_group)
