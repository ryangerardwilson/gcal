import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gcal_cli.errors import ApiError
from gcal_cli.transcripts import export_transcript_text, find_transcript_attachment, save_transcript


class TranscriptTests(unittest.TestCase):
    def test_find_transcript_attachment_returns_file_id(self) -> None:
        event = {
            "attachments": [
                {
                    "fileId": "file1",
                    "title": "Meeting Transcript",
                    "mimeType": "application/vnd.google-apps.document",
                }
            ]
        }
        attachment = find_transcript_attachment(event)
        self.assertEqual(attachment.file_id, "file1")

    def test_find_transcript_attachment_raises_when_missing(self) -> None:
        with self.assertRaises(ApiError):
            find_transcript_attachment({"attachments": []})

    def test_export_transcript_text_decodes_bytes(self) -> None:
        drive_service = MagicMock()
        drive_service.files.return_value.export.return_value.execute.return_value = b"hello"
        self.assertEqual(export_transcript_text(drive_service, "file1"), "hello")

    def test_save_transcript_writes_under_transcripts_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("gcal_cli.transcripts.transcripts_dir", return_value=Path(tmpdir)):
            path = save_transcript("hello", "evt1", "Weekly Sync", "2026-03-10T14:00:00+05:30")
        self.assertEqual(path.name, "2026-03-10_weekly-sync_evt1.txt")
