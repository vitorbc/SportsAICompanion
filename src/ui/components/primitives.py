"""Escaped HTML, local images, and a consistent set of line icons."""

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

from src.core.config import ROOT

ASSETS = ROOT / "assets"


def esc(value: object) -> str:
    return escape(str(value), quote=True)


def icon(name: str, size: int = 20) -> str:
    paths = {
        "ball": '<circle cx="12" cy="12" r="9"/><path d="m12 7 5 4-2 6H9l-2-6 5-4Zm0-4v4m8 1-3 3m1 8-3-2m-9 2 3-2M4 8l3 3"/>',
        "file": '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5Z"/><path d="M14 3v6h5M8 13h8m-8 4h6"/>',
        "shield": '<path d="m12 3 8 4v5c0 5-8 9-8 9s-8-4-8-9V7l8-4Z"/><path d="m8 12 3 3 5-6"/>',
        "play": '<path d="m9 5 11 7-11 7Z"/>',
        "arrow": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
        "chart": '<path d="M4 20h16M6 17v-5m6 5V4m6 13V8"/>',
        "calendar": '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18"/>',
        "spark": '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
    }
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
           f'stroke="#9fc4e3" stroke-width="1.6" stroke-linecap="round" '
           f'stroke-linejoin="round">{paths.get(name, paths["ball"])}</svg>')
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return f'<img class="line-icon" src="{uri}" width="{size}" height="{size}" alt="" />'


@lru_cache(maxsize=32)
def asset_uri(relative: str) -> str | None:
    path = (ASSETS / relative).resolve()
    if not path.is_relative_to(ASSETS.resolve()) or not path.is_file():
        return None
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml"}.get(path.suffix)
    if not mime:
        return None
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def portrait(asset: str, name: str, css: str = "participant") -> str:
    uri = asset_uri(asset)
    if uri:
        return f'<img class="{esc(css)}" src="{uri}" alt="{esc(name)}" />'
    initials = "".join(word[0] for word in name.split()[:2]) or "?"
    return f'<span class="{esc(css)} initials">{esc(initials)}</span>'


def section_title(title: str, name: str = "file", subtitle: str = "") -> str:
    return (f'<div class="section-heading"><span class="heading-icon">{icon(name)}</span>'
            f'<div><h2>{esc(title)}</h2>'
            + (f'<p>{esc(subtitle)}</p>' if subtitle else "") + '</div></div>')
