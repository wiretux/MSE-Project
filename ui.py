from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, LoadingIndicator

from utils.query import retrieve


MAX_TITLE_LENGTH = 100
MAX_URL_LENGTH = 80
MAX_DESC_LENGTH = 150

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
        background: transparent;
    }

    #history-list > ListItem {
        width: 100%;
        height: auto;
        margin-top: 1;
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
        max-width: 100;
        height: 1fr;
        margin-top: 1;
        margin-bottom: 1;
        background: transparent;
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

    #result-list > ListItem Vertical {
        width: 100%;
        height: auto;
    }

    /* Fix label sizing and ensure text wraps properly instead of cutting off */
    #result-list > ListItem Label {
        width: 100%;
        height: auto;
    }

    .result-title {
        text-style: bold;
        color: $success;
    }

    .result-desc {
        color: $text-muted;
        margin-top: 1;
    }

    .result-url {
        width: 100%;
        height: auto;
        color: $text-disabled;
        text-style: italic;
    }

    .ai-score {
        color: $accent;
        margin-top: 1;
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
        self.search_list: list[tuple[str, str, str, str]] = []
        self.search_completed = False

    # Start the search in the background once the screen is mounted.
    def on_mount(self) -> None:
        self.perform_search()

    # Run retrieve() in a thread so the UI doesn't freeze while searching.
    @work(thread=True)
    def perform_search(self) -> None:
        results = retrieve(self.search_term)
        self.search_completed = True
        self.app.call_from_thread(self.update_results, results)

    # Shortens a text
    @staticmethod
    def shorten_text(text: str, limit: int) -> str:
        return ((text[:limit - 3] + "...")
                if len(text) > limit
                else text)

    # Returns the footer text
    def get_footer_text(self) -> str:
        ai_status_text = "on" if self.app.show_ai_score else "off"
        return f"Ctrl+A Show-AI-probably: {ai_status_text} | Press ESC to go back | Press Ctrl+Q to exit"

    # Hide the loading spinner and show the results (or a "no results" message).
    def update_results(self, results: list) -> None:
        self.search_list = []
        for doc, score in results:
            url = doc["url"]
            title = doc.get("title", "Untitled")
            desc = doc.get("description")
            ai_score = f"AI-probably: {doc.get("ai_score", 0) * 100.0:.2f}%"

            if desc in [None, "", "[No description]"]:
                desc = "No description provided"


            self.search_list.append((url, title, desc, ai_score))

        loader = self.query_one("#loader", LoadingIndicator)
        loader.display = False

        list_view = self.query_one("#result-list", ListView)
        if self.search_list:
            for url, title, desc, ai_score in self.search_list:

                ai_score_label = Label(self.shorten_text(ai_score, MAX_DESC_LENGTH), classes="ai-score")
                ai_score_label.display = self.app.show_ai_score

                list_view.append(
                    ListItem(
                        Vertical(
                            Label(self.shorten_text(title, MAX_TITLE_LENGTH), classes="result-title"),
                            Label(self.shorten_text(url, MAX_URL_LENGTH), classes="result-url"),
                            Label(self.shorten_text(desc, MAX_DESC_LENGTH), classes="result-desc"),
                            ai_score_label
                        )
                    )
                )
        else:
            list_view.append(ListItem(Label("No results found :(")))

    # Show the title, a loading spinner, and an empty results list to fill in later.
    def compose(self) -> ComposeResult:
        yield Label(f"Results for: {self.search_term}", id="title")
        yield LoadingIndicator(id="loader")
        yield ListView(id="result-list")
        yield Label(self.get_footer_text(), id="exit-label")

    # Open the URL of the selected result.
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        url, _, _, _ = self.search_list[event.index]
        self.app.open_url(url)

    # Go back to the search home screen.
    def key_escape(self) -> None:
        self.app.pop_screen()

    # Check if the user pressed a combination
    def on_key(self, event: Key) -> None:
        if event.key == "ctrl+a" and self.search_completed:
            self.app.show_ai_score = not self.app.show_ai_score

            # Update footer text
            exit_label = self.query_one("#exit-label", Label)
            exit_label.update(self.get_footer_text())

            # Toggle visibility of ai score labels
            for ai_label in self.query(".ai-score"):
                ai_label.display = self.app.show_ai_score

            event.stop()

class SearchEngine(App):
    # Create shared search history and show the home screen on startup.
    def on_mount(self) -> None:
        self.search_history = []
        self.show_ai_score = False
        self.push_screen(SearchScreen())


if __name__ == "__main__":
    app = SearchEngine()
    app.run()
