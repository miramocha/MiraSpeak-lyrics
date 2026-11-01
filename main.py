"""Look up lyrics on LRCLIB and speak them line by line. Reference form module."""

from __future__ import annotations

from miraspeak.modules.api import (
    LIVE,
    LineEvent,
    LineState,
    Module,
    ModuleContext,
    ModuleError,
    ui,
)

from . import lrclib

_TERMINAL = frozenset({LineState.DONE, LineState.STOPPED, LineState.FAILED})
_MISALIGNED = "Couldn't line the lyrics up with playback."


class LyricsModule(Module):
    def page(self) -> ui.Page:
        return ui.Page(
            intro="Look up lyrics on LRCLIB and speak them line by line.",
            sections=(
                ui.Section(
                    "Song",
                    (
                        ui.Text("artist", "Artist"),
                        ui.Text("title", "Title"),
                        ui.Button("search", "Search"),
                        ui.Status("found"),
                    ),
                ),
                ui.Section(
                    "Speak",
                    (
                        ui.Rows("lines", "Lines", row_actions=("Speak",), speaks=True),
                        ui.Button("speak_all", "Speak all", speaks=True),
                        ui.Button("stop", "Stop"),
                    ),
                ),
            ),
        )

    def on_start(self, ctx: ModuleContext) -> None:
        self.ctx = ctx
        self.lines: list[str] = []
        self.track = ""
        self.found_artist = ""
        self.row_by_line: dict[int, int] = {}
        self._highlight_id: int | None = None

    def mcp_instructions(self) -> str:
        return (
            "Lyrics looks up a song on LRCLIB and can speak it. When the user asks "
            "to look up or speak a song's lyrics, call_module with module_id 'lyrics' "
            "and tool 'speak' (artist, title). Do not pass lyric text to the speak tool. "
            "Tool 'search' fills the page without speaking. Tool 'stop' stops this module's lines."
        )

    def mcp_tools(self) -> dict:
        return {"search": self.mcp_search, "speak": self.mcp_speak, "stop": self.mcp_stop}

    def mcp_search(self, artist: str, title: str) -> dict:
        """Look up lyrics and show them. Does not speak."""
        return self._lookup(artist, title)

    def mcp_speak(self, artist: str, title: str) -> dict:
        """Look up lyrics and speak them as one stack with Active Settings."""
        found = self._lookup(artist, title)
        if not found["ok"]:
            return found
        problem = self._speak_all()
        if problem:
            return {"ok": False, "message": problem}
        return found

    def mcp_stop(self) -> dict:
        """Stop this module's lines."""
        self._stop()
        return {"ok": True}

    def on_action(self, action: str, row: int | None = None) -> None:
        if action == "search":
            self._search()
        elif action == "speak_all":
            self._speak_all()
        elif action == "Speak":
            self._speak_row(row)
        elif action == "stop":
            self._stop()

    def on_line(self, event: LineEvent) -> None:
        if event.state is LineState.PLAYING and event.line_id in self.row_by_line:
            self._highlight_id = event.line_id
            self.ctx.ui.highlight_row("lines", self.row_by_line[event.line_id])
        elif event.line_id == self._highlight_id and event.state in _TERMINAL:
            self._clear_highlight()

    def _lookup(self, artist: str, title: str) -> dict:
        self.ctx.ui.set("artist", artist)
        self.ctx.ui.set("title", title)
        problem = self._search()
        if problem:
            return {"ok": False, "message": problem}
        return {
            "ok": True,
            "track": self.track,
            "artist": self.found_artist,
            "lines": len(self.lines),
        }

    def _search(self) -> str | None:
        artist = str(self.ctx.values.get("artist", "")).strip()
        title = str(self.ctx.values.get("title", "")).strip()
        if not artist or not title:
            message = "Type an artist and a title first."
            self.ctx.ui.set_status("found", message, tone=ui.TONE_WARNING)
            return message
        self.ctx.ui.set_status("found", "Searching…")
        try:
            hit = lrclib.search(artist, title)
        except lrclib.LrclibError as e:
            return self._miss(str(e))
        self.lines = list(hit.lines)
        self.track = hit.track
        self.found_artist = hit.artist
        self.row_by_line = {}
        self._highlight_id = None
        self.ctx.ui.set_rows("lines", self.lines)
        count = len(self.lines)
        self.ctx.ui.set_status("found", f"{hit.track} — {hit.artist} ({count} lines)")
        return None

    def _miss(self, message: str) -> str:
        self._forget_lines()
        self.ctx.ui.set_status("found", message, tone=ui.TONE_WARNING)
        return message

    def _speak_all(self) -> str | None:
        if not self.lines:
            self.ctx.ui.set_status("found", "Search for a song first.", tone=ui.TONE_WARNING)
            return "Search for a song first."
        try:
            queued = self.ctx.speak_lines(self.lines, voice=LIVE)
        except ModuleError as e:
            self.ctx.ui.set_status("found", str(e), tone=ui.TONE_WARNING)
            return str(e)
        if len(queued.line_ids) != len(self.lines):
            self.row_by_line = {}
            self._highlight_id = None
            self.ctx.ui.set_status("found", _MISALIGNED, tone=ui.TONE_WARNING)
            return _MISALIGNED
        self.row_by_line = dict(zip(queued.line_ids, range(len(self.lines)), strict=True))
        return None

    def _speak_row(self, row: int | None) -> None:
        if row is None or not 0 <= row < len(self.lines):
            return
        try:
            queued = self.ctx.speak(self.lines[row], voice=LIVE, split=False)
        except ModuleError as e:
            self.ctx.ui.set_status("found", str(e), tone=ui.TONE_WARNING)
            return
        if len(queued.line_ids) != 1:
            self.ctx.ui.set_status("found", _MISALIGNED, tone=ui.TONE_WARNING)
            return
        self.row_by_line[queued.line_ids[0]] = row

    def _stop(self) -> None:
        self.ctx.stop_mine()
        self._clear_highlight()

    def _clear_highlight(self) -> None:
        self._highlight_id = None
        self.ctx.ui.highlight_row("lines", None)

    def _forget_lines(self) -> None:
        self.lines = []
        self.track = ""
        self.found_artist = ""
        self.row_by_line = {}
        self._highlight_id = None
        self.ctx.ui.set_rows("lines", ())
