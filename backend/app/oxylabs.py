"""Oxylabs Web Scraper API client for YouTube surveillance.

Uses the Realtime integration (synchronous POST to /v1/queries) with the
YouTube sources: youtube_search for discovery, youtube_metadata and
youtube_transcript to assemble a video's textual content for analysis.

Response layouts differ per source and evolve, so parsing is deliberately
defensive: we walk the returned JSON for video-shaped objects and known text
keys instead of assuming exact schemas, and we always keep going on partial
data — a missing transcript degrades the analysis, it must not fail it.
"""
import asyncio
import logging
import os
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger("oxylabs")

OXYLABS_BASE_URL = os.environ.get("OXYLABS_BASE_URL", "https://realtime.oxylabs.io")
OXYLABS_USERNAME = os.environ.get("OXYLABS_USERNAME", "")
OXYLABS_PASSWORD = os.environ.get("OXYLABS_PASSWORD", "")

MAX_TRANSCRIPT_CHARS = 30000
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def available() -> bool:
    return bool(OXYLABS_USERNAME and OXYLABS_PASSWORD)


# --------------------------------------------------------------------------
# Generic JSON helpers (YouTube payloads nest text as str | {text} |
# {simpleText} | {runs:[{text}...]}).
# --------------------------------------------------------------------------

def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("simpleText", "text", "label", "content"):
            if key in value:
                return _text(value[key])
        if "runs" in value:
            return "".join(_text(run) for run in value.get("runs") or [])
        return ""
    if isinstance(value, list):
        return " ".join(filter(None, (_text(v) for v in value)))
    return ""


def _first(d: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        if key in d and d[key] is not None:
            text = _text(d[key])
            if text:
                return text
    return ""


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _extract_video_id(d: dict) -> Optional[str]:
    for key in ("videoId", "video_id", "id"):
        value = d.get(key)
        if isinstance(value, str) and _VIDEO_ID_RE.match(value):
            return value
    return None


# --------------------------------------------------------------------------
# API access
# --------------------------------------------------------------------------

class OxylabsError(RuntimeError):
    pass


async def _query(payload: dict, timeout: float = 90.0) -> Any:
    if not available():
        raise OxylabsError("Oxylabs credentials are not configured (OXYLABS_USERNAME / OXYLABS_PASSWORD).")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OXYLABS_BASE_URL}/v1/queries",
            auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
            json=payload,
        )
        if response.status_code in (401, 403):
            raise OxylabsError("Oxylabs rejected the credentials.")
        if response.status_code >= 400:
            # Oxylabs explains rejected parameters in the body — surface it.
            detail = response.text[:300]
            logger.warning("Oxylabs %s for payload %s: %s", response.status_code, payload, detail)
            raise OxylabsError(f"Oxylabs returned {response.status_code}: {detail}")
        data = response.json()
    # Realtime responses wrap content in results[0].content
    results = data.get("results") if isinstance(data, dict) else None
    if isinstance(results, list) and results:
        return results[0].get("content", results[0])
    return data


async def search(query: str, upload_date: str | None = None,
                 sort_by: str | None = None) -> list[dict]:
    # Search filters are top-level payload parameters (not `context` entries —
    # context is used by other sources, e.g. transcript language options).
    payload: dict[str, Any] = {"source": "youtube_search", "query": query}
    if upload_date:
        payload["upload_date"] = upload_date
    if sort_by and sort_by != "relevance":  # relevance is the service default
        payload["sort_by"] = sort_by

    content = await _query(payload)
    videos: dict[str, dict] = {}
    for node in _walk(content):
        video_id = _extract_video_id(node)
        if not video_id or video_id in videos:
            continue
        title = _first(node, ("title", "headline", "video_title"))
        if not title:
            continue
        videos[video_id] = {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": title,
            "channel": _first(node, ("channel", "channelTitle", "channel_name", "author",
                                     "ownerText", "longBylineText", "shortBylineText")),
            "views": _first(node, ("views", "view_count", "viewCountText", "shortViewCountText")),
            "published": _first(node, ("published", "published_time", "publishedTimeText")),
            "length": _first(node, ("length", "duration", "lengthText")),
            "description": _first(node, ("description", "descriptionSnippet", "detailedMetadataSnippets"))[:500],
            "thumbnail": _thumbnail(node),
        }
    return list(videos.values())[:20]


def _thumbnail(node: dict) -> str:
    for candidate in _walk(node.get("thumbnail") or node.get("thumbnails") or {}):
        url = candidate.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
    return ""


async def video_bundle(video_id: str) -> dict:
    """Metadata + transcript for one video, assembled for analysis."""
    if not _VIDEO_ID_RE.match(video_id):
        raise OxylabsError("Invalid YouTube video id.")

    url = f"https://www.youtube.com/watch?v={video_id}"

    async def _query_id_or_url(payload: dict) -> Any:
        """Some sources take the bare video id, some the watch URL — try both."""
        try:
            return await _query(payload)
        except OxylabsError:
            return await _query({**payload, "query": url})

    async def _metadata() -> dict:
        content = await _query_id_or_url({"source": "youtube_metadata", "query": video_id})
        meta = {"title": "", "channel": "", "description": ""}
        for node in _walk(content):
            if not meta["title"]:
                meta["title"] = _first(node, ("title", "video_title"))
            if not meta["channel"]:
                meta["channel"] = _first(node, ("channel", "channel_name", "channelTitle",
                                                "author", "ownerChannelName"))
            if not meta["description"]:
                meta["description"] = _first(node, ("description", "shortDescription",
                                                    "video_description"))
        return meta

    async def _transcript() -> str:
        content = await _query_id_or_url({
            "source": "youtube_transcript",
            "query": video_id,
            "context": [{"key": "language_code", "value": "en"}],
        })
        # Extract at the shallowest node exposing a text key and do not descend
        # into that subtree again (wrappers and their inner `runs` would
        # otherwise both match and duplicate every segment).
        segments: list[str] = []
        stack: list[Any] = [content]
        text_keys = ("snippet", "segment_text", "simpleText", "text")
        while stack:
            node = stack.pop(0)
            if isinstance(node, dict):
                matched = next((k for k in text_keys if k in node), None)
                if matched:
                    text = _text(node[matched]).strip()
                    if text:
                        segments.append(text)
                stack.extend(v for k, v in node.items() if k != matched)
            elif isinstance(node, list):
                stack = node + stack
        transcript = " ".join(segments).strip()
        if not transcript and isinstance(content, str):
            transcript = content
        return transcript[:MAX_TRANSCRIPT_CHARS]

    meta_result, transcript_result = await asyncio.gather(
        _metadata(), _transcript(), return_exceptions=True)

    meta = meta_result if isinstance(meta_result, dict) else {"title": "", "channel": "", "description": ""}
    if isinstance(meta_result, Exception):
        logger.warning("youtube_metadata failed for %s: %s", video_id, meta_result)
    transcript = transcript_result if isinstance(transcript_result, str) else ""
    if isinstance(transcript_result, Exception):
        logger.warning("youtube_transcript failed for %s: %s", video_id, transcript_result)

    if not (meta["title"] or meta["description"] or transcript):
        raise OxylabsError("Could not retrieve any content for this video.")

    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": meta["title"],
        "channel": meta["channel"],
        "description": meta["description"],
        "transcript": transcript,
    }
