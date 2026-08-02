from pathlib import Path

import gi

_gdk_pixbuf_version = "2.0"
gi.require_version("GdkPixbuf", _gdk_pixbuf_version)
from gi.repository import Gdk, GdkPixbuf, Gtk


class SidebarPageRow(Gtk.ListBoxRow):
    def __init__(
        self,
        page_name: str,
        title: str,
        is_section: bool = False,
    ) -> None:
        super().__init__()

        self.page_name = page_name
        self.title = title
        self.is_section = is_section
        self.section_rows: list[SidebarPageRow] = []
        self.parent_row: SidebarPageRow | None = None
        self.is_expanded = False
        self.revealer: Gtk.Revealer | None = None
        self.revealer_hide_handler_id: int | None = None

        if is_section:
            self.add_css_class("sidebar-section-row")
        else:
            self.add_css_class("sidebar-page-row")

        self.label = Gtk.Label(
            label=title,
            xalign=0,
            margin_top=7 if is_section else 9,
            margin_bottom=7 if is_section else 9,
            margin_start=32 if is_section else 14,
            margin_end=14,
        )

        if is_section:
            self.revealer = Gtk.Revealer()
            self.revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_DOWN
            )
            self.revealer.set_transition_duration(160)
            self.revealer.set_reveal_child(False)
            self.revealer.set_child(self.label)
            self.set_child(self.revealer)
        else:
            click = Gtk.GestureClick()
            click.connect("released", self.on_clicked)
            self.add_controller(click)
            self.set_child(self.label)

    def add_section_row(self, row: "SidebarPageRow") -> None:
        row.parent_row = self
        self.section_rows.append(row)
        self.update_label()
        row.set_revealed(self.is_expanded)

    def on_clicked(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        if self.section_rows:
            self.set_expanded(not self.is_expanded)

    def set_expanded(self, is_expanded: bool) -> None:
        self.is_expanded = is_expanded

        for row in self.section_rows:
            row.set_revealed(is_expanded)

        self.update_label()

    def set_revealed(self, is_revealed: bool) -> None:
        if self.revealer is None:
            return

        if self.revealer_hide_handler_id is not None:
            self.revealer.disconnect(self.revealer_hide_handler_id)
            self.revealer_hide_handler_id = None

        if is_revealed:
            self.set_visible(True)
            self.revealer.set_reveal_child(True)
            return

        if not self.get_visible() or not self.revealer.get_child_revealed():
            self.revealer.set_reveal_child(False)
            self.set_visible(False)
            return

        self.revealer.set_reveal_child(False)
        self.revealer_hide_handler_id = self.revealer.connect(
            "notify::child-revealed",
            self.on_child_revealed_changed,
        )

    def on_child_revealed_changed(
        self,
        revealer: Gtk.Revealer,
        _parameter,
    ) -> None:
        if revealer.get_child_revealed():
            return

        self.set_visible(False)

        if self.revealer_hide_handler_id is not None:
            revealer.disconnect(self.revealer_hide_handler_id)
            self.revealer_hide_handler_id = None

    def update_label(self) -> None:
        if not self.section_rows:
            self.label.set_label(self.title)
            return

        arrow = "▾" if self.is_expanded else "▸"
        self.label.set_label(f"{arrow} {self.title}")


class SidebarCategory(Gtk.Box):
    def __init__(
        self,
        title: str,
        row_selected_callback,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
        )

        heading = Gtk.Label(
            label=title,
            xalign=0,
            margin_start=14,
            margin_top=10,
            margin_bottom=4,
        )
        heading.add_css_class("sidebar-category-title")

        self.page_rows: dict[str, SidebarPageRow] = {}

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(
            Gtk.SelectionMode.SINGLE
        )
        self.listbox.add_css_class("sidebar-category")

        self.listbox.connect(
            "row-selected",
            row_selected_callback,
        )

        self.append(heading)
        self.append(self.listbox)

    def add_page(
        self,
        page_name: str,
        title: str,
    ) -> SidebarPageRow:
        row = SidebarPageRow(
            page_name,
            title,
        )

        self.page_rows[page_name] = row
        self.listbox.append(row)

        return row

    def add_section(
        self,
        page_name: str,
        title: str,
    ) -> SidebarPageRow:
        row = SidebarPageRow(
            page_name,
            title,
            is_section=True,
        )

        parent_row = self.page_rows.get(page_name)

        if parent_row is not None:
            parent_row.add_section_row(row)

        self.listbox.append(row)

        return row


class UserProfileEntry(Gtk.Box):
    def __init__(
        self,
        clicked_callback,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=4,
            margin_start=10,
            margin_end=10,
        )
        self.set_hexpand(True)
        self.add_css_class("profile-entry")

        profile_click = Gtk.GestureClick()
        profile_click.connect(
            "released",
            clicked_callback,
        )
        self.add_controller(profile_click)

        profile_content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=14,
            margin_bottom=14,
            margin_start=12,
            margin_end=12,
        )
        profile_content.set_halign(Gtk.Align.CENTER)

        avatar_frame = Gtk.Box()
        avatar_frame.set_size_request(64, 64)
        avatar_frame.set_halign(Gtk.Align.CENTER)
        avatar_frame.set_valign(Gtk.Align.CENTER)
        avatar_frame.set_overflow(Gtk.Overflow.HIDDEN)
        avatar_frame.add_css_class("profile-avatar")

        avatar = self.create_avatar()
        avatar_frame.append(avatar)

        profile_labels = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
        )
        profile_labels.set_halign(Gtk.Align.CENTER)

        profile_name = Gtk.Label(
            label="User",
            xalign=0.5,
        )
        profile_name.add_css_class("profile-name")

        profile_hint = Gtk.Label(
            label="Account settings",
            xalign=0.5,
        )
        profile_hint.add_css_class("profile-hint")

        profile_labels.append(profile_name)
        profile_labels.append(profile_hint)

        profile_content.append(avatar_frame)
        profile_content.append(profile_labels)
        self.append(profile_content)

    def create_avatar(self) -> Gtk.Image:
        user_icon_path = Path.home() / ".face"

        if user_icon_path.is_file():
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(user_icon_path),
                64,
                64,
                True,
            )
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            avatar = Gtk.Image.new_from_paintable(texture)
        else:
            avatar = Gtk.Image.new_from_icon_name(
                "avatar-default-symbolic"
            )
            avatar.set_pixel_size(34)

        avatar.set_size_request(64, 64)
        avatar.set_halign(Gtk.Align.CENTER)
        avatar.set_valign(Gtk.Align.CENTER)

        return avatar
