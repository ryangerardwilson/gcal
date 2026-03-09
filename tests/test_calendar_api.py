import unittest
from unittest.mock import MagicMock

from gcal_cli.calendar_api import create_event, extract_attendees, extract_meeting_url, list_upcoming_events


class CalendarApiTests(unittest.TestCase):
    def test_extract_meeting_url_prefers_hangout_link(self) -> None:
        event = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
        self.assertEqual(extract_meeting_url(event), "https://meet.google.com/abc-defg-hij")

    def test_extract_attendees_returns_email_ids(self) -> None:
        event = {"attendees": [{"email": "a@example.com"}, {"email": "b@example.com"}]}
        self.assertEqual(extract_attendees(event), ["a@example.com", "b@example.com"])

    def test_create_event_requests_meet_and_send_updates(self) -> None:
        service = MagicMock()
        execute = service.events.return_value.insert.return_value.execute
        execute.return_value = {
            "id": "evt1",
            "summary": "Interview",
            "start": {"dateTime": "2026-03-10T14:00:00+05:30"},
            "end": {"dateTime": "2026-03-10T15:00:00+05:30"},
            "attendees": [{"email": "a@example.com"}, {"email": "b@example.com"}],
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
        self.assertEqual(event.attendees, ["a@example.com", "b@example.com"])
        kwargs = service.events.return_value.insert.call_args.kwargs
        self.assertEqual(kwargs["calendarId"], "primary")
        self.assertEqual(kwargs["conferenceDataVersion"], 1)
        self.assertEqual(kwargs["sendUpdates"], "all")
        self.assertEqual(len(kwargs["body"]["attendees"]), 2)

    def test_list_upcoming_events_does_not_pass_conference_data_version(self) -> None:
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {"items": []}
        events = list_upcoming_events(service, 5)
        self.assertEqual(events, [])
        kwargs = service.events.return_value.list.call_args.kwargs
        self.assertEqual(kwargs["calendarId"], "primary")
        self.assertEqual(kwargs["maxResults"], 5)
        self.assertNotIn("conferenceDataVersion", kwargs)

    def test_list_upcoming_events_can_exclude_recurring(self) -> None:
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "One-off",
                    "start": {"dateTime": "2026-03-10T14:00:00+05:30"},
                    "end": {"dateTime": "2026-03-10T15:00:00+05:30"},
                    "attendees": [{"email": "solo@example.com"}],
                },
                {
                    "id": "evt2",
                    "summary": "Recurring",
                    "start": {"dateTime": "2026-03-11T14:00:00+05:30"},
                    "end": {"dateTime": "2026-03-11T15:00:00+05:30"},
                    "attendees": [{"email": "series@example.com"}],
                    "recurringEventId": "series1",
                },
            ]
        }
        events = list_upcoming_events(service, 5, include_recurring=False)
        self.assertEqual([event.event_id for event in events], ["evt1"])
        self.assertEqual(events[0].attendees, ["solo@example.com"])
