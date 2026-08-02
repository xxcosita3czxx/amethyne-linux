import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: I001

from components.sidebar import SidebarCategory, SidebarPageRow, UserProfileEntry

from pages.about import AboutPage
from pages.appearance import AppearancePage
from pages.bluetooth import BluetoothPage
from pages.display import DisplayPage
from pages.network import NetworkPage
from pages.user import UserPage
from pages.windows import WindowsPage


APP_ID = "cz.amethyne.Settings"




class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
    ) -> None:
        super().__init__(
            application=application,
            title="Settings",
            default_width=1000,
            default_height=680,
        )

        self.set_decorated(True)
        self.set_size_request(720, 480)

        self.sidebar_categories: list[SidebarCategory] = []

        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
        )
        root.add_css_class("app-background")

        root.set_hexpand(True)
        root.set_vexpand(True)

        title_bar = Gtk.HeaderBar()
        title_bar.set_show_title_buttons(True)

        title = Gtk.Label(label="Settings")
        title.add_css_class("window-title")
        title_bar.set_title_widget(title)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search settings")
        self.search_entry.set_width_chars(24)
        title_bar.pack_end(self.search_entry)

        self.set_titlebar(title_bar)

        content = Gtk.Paned.new(
            Gtk.Orientation.HORIZONTAL
        )
        content.add_css_class("content-background")
        content.set_position(260)
        content.set_shrink_start_child(False)
        content.set_resize_start_child(False)
        content.set_hexpand(True)
        content.set_vexpand(True)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        sidebar_scroll.set_vexpand(True)
        sidebar_scroll.add_css_class("sidebar")

        self.sidebar_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=8,
            margin_bottom=16,
        )
        sidebar_scroll.set_child(self.sidebar_container)

        self.sidebar_container.append(
            UserProfileEntry(self.on_user_profile_clicked)
        )

        page_scroll = Gtk.ScrolledWindow()
        page_scroll.add_css_class("page-background")
        page_scroll.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        page_scroll.set_hexpand(True)
        page_scroll.set_vexpand(True)

        self.stack = Gtk.Stack()
        self.stack.add_css_class("page-background")
        self.stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )
        self.stack.set_transition_duration(180)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)

        page_scroll.set_child(self.stack)

        content.set_start_child(sidebar_scroll)
        content.set_end_child(page_scroll)

        root.append(content)

        self.set_child(root)
        self.build_pages()

    def build_pages(self) -> None:
        first_row = None

        self.stack.add_named(
            UserPage(),
            "user",
        )

        system_category = self.add_category("System")

        row = self.add_page(
            system_category,
            "appearance",
            "Appearance",
            AppearancePage(),
        )

        first_row = row

        self.add_page(
            system_category,
            "windows",
            "Windows",
            WindowsPage(),
        )

        self.add_page(
            system_category,
            "displays",
            "Displays",
            DisplayPage(),
        )

        connectivity_category = self.add_category(
            "Connectivity"
        )

        self.add_page(
            connectivity_category,
            "network",
            "Network",
            NetworkPage(),
        )

        self.add_page(
            connectivity_category,
            "bluetooth",
            "Bluetooth",
            BluetoothPage(),
        )

        information_category = self.add_category(
            "Information"
        )

        self.add_page(
            information_category,
            "about",
            "About",
            AboutPage(),
        )

        if first_row is not None:
            system_category.listbox.select_row(
                first_row
            )

    def add_category(
        self,
        title: str,
    ) -> SidebarCategory:
        category = SidebarCategory(
            title,
            self.on_page_selected,
        )

        self.sidebar_categories.append(category)
        self.sidebar_container.append(category)

        return category

    def add_page(
        self,
        category: SidebarCategory,
        page_name: str,
        title: str,
        page: Gtk.Widget,
    ) -> SidebarPageRow:
        row = category.add_page(
            page_name,
            title,
        )

        self.stack.add_named(
            page,
            page_name,
        )

        for section_title in getattr(page, "sidebar_sections", []):
            category.add_section(page_name, section_title)

        return row

    def collapse_sidebar_sections(
        self,
        selected_page_name: str | None = None,
    ) -> None:
        for category in self.sidebar_categories:
            for page_name, page_row in category.page_rows.items():
                page_row.set_expanded(page_name == selected_page_name)

    def on_user_profile_clicked(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        for category in self.sidebar_categories:
            category.listbox.unselect_all()

        self.collapse_sidebar_sections()
        self.stack.set_visible_child_name("user")

    def on_page_selected(
        self,
        selected_listbox: Gtk.ListBox,
        row: Gtk.ListBoxRow | None,
    ) -> None:
        if not isinstance(row, SidebarPageRow):
            return

        for category in self.sidebar_categories:
            if category.listbox is selected_listbox:
                continue

            category.listbox.unselect_all()

        self.collapse_sidebar_sections(row.page_name)

        self.stack.set_visible_child_name(
            row.page_name
        )


class SettingsApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.load_css()

    def do_activate(self) -> None:
        window = self.props.active_window

        if window is None:
            window = SettingsWindow(self)

        window.present()

    def load_css(self) -> None:
        css_path = Path(__file__).with_name("style.gtk.css")

        if not css_path.is_file():
            raise RuntimeError(f"Missing stylesheet: {css_path}")

        provider = Gtk.CssProvider()
        provider.load_from_file(
            Gio.File.new_for_path(str(css_path))
        )

        display = Gdk.Display.get_default()

        if display is None:
            raise RuntimeError("GTK could not find an active display")

        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def main() -> int:
    application = SettingsApplication()
    return application.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
