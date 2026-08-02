from gi.repository import Gtk


class SettingsRow(Gtk.Box):
    def __init__(
        self,
        title: str,
        description: str,
        control: Gtk.Widget | None = None,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=18,
            margin_top=14,
            margin_bottom=14,
            margin_start=16,
            margin_end=16,
        )

        self.add_css_class("settings-row")

        labels = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=3,
            hexpand=True,
        )

        title_label = Gtk.Label(
            label=title,
            xalign=0,
        )
        title_label.add_css_class("setting-title")

        description_label = Gtk.Label(
            label=description,
            xalign=0,
            wrap=True,
        )
        description_label.add_css_class("setting-description")

        labels.append(title_label)
        labels.append(description_label)

        self.append(labels)

        if control is not None:
            control.set_valign(Gtk.Align.CENTER)
            self.append(control)


class SettingsGroup(Gtk.Box):
    def __init__(self, title: str) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        self.title = title

        heading = Gtk.Label(
            label=title,
            xalign=0,
        )
        heading.add_css_class("group-title")

        self.rows = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self.rows.add_css_class("settings-group")

        self.append(heading)
        self.append(self.rows)

    def add_row(
        self,
        title: str,
        description: str,
        control: Gtk.Widget | None = None,
    ) -> None:
        self.rows.append(
            SettingsRow(
                title,
                description,
                control,
            )
        )


class SettingsPage(Gtk.Box):
    def __init__(
        self,
        title: str,
        description: str,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=22,
            margin_top=32,
            margin_bottom=32,
            margin_start=32,
            margin_end=32,
        )
        self.sidebar_sections: list[str] = []
        self.add_css_class("settings-page")

        heading = Gtk.Label(
            label=title,
            xalign=0,
        )
        heading.add_css_class("page-title")

        subtitle = Gtk.Label(
            label=description,
            xalign=0,
            wrap=True,
        )
        subtitle.add_css_class("page-description")

        self.append(heading)
        self.append(subtitle)

    def append(self, child: Gtk.Widget) -> None:
        if isinstance(child, SettingsGroup):
            self.sidebar_sections.append(child.title)

        super().append(child)
