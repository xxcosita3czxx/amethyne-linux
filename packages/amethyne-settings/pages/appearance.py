from gi.repository import Gtk

from pages.base import SettingsGroup, SettingsPage


class AppearancePage(SettingsPage):
    def __init__(self) -> None:
        super().__init__(
            "Appearance",
            "Configure the desktop theme, colors and visual effects.",
        )

        theme_group = SettingsGroup("Theme")

        dark_mode = Gtk.Switch()
        theme_group.add_row(
            "Dark mode",
            "Use dark colors throughout the desktop.",
            dark_mode,
        )

        animations = Gtk.Switch()
        animations.set_active(True)

        theme_group.add_row(
            "Animations",
            "Animate windows and interface elements.",
            animations,
        )

        self.append(theme_group)

        effects_group = SettingsGroup("Effects")

        blur = Gtk.Switch()
        effects_group.add_row(
            "Background blur",
            "Blur transparent desktop surfaces.",
            blur,
        )

        shadows = Gtk.Switch()
        shadows.set_active(True)

        effects_group.add_row(
            "Window shadows",
            "Draw shadows around floating windows.",
            shadows,
        )

        self.append(effects_group)
