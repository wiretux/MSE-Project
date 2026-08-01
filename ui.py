from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, LoadingIndicator

from query import retrieve


class SearchScreen(Screen):
    # Styling for the search home screen: centered card, input box, and history list below it.
    CSS = """
    SearchScreen {
        align: center middle;
        padding: 1 2;
        background: $surface;
    }

    #search-box {
        width: 80%;
        max-width: 72;
        height: auto;
        padding: 1 2;
        background: $panel;
        border: round $accent;
    }

    #title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $success;
        margin-bottom: 0;
    }

    .subtitle {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    #search-input {
        width: 100%;
        margin-bottom: 1;
    }

    .section-label {
        margin-top: 1;
        margin-bottom: 0;
        text-style: bold;
        color: $accent;
    }

    #history-list {
        width: 100%;
        height: auto;
        max-height: 10;
    }

    #history-list > ListItem {
        width: 100%;
        height: auto;
        margin-top: 1;
        padding: 0 1;
        background: $boost;
        border: round $primary;
    }

    #history-list > ListItem.-highlight {
        background: $primary;
        border: round $success;
    }

    #history-list > ListItem > Label {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }

    #exit-label {
        dock: bottom;
        width: 100%;
        text-align: center;
        color: $text-muted;
    }
    """

    # Build the search box and the recent-searches list.
    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label("MSE Search", id="title")
            yield Label("Find indexed results and re-run past queries.", classes="subtitle")
            yield Input(placeholder="Enter the search terms here", id="search-input")
            yield Label("Recent searches", classes="section-label")
            yield ListView(
                *[
                    ListItem(Label(term))
                    for term in getattr(self.app, "search_history", [])
                ],
                id="history-list",
            )
        yield Label("Press Ctrl+Q to exit", id="exit-label")

    # Save the search term to history and open the results screen.
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value:
            self._record_search(event.value)
            self.app.push_screen(ResultScreen(search_term=event.value))

    # Re-run a search picked from the history list.
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        history = self.app.search_history
        search_term = history[event.index]
        self._record_search(search_term)
        self.app.push_screen(ResultScreen(search_term=search_term))

    # Focus the input as soon as the screen is ready.
    def on_ready(self) -> None:
        self.query_one(Input).focus()

    # Add the search term to the top of the history and refresh the list.
    def _record_search(self, search_term: str) -> None:
        history = self.app.search_history

        if search_term in history:
            history.remove(search_term)

        history.insert(0, search_term)
        self._sync_history_list()

    # Rebuild the history list widget from the current history.
    def _sync_history_list(self) -> None:
        history_list = self.query_one("#history-list", ListView)
        history_list.clear()
        history_list.extend(ListItem(Label(term)) for term in self.app.search_history)


class ResultScreen(Screen):
    # Styling for the results screen: one chip per result.
    CSS = """
    ResultScreen {
        align: center top;
        padding: 1 2;
        background: $surface;
    }

    #result-list {
        width: 80%;
        max-width: 72;
        height: 1fr;
        margin-top: 1;
        align-horizontal: center;
    }

    #result-list > ListItem {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-top: 1;
        background: $boost;
        border: round $accent;
    }

    #result-list > ListItem.-highlight {
        background: $primary;
        border: round $success;
    }

    #result-list > ListItem > Label {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }

    #title {
        dock: top;
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $success;
    }

    #exit-label {
        dock: bottom;
        width: 100%;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, search_term: str):
        super().__init__()
        self.search_term = search_term
        self.search_list: list[tuple[str, str, str]] = []

    # Start the search in the background once the screen is mounted.
    def on_mount(self) -> None:
        self.perform_search()

    # Run retrieve() in a thread so the UI doesn't freeze while searching.
    @work(thread=True)
    def perform_search(self) -> None:
        results = retrieve(self.search_term)
        self.app.call_from_thread(self.update_results, results)

    # Hide the loading spinner and show the results (or a "no results" message).
    def update_results(self, results) -> None:
        self.search_list = [
            (doc["url"], doc["title"], doc["description"])
            for doc, score in results
        ]

        loader = self.query_one("#loader", LoadingIndicator)
        loader.display = False

        list_view = self.query_one("#result-list", ListView)
        if self.search_list:
            for _, title, desc in self.search_list:
                list_view.append(ListItem(Label(title)))
        else:
            list_view.append(ListItem(Label("No results found :(")))

    # Show the title, a loading spinner, and an empty results list to fill in later.
    def compose(self) -> ComposeResult:
        yield Label(f"Results for: {self.search_term}", id="title")
        yield LoadingIndicator(id="loader")
        yield ListView(id="result-list")
        yield Label("Press ESC to go back", id="exit-label")

    # Open the URL of the selected result.
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        url, _, _ = self.search_list[event.index]
        self.app.open_url(url)

    # Go back to the search home screen.
    def key_escape(self) -> None:
        self.app.pop_screen()


class SearchEngine(App):
    # Create shared search history and show the home screen on startup.
    def on_mount(self) -> None:
        self.search_history = []
        self.push_screen(SearchScreen())


if __name__ == "__main__":
    app = SearchEngine()
    app.run()
