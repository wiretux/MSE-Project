from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView

# TODO Make a good looking UI
# This is just a quick and dirty example implementation!
# The basics and structure can be used for a real implementation


class SearchScreen(Screen):
    CSS = """
    SearchScreen { align: center middle; padding: 1 0;}

    #search-box {
        width: 50%;
        height: auto;
        align: center middle;
    }

    #title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: green;
        margin-bottom: 1;
        text-wrap: nowrap;
    }

    #exit-label {
        dock: bottom;
        width: 100%;
        text-align: center;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        # generated with: https://coddy.tech/tools/ascii-art-generator
        logo_ascii = """
█████ █   █ █████     ████ █████  ███  ████   ███  █   █
  █   █   █ █        █     █     █   █ █   █ █     █   █
  █   █   █ ████      ███  ████  █████ ████  █     █████
  █   █   █ █            █ █     █   █ █  █  █     █   █
  █    ███  █████    ████  █████ █   █ █   █  ███  █   █
                     """

        with Vertical(id="search-box"):
            yield Label(logo_ascii, id="title")
            yield Input(placeholder="Enter the searchterms here")
        yield Label("Press Ctrl+Q to exit", id="exit-label")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value:
            self.app.push_screen(ResultScreen(search_term=event.value))

    def on_ready(self) -> None:
        pass


class ResultScreen(Screen):
    CSS = """
    ResultScreen { align: center top; padding: 1 0;}
    ListView {
        background: transparent;
        height: 1fr;
        margin-top: 1;
        align-horizontal: center;
    }

    ListItem {
        background: transparent;
        border: dashed gray;
        height: auto;
        width: 60;
        padding: 0 1;
    }

    ListView > ListItem.-highlight {
        background: transparent;
        border: solid $success;
        width: 60;
    }

    .item-title {
        text-style: bold;
        width: 1fr;
    }

    .item-info,
    ListView > ListItem.-highlight .item-info {
        text-style: not bold !important;
        text-align: right;
    }

    #title {
        dock: top;
        width: 100%;
        text-align: center;
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

        # For the final ui we would need to get here the real search results
        self.search_list = [
            (
                "https://www.google.com/",
                "First Result Title",
                "A cool website desciption ig",
            ),
            (
                "https://github.com/",
                "Second Result Title",
                "Another cool website desciption ig",
            ),
            (
                "https://www.google.com/",
                "Third Result Title",
                "idk what to put here anymore XD",
            ),
            ("https://www.google.com/", "Fourth Result Title", "..."),
            (
                "https://www.google.com/",
                "Third Result Title",
                "This allows us to test scrolling",
            ),
            ("https://www.google.com/", "Fifth Result Title", "An finally done"),
        ]

    def compose(self) -> ComposeResult:
        yield Label(f"Results for: {self.search_term}", id="title")
        yield ListView(
            *[
                ListItem(
                    Label(title, classes="item-title"), Label(desc, classes="item-info")
                )
                for _, title, desc in self.search_list
            ]
        )
        yield Label("Press ESC to go back", id="exit-label")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        url, _, _ = self.search_list[event.index]

        self.app.open_url(url)

    def key_escape(self) -> None:
        self.app.pop_screen()


class SearchEngine(App):
    def on_mount(self) -> None:
        self.push_screen(SearchScreen())


if __name__ == "__main__":
    app = SearchEngine()
    app.run()
