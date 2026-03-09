import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gcal_cli.config import load_config, token_file_for_email, validate_timezone
from gcal_cli.errors import ConfigError


class ConfigTests(unittest.TestCase):
    def test_validate_timezone(self) -> None:
        self.assertEqual(validate_timezone("Asia/Kolkata", Path("/tmp/config.json")), "Asia/Kolkata")

    def test_validate_timezone_rejects_unknown(self) -> None:
        with self.assertRaises(ConfigError):
            validate_timezone("Mars/Base", Path("/tmp/config.json"))

    def test_token_file_for_email_uses_xdg_data_home(self) -> None:
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-data"}, clear=False):
            self.assertEqual(
                token_file_for_email("User@Example.com"),
                Path("/tmp/xdg-data/gcal/tokens/user@example.com.json"),
            )

    def test_load_config_reads_timezone(self) -> None:
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            secret = Path(tmp) / "client.json"
            secret.write_text("{}", encoding="utf-8")
            config_path.write_text(
                (
                    '{\n'
                    '  "accounts": {\n'
                    '    "1": {\n'
                    '      "email": "user@example.com",\n'
                    f'      "client_secret_file": "{secret}"\n'
                    '    }\n'
                    '  },\n'
                    '  "defaults": {\n'
                    '    "timezone": "Asia/Kolkata"\n'
                    '  }\n'
                    '}\n'
                ),
                encoding="utf-8",
            )
            config = load_config(config_path)
            self.assertEqual(config.timezone, "Asia/Kolkata")
            self.assertEqual(config.accounts["1"].email, "user@example.com")
