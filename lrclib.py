"""Look up plain lyrics on LRCLIB. No API key; Python modules are not fenced to this host."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "MiraSpeak/lyrics (https://lrclib.net/docs)"
# connect + read stay under MCP's 10 s call_module timeout.
TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_LONG_DURATION_S = 90.0
_TAG_LINE = re.compile(r"^(?:\[[^\[\]]*\]\s*)+$")

_NO_LYRICS = "No lyrics for that search."
_NO_ANSWER = "LRCLIB didn't answer."
_BAD_LIST = "LRCLIB returned something that isn't a song list."


class LrclibError(Exception):
    """The lookup failed, or the response had nothing speakable."""


@dataclass(frozen=True)
class LyricHit:
    """One recording: display names and one speakable line per row."""

    track: str
    artist: str
    lines: tuple[str, ...]


def search(artist: str, title: str) -> LyricHit:
    """GET LRCLIB search and pick one recording with plain lyrics.

    Raises LrclibError. Rank is whether the track and artist match *title* and
    *artist*, then duration of at least 90s, then longer text.
    """
    record = _choose(artist, title, _fetch(artist, title))
    lines = speakable_lines(str(record.get("plainLyrics") or ""))
    if not lines:
        raise LrclibError(_NO_LYRICS)
    track = str(record.get("trackName") or "").strip() or "Unknown"
    name = str(record.get("artistName") or "").strip() or "Unknown"
    return LyricHit(track, name, lines)


def speakable_lines(plain: str) -> tuple[str, ...]:
    """Non-empty lines, without rows that are only ``[section]`` tags."""
    kept: list[str] = []
    for raw in plain.splitlines():
        text = raw.strip()
        if text and _TAG_LINE.fullmatch(text) is None:
            kept.append(text)
    return tuple(kept)


def _fetch(artist: str, title: str) -> object:
    try:
        with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(SEARCH_URL, params={"artist_name": artist, "track_name": title})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise LrclibError(_NO_ANSWER) from e
    except ValueError as e:
        raise LrclibError(_BAD_LIST) from e


def _choose(artist: str, title: str, payload: object) -> dict:
    if not isinstance(payload, list):
        raise LrclibError(_BAD_LIST)
    pool = [item for item in payload if _has_plain(item)]
    if not pool:
        raise LrclibError(_NO_LYRICS)
    return max(pool, key=lambda item: _rank_key(artist, title, item))


def _has_plain(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    plain = item.get("plainLyrics")
    return isinstance(plain, str) and bool(plain.strip())


def _rank_key(artist: str, title: str, record: dict) -> tuple[int, int, int]:
    track = str(record.get("trackName") or "")
    recorded = str(record.get("artistName") or "")
    named = int(_same_name(title, track)) + int(_same_name(artist, recorded))
    duration = _duration(record.get("duration"))
    plain = str(record.get("plainLyrics") or "")
    return (named, int(duration >= _LONG_DURATION_S), len(plain))


def _same_name(wanted: str, got: str) -> bool:
    """True when *wanted* and *got* are the same name, ignoring case."""
    if not wanted or not got:
        return False
    left, right = wanted.casefold(), got.casefold()
    return left == right or left in right or right in left


def _duration(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return 0.0
    return float(raw)
