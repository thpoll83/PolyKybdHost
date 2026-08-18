"""Compose a bug report a maintainer can actually act on.

The log bundle (:mod:`polyhost.services.log_bundle`) solves "which files do I
send"; this solves the other half — what the report *says*, and getting it to a
place the maintainer will see. It builds a GitHub issue body from the user's
description plus the same diagnostics About shows, and a pre-filled new-issue
URL to open in the browser.

Qt-free, so the tray dialog and any future CLI front end share it.

⚠️ **The destination is a PUBLIC issue tracker.** Two consequences shape this
module: paths are scrubbed of the user's home directory (they carry the account
name), and the body deliberately carries **no log content** — the logs go in the
attached bundle, where the user can see the file before deciding to upload it.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

ISSUE_REPO = "thpoll83/PolyKybdHost"

# A pre-filled new-issue URL is a GET, so the body rides in the query string.
# Long URLs are silently truncated or rejected somewhere between the browser and
# GitHub, so anything above this falls back to "open the blank form, body is on
# the clipboard" rather than posting a mangled report.
MAX_URL_BYTES = 6000

_TITLE_MAX = 90


def scrub_paths(text: str, home: str | None = None) -> str:
    """Replace the user's home directory with ``~``.

    The diagnostics block ends with the config and log directories, and on every
    platform those contain the account name (``C:\\Users\\tom\\AppData\\…``,
    ``/home/tom/…``). That is not worth publishing on a public tracker to say
    "the logs are in the usual place".
    """
    if not text:
        return text
    home = home or os.path.expanduser("~")
    out = text
    if home and home not in ("/", ""):
        # Match the literal path and its forward-slash spelling (Qt and pathlib
        # disagree about separators on Windows).
        for variant in {home, home.replace("\\", "/")}:
            out = out.replace(variant, "~")
    # Any remaining user directory from a *different* path root (e.g. a bundle
    # written to another drive, or a daemon started under another account).
    out = re.sub(r"(?i)([A-Z]:\\Users\\)[^\\/\s]+", r"\1<user>", out)
    out = re.sub(r"(/home/|/Users/)[^/\s]+", r"\1<user>", out)
    return out


def default_title(description: str) -> str:
    """A one-line issue title from the first line of the description."""
    first = (description or "").strip().splitlines()
    if not first:
        return "Problem report"
    title = first[0].strip()
    if len(title) > _TITLE_MAX:
        title = title[:_TITLE_MAX - 1].rstrip() + "…"
    return title or "Problem report"


def compose_body(description: str, expected: str = "", diagnostics: str = "",
                 bundle_name: str | None = None, redacted: bool = True,
                 home: str | None = None) -> str:
    """Build the issue body.

    Carries the description, the environment, and a pointer to the bundle — but
    never log lines themselves: the bundle is a file the reporter can inspect and
    choose to attach, which is a materially different decision from having it
    pasted into a public issue on their behalf.
    """
    parts = ["### What happened", (description or "").strip() or "_(not described)_"]
    if (expected or "").strip():
        parts += ["", "### What I expected", expected.strip()]
    if (diagnostics or "").strip():
        parts += ["", "### Diagnostics", "```", scrub_paths(diagnostics.strip(), home), "```"]
    if bundle_name:
        masked = ("window titles masked" if redacted
                  else "⚠️ window titles NOT masked — check it before attaching")
        parts += [
            "", "### Logs",
            f"A log bundle was saved as **`{bundle_name}`** ({masked}).",
            "",
            "**Please attach it to this issue** — drag the file into the comment "
            "box below before submitting. GitHub does not allow an app to attach "
            "it for you.",
        ]
    parts += ["", "---",
              "<sub>Reported from PolyHost's “Report a Problem” dialog.</sub>"]
    return "\n".join(parts)


def new_issue_url(title: str, body: str = "", repo: str = ISSUE_REPO,
                  labels: list[str] | None = None) -> str:
    """A GitHub new-issue URL with the fields pre-filled."""
    params = {"title": title or "Problem report"}
    if body:
        params["body"] = body
    if labels:
        params["labels"] = ",".join(labels)
    return f"https://github.com/{repo}/issues/new?" + urllib.parse.urlencode(params)


def url_too_long(url: str) -> bool:
    """True when the pre-filled URL should not be trusted to survive the trip."""
    return len(url.encode("utf-8")) > MAX_URL_BYTES


def issue_url_for(title: str, body: str, repo: str = ISSUE_REPO,
                  labels: list[str] | None = None) -> tuple[str, bool]:
    """Return ``(url, prefilled)``.

    Falls back to the blank new-issue form when the body would make the URL too
    long — the caller puts the body on the clipboard either way, so the reporter
    only has to paste rather than retype.
    """
    full = new_issue_url(title, body, repo, labels)
    if not url_too_long(full):
        return full, True
    return new_issue_url(title, "", repo, labels), False


def bundle_display_name(path: str | Path | None) -> str | None:
    return Path(path).name if path else None
