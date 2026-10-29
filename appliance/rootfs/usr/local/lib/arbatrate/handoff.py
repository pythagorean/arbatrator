"""The media-handoff request, shared by the appliance's helper programs.

A request asks the client to play one piece of media outside the browser:

    {"type": "play", "url": "https://…", "page_url": "https://…",
     "title": "…", "start": 12.5}

"url" is what to play: the media element's own source when it is a plain
http(s) URL, otherwise the page it sits on. "start" is the playback position
in seconds, or null.
"""
import math
import os
from urllib.parse import urlsplit

SOCKET_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp/arbatrate-runtime"), "arbatrate", "handoff.sock"
)

MAX_URL = 8192
MAX_TITLE = 512


def _http_url(value, field):
    if not isinstance(value, str) or len(value) > MAX_URL:
        raise ValueError(f"{field} must be a URL string")
    if urlsplit(value).scheme not in ("http", "https"):
        raise ValueError(f"{field} must be an http or https URL")
    return value


def validate_request(obj):
    """Return a clean copy of a request, or raise ValueError."""
    if not isinstance(obj, dict) or obj.get("type") != "play":
        raise ValueError("not a play request")
    title = obj.get("title") or ""
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    start = obj.get("start")
    if start is not None:
        if isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start) or start < 0:
            raise ValueError("start must be a non-negative number of seconds")
        start = float(start)
    page_url = obj.get("page_url")
    return {
        "type": "play",
        "url": _http_url(obj.get("url"), "url"),
        "page_url": _http_url(page_url, "page_url") if page_url else None,
        "title": title[:MAX_TITLE],
        "start": start,
    }
