"""Entry reader screen for viewing feed entry content."""

import traceback
import webbrowser
from typing import TYPE_CHECKING, cast

import html2text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Markdown, Static

from miniflux_tui.api.models import Entry
from miniflux_tui.constants import CONTENT_SEPARATOR
from miniflux_tui.utils import api_call, get_star_icon

if TYPE_CHECKING:
    from miniflux_tui.ui.app import MinifluxTUI


class EntryReaderScreen(Screen):
    """Screen for reading a single feed entry."""

    BINDINGS: list[Binding] = [  # noqa: RUF012
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("J", "next_entry", "Next Entry", show=True),
        Binding("K", "previous_entry", "Previous Entry", show=True),
        Binding("pagedown", "page_down", "Page Down"),
        Binding("pageup", "page_up", "Page Up"),
        Binding("b", "back", "Back to List"),
        Binding("u", "mark_unread", "Mark Unread"),
        Binding("asterisk", "toggle_star", "Toggle Star"),
        Binding("e", "save_entry", "Save Entry"),
        Binding("o", "open_browser", "Open in Browser"),
        Binding("f", "fetch_original", "Fetch Original"),
        Binding("question_mark", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "back", "Back", show=False),
    ]

    def __init__(
        self,
        entry: Entry,
        entry_list: list | None = None,
        current_index: int = 0,
        unread_color: str = "cyan",
        read_color: str = "gray",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.entry = entry
        self.entry_list = entry_list or []
        self.current_index = current_index
        self.unread_color = unread_color
        self.read_color = read_color
        self.scroll_container = None

    @property
    def app(self) -> "MinifluxTUI":
        """Get the app instance with proper type hints."""
        return cast("MinifluxTUI", super().app)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()

        # Entry metadata
        star_icon = get_star_icon(self.entry.starred)

        # Create scrollable container with entry content
        with VerticalScroll():
            # Title and metadata
            yield Static(
                f"[bold cyan]{star_icon} {self.entry.title}[/bold cyan]",
                classes="entry-title",
            )
            yield Static(
                f"[dim]{self.entry.feed.title} | {self.entry.published_at.strftime('%Y-%m-%d %H:%M')}[/dim]",
                classes="entry-meta",
            )
            yield Static(f"[dim]{self.entry.url}[/dim]", classes="entry-url")
            yield Static(CONTENT_SEPARATOR, classes="separator")

            # Convert HTML content to markdown for better display
            content = self._html_to_markdown(self.entry.content)
            yield Markdown(content, classes="entry-content")

        yield Footer()

    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        # Get reference to the scroll container after mount
        self.scroll_container = self.query_one(VerticalScroll)

        # Mark entry as read when opened
        if self.entry.is_unread:
            await self._mark_entry_as_read()

    async def _mark_entry_as_read(self):
        """Mark the current entry as read via API."""
        if hasattr(self.app, "client") and self.app.client:
            try:
                await self.app.client.mark_as_read(self.entry.id)
                self.entry.status = "read"
            except Exception as e:
                self.log(f"Error marking as read: {e}")
                self.log(traceback.format_exc())
                self.notify(f"Error marking as read: {e}", severity="error")

    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to markdown for display.

        Converts HTML from RSS feed entries to markdown format for better
        terminal display. Preserves links, images, and formatting information.

        Args:
            html_content: Raw HTML content from the entry

        Returns:
            Markdown-formatted string suitable for terminal display
        """
        h = html2text.HTML2Text()
        # Preserve links, images, and emphasis in the output
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        # Disable body width wrapping - let Textual handle terminal wrapping
        h.body_width = 0
        return h.handle(html_content)

    def action_scroll_down(self):
        """Scroll down one line."""
        if not self.scroll_container:
            self.scroll_container = self.query_one(VerticalScroll)
        self.scroll_container.scroll_down()

    def action_scroll_up(self):
        """Scroll up one line."""
        if not self.scroll_container:
            self.scroll_container = self.query_one(VerticalScroll)
        self.scroll_container.scroll_up()

    def action_page_down(self):
        """Scroll down one page."""
        if not self.scroll_container:
            self.scroll_container = self.query_one(VerticalScroll)
        self.scroll_container.scroll_page_down()

    def action_page_up(self):
        """Scroll up one page."""
        if not self.scroll_container:
            self.scroll_container = self.query_one(VerticalScroll)
        self.scroll_container.scroll_page_up()

    def action_back(self):
        """Return to entry list."""
        self.app.pop_screen()

    async def action_mark_unread(self):
        """Mark entry as unread."""
        async with api_call(self, "marking entry as unread") as client:
            await client.mark_as_unread(self.entry.id)
            self.entry.status = "unread"
            self.notify("Marked as unread")

    async def action_toggle_star(self):
        """Toggle star status."""
        async with api_call(self, "toggling star status") as client:
            await client.toggle_starred(self.entry.id)
            self.entry.starred = not self.entry.starred
            status = "starred" if self.entry.starred else "unstarred"
            self.notify(f"Entry {status}")

            # Refresh display to update star icon
            await self.refresh_screen()

    async def action_save_entry(self):
        """Save entry to third-party service."""
        async with api_call(self, "saving entry") as client:
            await client.save_entry(self.entry.id)
            self.notify(f"Entry saved: {self.entry.title}")

    def action_open_browser(self):
        """Open entry URL in web browser."""
        try:
            webbrowser.open(self.entry.url)
            self.notify(f"Opened in browser: {self.entry.url}")
        except Exception as e:
            self.notify(f"Error opening browser: {e}", severity="error")

    async def action_fetch_original(self):
        """Fetch original content from source."""
        async with api_call(self, "fetching original content") as client:
            self.notify("Fetching original content...")

            # Fetch original content from API
            original_content = await client.fetch_original_content(self.entry.id)

            if original_content:
                # Update the entry's content
                self.entry.content = original_content

                # Refresh the screen to show new content
                await self.refresh_screen()

                self.notify("Original content loaded")
            else:
                self.notify("No original content available", severity="warning")

    async def action_next_entry(self):
        """Navigate to next entry."""
        if not self.entry_list or self.current_index >= len(self.entry_list) - 1:
            self.notify("No next entry", severity="warning")
            return

        # Move to next entry
        self.current_index += 1
        self.entry = self.entry_list[self.current_index]

        # Refresh the screen with new entry
        await self.refresh_screen()

    async def action_previous_entry(self):
        """Navigate to previous entry."""
        if not self.entry_list or self.current_index <= 0:
            self.notify("No previous entry", severity="warning")
            return

        # Move to previous entry
        self.current_index -= 1
        self.entry = self.entry_list[self.current_index]

        # Refresh the screen with new entry
        await self.refresh_screen()

    async def refresh_screen(self):
        """Refresh the screen with current entry."""
        scroll = self._get_scroll_container()
        self._clear_scroll_content(scroll)
        self._mount_entry_content(scroll)
        scroll.scroll_home(animate=False)

        # Mark as read after displaying
        if self.entry.is_unread:
            await self._mark_entry_as_read()

    def _get_scroll_container(self) -> VerticalScroll:
        """Get scroll container widget."""
        if not self.scroll_container:
            self.scroll_container = self.query_one(VerticalScroll)
        return self.scroll_container

    def _clear_scroll_content(self, scroll: VerticalScroll):
        """Remove all children from scroll container."""
        for child in scroll.children:
            child.remove()

    def _mount_entry_content(self, scroll: VerticalScroll):
        """Mount entry content widgets (title, metadata, URL, content)."""
        self._mount_title(scroll)
        self._mount_metadata(scroll)
        self._mount_url(scroll)
        self._mount_separator(scroll)
        self._mount_content(scroll)

    def _mount_title(self, scroll: VerticalScroll):
        """Mount entry title widget with star icon."""
        star_icon = get_star_icon(self.entry.starred)
        scroll.mount(
            Static(
                f"[bold cyan]{star_icon} {self.entry.title}[/bold cyan]",
                classes="entry-title",
            )
        )

    def _mount_metadata(self, scroll: VerticalScroll):
        """Mount entry metadata widget (feed name and published date)."""
        scroll.mount(
            Static(
                f"[dim]{self.entry.feed.title} | {self.entry.published_at.strftime('%Y-%m-%d %H:%M')}[/dim]",
                classes="entry-meta",
            )
        )

    def _mount_url(self, scroll: VerticalScroll):
        """Mount entry URL widget."""
        scroll.mount(Static(f"[dim]{self.entry.url}[/dim]", classes="entry-url"))

    def _mount_separator(self, scroll: VerticalScroll):
        """Mount visual separator widget."""
        scroll.mount(Static(CONTENT_SEPARATOR, classes="separator"))

    def _mount_content(self, scroll: VerticalScroll):
        """Mount entry content widget (converted HTML to Markdown)."""
        content = self._html_to_markdown(self.entry.content)
        scroll.mount(Markdown(content, classes="entry-content"))

    def action_show_help(self):
        """Show keyboard help."""
        self.app.push_screen("help")

    def action_quit(self):
        """Quit the application."""
        self.app.exit()
