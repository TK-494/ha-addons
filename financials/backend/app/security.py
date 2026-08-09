"""Security helpers: response headers, path containment, log redaction and
CSV-export escaping.

These are deliberately small, boring functions in one place rather than
inline checks scattered through the routers — a containment check that only
exists on three of four file endpoints is the same as no containment check.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import Request
from fastapi.responses import Response

# `X-Frame-Options` is deliberately absent: Home Assistant serves add-on
# panels inside an iframe, and DENY/SAMEORIGIN would break Ingress. The CSP
# below carries the rest of the weight.
CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "   # Tailwind injects a style element
    "script-src 'self'; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors *"                     # required by Ingress
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    "Content-Security-Policy": CSP,
    "Cross-Origin-Opener-Policy": "same-origin",
}


async def security_headers_middleware(request: Request, call_next) -> Response:
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


def contained_path(root: Path, candidate: str) -> Optional[Path]:
    """Resolve `candidate` under `root` and return it only if it stays inside.

    Guards both the SPA fallback and the uploaded-file endpoints. Without it,
    a request for `..%2F..%2Fdata%2Ffinancials.db` resolves outside the root
    and the server hands over the database — which was a real HIGH finding in
    the predecessor add-on.
    """
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return resolved


_IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2})([A-Z0-9]{4,26})\b")


def mask_iban(text: str) -> str:
    """Reduce IBANs to `NL96…1953`.

    Add-on logs are visible in the Home Assistant UI and get attached to
    diagnostics and bug reports, so account numbers must not reach them.
    """
    return _IBAN_RE.sub(lambda m: f"{m.group(1)}…{m.group(2)[-4:]}", text or "")


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: object) -> str:
    """Neutralise spreadsheet formula injection on export.

    A merchant name is attacker-controlled in the sense that anyone who can
    get a payment description into your bank feed chooses that text. Excel
    happily evaluates a cell starting with `=`, so exports prefix those.
    """
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text
