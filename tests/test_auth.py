import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from gcal_cli.auth import SCOPES, build_calendar_service
from gcal_cli.config import AccountConfig


class AuthTests(unittest.TestCase):
    def test_scopes_include_openid(self) -> None:
        self.assertIn("openid", SCOPES)

    def test_build_calendar_service_imports_build(self) -> None:
        account = AccountConfig(
            preset="1",
            email="user@example.com",
            client_secret_file=Path("/tmp/client.json"),
        )
        build_mock = MagicMock()
        googleapiclient = ModuleType("googleapiclient")
        discovery = ModuleType("googleapiclient.discovery")
        discovery.build = build_mock
        googleapiclient.discovery = discovery
        with patch("gcal_cli.auth.load_credentials", return_value=object()), patch.dict(
            "sys.modules",
            {
                "googleapiclient": googleapiclient,
                "googleapiclient.discovery": discovery,
            },
        ):
            build_calendar_service(account)
        build_mock.assert_called_once()
