from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from .errors import ApiError
from .paths import ensure_dirs, transcripts_dir

try:
    from googleapiclient.errors import HttpError
except ModuleNotFoundError:  # pragma: no cover - allows source tests without installed deps
    HttpError = Exception

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"


@dataclass(slots=True)
class TranscriptAttachment:
    file_id: str
    title: str


def _looks_like_transcript_attachment(attachment: dict) -> bool:
    title = str(attachment.get("title", "")).strip().casefold()
    mime_type = str(attachment.get("mimeType", "")).strip()
    file_url = str(attachment.get("fileUrl", "")).strip()
    if mime_type == GOOGLE_DOC_MIME and "transcript" in title:
        return True
    return "docs.google.com/document" in file_url and "transcript" in title


def find_transcript_attachment(event: dict) -> TranscriptAttachment:
    attachments = event.get("attachments", []) or []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        if _looks_like_transcript_attachment(attachment):
            file_id = str(attachment.get("fileId", "")).strip()
            title = str(attachment.get("title", "")).strip() or "Transcript"
            if file_id:
                return TranscriptAttachment(file_id=file_id, title=title)
    raise ApiError("No transcript attachment found for this event.")


def export_transcript_text(drive_service, file_id: str) -> str:
    try:
        payload = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
    except HttpError as exc:
        raise ApiError(f"Transcript export failed: {exc}") from exc
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        return payload
    raise ApiError("Transcript export returned an unexpected response.")


def _safe_slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return normalized or "meeting"


def _start_fragment(start_value: str) -> str:
    raw = str(start_value).strip()
    if not raw:
        return "unknown-date"
    if "T" not in raw:
        return raw.replace("/", "-")
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d")
    except ValueError:
        return raw.split("T", 1)[0]


def save_transcript(text: str, event_id: str, title: str, start_value: str) -> Path:
    ensure_dirs()
    output_path = transcripts_dir() / f"{_start_fragment(start_value)}_{_safe_slug(title)}_{event_id}.txt"
    output_path.write_text(text, encoding="utf-8")
    return output_path
