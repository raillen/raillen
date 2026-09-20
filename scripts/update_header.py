#!/usr/bin/env python3

from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
from html import escape
from pathlib import Path

QUOTES = [
    ("Live long and prosper.", "Star Trek"),
    ("We're all stories in the end.", "Doctor Who"),
    ("Bears. Beets. Battlestar Galactica.", "The Office"),
    ("Guys, I know kung fu.", "Chuck"),
]

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def quote_index(day: date) -> int:
    digest = sha256(day.isoformat().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % len(QUOTES)


def quote_for(day: date) -> tuple[str, str]:
    index = quote_index(day)
    previous = quote_index(day - timedelta(days=1))

    if index == previous:
        index = (index + 1) % len(QUOTES)

    return QUOTES[index]


def render_header(*, dark: bool, quote: str, source: str) -> str:
    if dark:
        background = "#0d1117"
        border = "#30363d"
        primary = "#f0f6fc"
        secondary = "#8b949e"
        accent = "#d2a8ff"
        poppy = "#ff7b72"
        humm = "#e3b341"
    else:
        background = "#ffffff"
        border = "#d0d7de"
        primary = "#1f2328"
        secondary = "#656d76"
        accent = "#8250df"
        poppy = "#cf222e"
        humm = "#9a6700"

    safe_quote = escape(quote)
    safe_source = escape(source)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="210" viewBox="0 0 900 210" role="img" aria-labelledby="title desc">
  <title id="title">Raillen profile header</title>
  <desc id="desc">{safe_quote} — {safe_source}</desc>

  <rect x="1" y="1" width="898" height="208" rx="22" fill="{background}" stroke="{border}"/>

  <circle cx="826" cy="46" r="38" fill="{poppy}" opacity="0.12"/>
  <circle cx="858" cy="76" r="24" fill="{humm}" opacity="0.16"/>
  <circle cx="796" cy="91" r="18" fill="{accent}" opacity="0.12"/>

  <text x="48" y="67" fill="{primary}" font-family="Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="34" font-weight="700">
    hey, i'm raillen 👋
  </text>

  <text x="49" y="101" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="15">
    software · experiments · rabbit holes · occasionally overthinking simple things
  </text>

  <line x1="49" y1="122" x2="851" y2="122" stroke="{border}"/>

  <text x="49" y="158" fill="{primary}" font-family="Georgia, Times New Roman, serif" font-size="19" font-style="italic">
    “{safe_quote}”
  </text>

  <text x="49" y="183" fill="{accent}" font-family="Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="13" font-weight="600">
    — {safe_source}
  </text>
</svg>
"""


def main() -> None:
    quote, source = quote_for(date.today())
    ASSETS.mkdir(parents=True, exist_ok=True)

    (ASSETS / "header-dark.svg").write_text(
        render_header(dark=True, quote=quote, source=source),
        encoding="utf-8",
    )
    (ASSETS / "header-light.svg").write_text(
        render_header(dark=False, quote=quote, source=source),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
