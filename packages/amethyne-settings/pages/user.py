from pages.base import SettingsGroup, SettingsPage


class UserPage(SettingsPage):
    def __init__(self) -> None:
        super().__init__(
            "User",
            "Manage your account, profile picture and sign-in preferences.",
        )

        profile_group = SettingsGroup("Profile")

        profile_group.add_row(
            "User account",
            "Profile settings will appear here.",
        )

        profile_group.add_row(
            "Avatar",
            "Choose a profile picture for this device.",
        )

        self.append(profile_group)
