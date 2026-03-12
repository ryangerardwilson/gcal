from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from .config import timezone_info
from .errors import ApiError

try:
    from googleapiclient.errors import HttpError
except ModuleNotFoundError:  # pragma: no cover - allows source tests without installed deps
    HttpError = Exception


@dataclass(slots=True)
class CalendarEvent:
    event_id: str
    title: str
    start: str
    end: str
    attendees: list[str]
    meeting_url: str


def _calendar_event_from_item(item: dict) -> CalendarEvent:
    return CalendarEvent(
        event_id=str(item.get("id", "")),
        title=str(item.get("summary", "(untitled)")),
        start=str(item.get("start", {}).get("dateTime") or item.get("start", {}).get("date", "")),
        end=str(item.get("end", {}).get("dateTime") or item.get("end", {}).get("date", "")),
        attendees=extract_attendees(item),
        meeting_url=extract_meeting_url(item),
    )


def extract_meeting_url(event: dict) -> str:
    hangout = str(event.get("hangoutLink", "")).strip()
    if hangout:
        return hangout
    conference_data = event.get("conferenceData")
    if isinstance(conference_data, dict):
        for entry in conference_data.get("entryPoints", []) or []:
            if str(entry.get("entryPointType", "")).strip() == "video":
                return str(entry.get("uri", "")).strip()
    return "-"


def extract_attendees(event: dict) -> list[str]:
    attendees = []
    for entry in event.get("attendees", []) or []:
        email = str(entry.get("email", "")).strip()
        if email:
            attendees.append(email)
    return attendees


def _event_time_payload(value: datetime, timezone: str) -> dict[str, str]:
    payload = {"dateTime": value.isoformat()}
    if "/" in timezone:
        payload["timeZone"] = timezone
    return payload


def _is_recurring_event(item: dict) -> bool:
    return bool(item.get("recurringEventId") or item.get("recurrence"))


def create_event(service, title: str, start: datetime, end: datetime, timezone: str, invitees: list[str]) -> CalendarEvent:
    body = {
        "summary": title,
        "start": _event_time_payload(start, timezone),
        "end": _event_time_payload(end, timezone),
        "attendees": [{"email": email} for email in invitees],
        "conferenceData": {
            "createRequest": {
                "requestId": uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    try:
        event = service.events().insert(
            calendarId="primary",
            body=body,
            conferenceDataVersion=1,
            sendUpdates="all",
        ).execute()
    except HttpError as exc:
        raise ApiError(f"Calendar create failed: {exc}") from exc
    return CalendarEvent(
        event_id=str(event.get("id", "")),
        title=str(event.get("summary", "")),
        start=str(event.get("start", {}).get("dateTime", "")),
        end=str(event.get("end", {}).get("dateTime", "")),
        attendees=extract_attendees(event),
        meeting_url=extract_meeting_url(event),
    )


def list_upcoming_events(service, count: int, include_recurring: bool = True) -> list[CalendarEvent]:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        payload = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=count,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except HttpError as exc:
        raise ApiError(f"Calendar list failed: {exc}") from exc
    events = []
    for item in payload.get("items", []) or []:
        if not include_recurring and _is_recurring_event(item):
            continue
        events.append(_calendar_event_from_item(item))
    return events


def list_historical_events(service, count: int, include_recurring: bool = True) -> list[CalendarEvent]:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    events: deque[CalendarEvent] = deque(maxlen=count)
    page_token = None
    while True:
        try:
            payload = service.events().list(
                calendarId="primary",
                timeMax=now,
                maxResults=min(max(count, 1), 250),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            ).execute()
        except HttpError as exc:
            raise ApiError(f"Calendar history failed: {exc}") from exc
        for item in payload.get("items", []) or []:
            if not include_recurring and _is_recurring_event(item):
                continue
            events.append(_calendar_event_from_item(item))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return list(events)


def get_event(service, event_id: str) -> dict:
    try:
        return service.events().get(calendarId="primary", eventId=event_id).execute()
    except HttpError as exc:
        raise ApiError(f"Calendar get failed: {exc}") from exc


def delete_event(service, event_id: str) -> None:
    try:
        service.events().delete(
            calendarId="primary",
            eventId=event_id,
            sendUpdates="all",
        ).execute()
    except HttpError as exc:
        raise ApiError(f"Calendar delete failed: {exc}") from exc


def reschedule_event(service, event_id: str, start: datetime, end: datetime, timezone: str) -> CalendarEvent:
    body = {
        "start": _event_time_payload(start, timezone),
        "end": _event_time_payload(end, timezone),
    }
    try:
        event = service.events().patch(
            calendarId="primary",
            eventId=event_id,
            body=body,
            sendUpdates="all",
            conferenceDataVersion=1,
        ).execute()
    except HttpError as exc:
        raise ApiError(f"Calendar reschedule failed: {exc}") from exc
    return CalendarEvent(
        event_id=str(event.get("id", "")),
        title=str(event.get("summary", "")),
        start=str(event.get("start", {}).get("dateTime", "")),
        end=str(event.get("end", {}).get("dateTime", "")),
        attendees=extract_attendees(event),
        meeting_url=extract_meeting_url(event),
    )
