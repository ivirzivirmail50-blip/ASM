"""Fetch vendor assets (offline guarantee).

Downloads third-party JS/CSS/fonts into static/vendor/ and writes a
MANIFEST.txt with name | version | source_url | local_path | sha256.

Run: python scripts/fetch_vendor.py
"""
from __future__ import annotations

import hashlib
import logging
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("fetch_vendor")

VENDOR_DIR = Path(__file__).resolve().parent.parent / "static" / "vendor"

# (relative_path, url) — name = relative path's first segment.
ASSETS: list[tuple[str, str]] = [
    # Tailwind (precompiled CDN build)
    ("tailwind/tailwind.min.css",
     "https://cdn.tailwindcss.com/3.4.16"),
    # Alpine.js
    ("alpine/alpine.min.js",
     "https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"),
    # SortableJS
    ("sortablejs/Sortable.min.js",
     "https://cdn.jsdelivr.net/npm/sortablejs@1.15.3/Sortable.min.js"),
    # vis-network
    ("vis-network/vis-network.min.js",
     "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"),
    ("vis-network/vis-network.min.css",
     "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/styles/vis-network.min.css"),
    # EasyMDE
    ("easymde/easymde.min.css",
     "https://cdn.jsdelivr.net/npm/easymde@2.18.0/dist/easymde.min.css"),
    ("easymde/easymde.min.js",
     "https://cdn.jsdelivr.net/npm/easymde@2.18.0/dist/easymde.min.js"),
    # Chart.js
    ("chartjs/chart.umd.min.js",
     "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"),
    # Fonts
    ("fonts/inter.woff2",
     "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.woff2"),
    ("fonts/inter-bold.woff2",
     "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-600-normal.woff2"),
    ("fonts/noto-serif.woff2",
     "https://cdn.jsdelivr.net/fontsource/fonts/noto-serif@latest/latin-400-normal.woff2"),
    ("fonts/jetbrains-mono.woff2",
     "https://cdn.jsdelivr.net/fontsource/fonts/jetbrains-mono@latest/latin-400-normal.woff2"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_one(rel_path: str, url: str) -> str | None:
    target = VENDOR_DIR / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        log.info("Fetching %s …", url)
        req = urllib.request.Request(url, headers={"User-Agent": "asm-fetch/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        target.write_bytes(data)
        digest = sha256(data)
        log.info("  → %s (%d bytes, sha256=%s…)", target, len(data), digest[:12])
        return digest
    except Exception as exc:
        log.error("Failed to fetch %s: %s", url, exc)
        return None


def main() -> int:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    manifest_lines = ["# ASM vendor manifest — name | version | source_url | local_path | sha256"]
    failures = 0
    for rel_path, url in ASSETS:
        digest = fetch_one(rel_path, url)
        if digest is None:
            failures += 1
            continue
        # Try to extract a version from URL.
        version = "?"
        for part in url.split("/"):
            if part and part[0].isdigit():
                version = part
                break
        name = rel_path.split("/")[0]
        manifest_lines.append(
            f"{name} | {version} | {url} | static/vendor/{rel_path} | {digest}"
        )
    manifest_path = VENDOR_DIR / "MANIFEST.txt"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    log.info("Manifest written: %s", manifest_path)
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
