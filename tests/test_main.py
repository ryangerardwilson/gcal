import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from gcal_cli.config import AccountConfig, AppConfig
from gcal_cli.errors import UsageError
from main import main


class MainTests(unittest.TestCase):
    def _config(self) -> AppConfig:
        return AppConfig(
            path=Path("/tmp/config.json"),
            accounts={
                "1": AccountConfig(
                    preset="1",
                    email="user@example.com",
                    client_secret_file=Path("/tmp/client.json"),
                )
            },
            timezone="Asia/Kolkata",
        )

    def test_create_event_command(self) -> None:
        created = MagicMock()
        created.event_id = "evt1"
        created.meeting_url = "https://meet.google.com/abc-defg-hij"
        with patch("main.load_config", return_value=self._config()), patch(
            "gcal_cli.auth.build_calendar_service", return_value=MagicMock()
        ), patch("gcal_cli.calendar_api.create_event", return_value=created) as create_mock:
            code = main(["1", "Interview", "2026-03-10 14:00:00", "2026-03-10 15:00:00", "a@example.com"])
        self.assertEqual(code, 0)
        create_mock.assert_called_once()

    def test_list_command(self) -> None:
        with patch("main.load_config", return_value=self._config()), patch(
            "gcal_cli.auth.build_calendar_service", return_value=MagicMock()
        ), patch("gcal_cli.calendar_api.list_upcoming_events", return_value=[]):
            code = main(["1", "ls", "5"])
        self.assertEqual(code, 0)

    def test_list_non_recurring_command(self) -> None:
        with patch("main.load_config", return_value=self._config()), patch(
            "gcal_cli.auth.build_calendar_service", return_value=MagicMock()
        ), patch("gcal_cli.calendar_api.list_upcoming_events", return_value=[]) as list_mock:
            code = main(["1", "ls", "-nr", "5"])
        self.assertEqual(code, 0)
        self.assertEqual(list_mock.call_args.kwargs["include_recurring"], False)

    def test_delete_command(self) -> None:
        with patch("main.load_config", return_value=self._config()), patch(
            "gcal_cli.auth.build_calendar_service", return_value=MagicMock()
        ), patch("gcal_cli.calendar_api.delete_event") as delete_mock:
            code = main(["1", "d", "evt1"])
        self.assertEqual(code, 0)
        delete_mock.assert_called_once()

    def test_reschedule_command(self) -> None:
        event = MagicMock()
        event.event_id = "evt1"
        event.meeting_url = "https://meet.google.com/abc-defg-hij"
        with patch("main.load_config", return_value=self._config()), patch(
            "gcal_cli.auth.build_calendar_service", return_value=MagicMock()
        ), patch("gcal_cli.calendar_api.reschedule_event", return_value=event) as reschedule_mock:
            code = main(["1", "r", "evt1", "2026-03-11 10:00:00", "2026-03-11 11:00:00"])
        self.assertEqual(code, 0)
        reschedule_mock.assert_called_once()

    def test_ls_requires_count(self) -> None:
        with patch("main.load_config", return_value=self._config()), patch(
            "gcal_cli.auth.build_calendar_service", return_value=MagicMock()
        ), self.assertRaises(UsageError):
            main(["1", "ls"])

    def test_auth_prompt_accepts_utc_offset(self) -> None:
        authorized = MagicMock()
        authorized.email = "user@example.com"
        account = MagicMock()
        account.preset = "1"
        account.email = "user@example.com"
        with patch("main.input", return_value="+0530"), patch(
            "main.Path.exists", return_value=True
        ), patch("main.Path.is_file", return_value=True), patch(
            "gcal_cli.auth.authorize_account", return_value=authorized
        ), patch(
            "main.upsert_authenticated_account", return_value=account
        ) as upsert_mock:
            code = main(["auth", "/tmp/client.json"])
        self.assertEqual(code, 0)
        self.assertEqual(upsert_mock.call_args.args[2], "+05:30")

    def test_help_is_human_friendly(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["-h"])
        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("Google Calendar event CLI", output)
        self.assertIn("create an event, invite attendees, and request a Google Meet link", output)
        self.assertIn("gcal 1 ls -nr 5", output)
        self.assertNotIn("usage:", output)
