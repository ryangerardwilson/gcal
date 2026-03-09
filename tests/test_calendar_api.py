import unittest
from unittest.mock import MagicMock

from gcal_cli.calendar_api import create_event, extract_meeting_url


class CalendarApiTests(unittest.TestCase):
    def test_extract_meeting_url_prefers_hangout_link(self) -> None:
        event = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
        self.assertEqual(extract_meeting_url(event), "https://meet.google.com/abc-defg-hij")

    def test_create_event_requests_meet_and_send_updates(self) -> None:
        service = MagicMock()
        execute = service.events.return_value.insert.return_value.execute
        execute.return_value = {
            "id": "evt1",
            "summary": "Interview",
            "start": {"dateTime": "2026-03-10T14:00:00+05:30"},
            "end": {"dateTime": "2026-03-10T15:00:00+05:30"},
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
        }
        event = create_event(
            service,
            "Interview",
            __import__("datetime").datetime.fromisoformat("2026-03-10T14:00:00+05:30"),
            __import__("datetime").datetime.fromisoformat("2026-03-10T15:00:00+05:30"),
            "Asia/Kolkata",
            ["a@example.com", "b@example.com"],
        )
        self.assertEqual(event.event_id, "evt1")
        kwargs = service.events.return_value.insert.call_args.kwargs
        self.assertEqual(kwargs["calendarId"], "primary")
        self.assertEqual(kwargs["conferenceDataVersion"], 1)
        self.assertEqual(kwargs["sendUpdates"], "all")
        self.assertEqual(len(kwargs["body"]["attendees"]), 2)
