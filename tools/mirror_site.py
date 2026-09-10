#!/usr/bin/env python3
"""Build a self-hosted Music Atlas mirror from the public Squarespace page."""

from __future__ import annotations

import concurrent.futures
import hashlib
import html as html_module
import json
import mimetypes
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SOURCE = "https://www.musicatlas.radio/"
ROOT = Path(__file__).resolve().parents[1]
MIRROR_ROOT = ROOT / "_mirror"
USER_AGENT = "MusicAtlasSelfHostedMirror/1.0"

MIRRORED_HOSTS = {
    "assets.squarespace.com",
    "definitions.sqspcdn.com",
    "images.squarespace-cdn.com",
    "static1.squarespace.com",
}

EXCLUDED_RUNTIME_MARKERS = (
    "visitor-site-error-reporter",
    "performance-",
    "user-account-core",
)

EXCLUDED_RESOURCE_MARKERS = EXCLUDED_RUNTIME_MARKERS + (
    "universal/images-v6/icons/icon-plus-16-dark.png",
)

ASSET_SUFFIXES = {
    ".avif",
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mjs",
    ".otf",
    ".png",
    ".svg",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
}

ABSOLUTE_URL_RE = re.compile(
    r"(?:(?:https?:)?//)(?:assets\.squarespace\.com|definitions\.sqspcdn\.com|"
    r"images\.squarespace-cdn\.com|static1\.squarespace\.com)"
    r"[^\s\"'<>\\),}\]]+",
    re.IGNORECASE,
)
CSS_URL_RE = re.compile(r"url\(\s*([\"']?)([^\"')]+)\1\s*\)", re.IGNORECASE)
SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE | re.DOTALL)


def normalize_url(raw: str, base: str = SOURCE) -> str:
    value = html_module.unescape(raw.strip()).strip(" \t\r\n\"'")
    if value.startswith("//"):
        value = "https:" + value
    value = urllib.parse.urljoin(base, value)
    parts = urllib.parse.urlsplit(value)
    return urllib.parse.urlunsplit(("https", parts.netloc.lower(), parts.path, parts.query, ""))


def is_mirrored(url: str) -> bool:
    return urllib.parse.urlsplit(url).hostname in MIRRORED_HOSTS


def is_excluded(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in EXCLUDED_RESOURCE_MARKERS)


def is_asset(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    path = parts.path.rstrip("/")
    suffix = Path(path).suffix.lower()
    return bool(path) and (suffix in ASSET_SUFFIXES or parts.hostname == "images.squarespace-cdn.com")


def safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._%+@-]", "_", value) or "index"


def local_relative_path(url: str) -> Path:
    parts = urllib.parse.urlsplit(url)
    decoded_path = urllib.parse.unquote(parts.path)
    path_parts = [safe_segment(part) for part in decoded_path.split("/") if part]
    if not path_parts or parts.path.endswith("/"):
        path_parts.append("index")

    filename = path_parts[-1]
    if parts.query:
        digest = hashlib.sha256(parts.query.encode()).hexdigest()[:12]
        suffixes = "".join(Path(filename).suffixes)
        stem = filename[: -len(suffixes)] if suffixes else filename
        filename = f"{stem}__q_{digest}{suffixes}"
        path_parts[-1] = filename

    return Path("_mirror") / safe_segment(parts.netloc) / Path(*path_parts)


def local_public_url(url: str) -> str:
    return "/" + local_relative_path(url).as_posix()


def fetch(url: str) -> tuple[str, bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": SOURCE, "Accept": "*/*"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return url, response.read(), response.headers.get_content_type()


def discover_absolute(text: str, base: str) -> set[str]:
    urls: set[str] = set()
    for match in ABSOLUTE_URL_RE.finditer(text):
        url = normalize_url(match.group(0), base)
        if is_mirrored(url) and is_asset(url) and not is_excluded(url):
            urls.add(url)
    return urls


def discover_css(text: str, base: str) -> set[str]:
    urls = discover_absolute(text, base)
    for match in CSS_URL_RE.finditer(text):
        raw = match.group(2).strip()
        if raw.startswith(("data:", "blob:", "#")):
            continue
        url = normalize_url(raw, base)
        if is_mirrored(url) and is_asset(url) and not is_excluded(url):
            urls.add(url)
    return urls


def rewrite_urls(text: str, base: str, downloaded: set[str], css: bool = False) -> str:
    def replace_absolute(match: re.Match[str]) -> str:
        url = normalize_url(match.group(0), base)
        return local_public_url(url) if url in downloaded else match.group(0)

    text = ABSOLUTE_URL_RE.sub(replace_absolute, text)

    if css:
        def replace_css(match: re.Match[str]) -> str:
            raw = match.group(2).strip()
            if raw.startswith(("data:", "blob:", "#")):
                return match.group(0)
            url = normalize_url(raw, base)
            if url not in downloaded:
                return match.group(0)
            quote = match.group(1) or "'"
            return f"url({quote}{local_public_url(url)}{quote})"

        text = CSS_URL_RE.sub(replace_css, text)

    return text


def scrub_html(source_html: str) -> str:
    def keep_script(match: re.Match[str]) -> str:
        block = match.group(0)
        lowered = block.lower()
        if "use.typekit.net" in lowered or "wf-loading" in lowered:
            return ""
        if "static.cookie_banner_capable" in lowered:
            return ""
        if any(marker in lowered for marker in EXCLUDED_RUNTIME_MARKERS):
            return ""
        return block

    def keep_link(match: re.Match[str]) -> str:
        block = match.group(0)
        lowered = block.lower()
        if "user-account-core" in lowered:
            return ""
        if ("preconnect" in lowered or "dns-prefetch" in lowered) and any(
            host in lowered for host in MIRRORED_HOSTS | {"use.typekit.net"}
        ):
            return ""
        return block

    source_html = SCRIPT_BLOCK_RE.sub(keep_script, source_html)
    source_html = LINK_TAG_RE.sub(keep_link, source_html)
    return source_html


def inject_local_policy(source_html: str) -> str:
    policy = (
        "default-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-inline' blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "media-src 'self' blob:; "
        "frame-src https://w.soundcloud.com; "
        "connect-src 'none'; object-src 'none'; base-uri 'self'; worker-src 'self' blob:"
    )
    additions = (
        f'\n<meta http-equiv="Content-Security-Policy" content="{policy}">\n'
        '<meta name="referrer" content="no-referrer">\n'
        '<link rel="stylesheet" href="/assets/self-hosted.css">\n'
        '<script src="/assets/self-hosted-runtime.js" defer></script>\n'
    )
    return re.sub(r"(<head\b[^>]*>)", lambda match: match.group(1) + additions, source_html, count=1, flags=re.IGNORECASE)


def main() -> None:
    MIRROR_ROOT.mkdir(parents=True, exist_ok=True)
    source_url, source_bytes, _ = fetch(SOURCE)
    source_html = source_bytes.decode("utf-8", errors="replace")
    source_html = scrub_html(source_html)

    pending = discover_absolute(source_html, source_url)
    downloaded: dict[str, dict[str, object]] = {}
    text_assets: dict[str, tuple[str, str]] = {}
    failed: dict[str, str] = {}

    while pending:
        batch = sorted(url for url in pending if url not in downloaded and url not in failed)
        pending.clear()
        if not batch:
            break

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fetch, url): url for url in batch}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    _, payload, content_type = future.result()
                except Exception as exc:  # Preserve a complete failure manifest.
                    failed[url] = f"{type(exc).__name__}: {exc}"
                    continue

                relative = local_relative_path(url)
                output = ROOT / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                extension = Path(urllib.parse.urlsplit(url).path).suffix.lower()
                is_text = content_type in {
                    "application/javascript",
                    "application/json",
                    "text/css",
                    "text/html",
                    "text/javascript",
                } or extension in {".css", ".js", ".json", ".mjs"}

                downloaded[url] = {
                    "local": "/" + relative.as_posix(),
                    "bytes": len(payload),
                    "content_type": content_type,
                }

                if is_text:
                    text = payload.decode("utf-8", errors="replace")
                    text_assets[url] = (text, content_type)
                    discovered = discover_css(text, url) if extension == ".css" or content_type == "text/css" else discover_absolute(text, url)
                    pending.update(discovered - downloaded.keys() - failed.keys())
                else:
                    output.write_bytes(payload)

    downloaded_urls = set(downloaded)
    for url, (text, content_type) in text_assets.items():
        extension = Path(urllib.parse.urlsplit(url).path).suffix.lower()
        rewritten = rewrite_urls(
            text,
            url,
            downloaded_urls,
            css=extension == ".css" or content_type == "text/css",
        )
        (ROOT / local_relative_path(url)).write_text(rewritten, encoding="utf-8")

    source_html = rewrite_urls(source_html, source_url, downloaded_urls)
    source_html = inject_local_policy(source_html)
    (ROOT / "index.html").write_text(source_html, encoding="utf-8")

    manifest = {
        "source": SOURCE,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "resources": downloaded,
        "failed": failed,
        "excluded_runtime_markers": list(EXCLUDED_RUNTIME_MARKERS),
        "excluded_resource_markers": list(EXCLUDED_RESOURCE_MARKERS),
        "remote_frames": ["https://w.soundcloud.com"],
        "parent_connect_policy": "none",
    }
    (ROOT / "mirror-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    total_bytes = sum(int(item["bytes"]) for item in downloaded.values())
    print(f"mirrored={len(downloaded)} failed={len(failed)} bytes={total_bytes}")
    for url, reason in sorted(failed.items()):
        print(f"FAILED {url}: {reason}")


if __name__ == "__main__":
    main()
