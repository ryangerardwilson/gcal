import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from gcal_cli.auth import SCOPES, build_calendar_service, build_drive_service, load_credentials
from gcal_cli.config import AccountConfig


class AuthTests(unittest.TestCase):
    def test_scopes_include_openid(self) -> None:
        self.assertIn("openid", SCOPES)
        self.assertIn("https://www.googleapis.com/auth/drive.meet.readonly", SCOPES)

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

    def test_build_drive_service_imports_build(self) -> None:
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
            build_drive_service(account)
        build_mock.assert_called_once_with("drive", "v3", credentials=unittest.mock.ANY, cache_discovery=False)

    def test_load_credentials_reauths_when_token_missing_required_scope(self) -> None:
        account = AccountConfig(
            preset="1",
            email="user@example.com",
            client_secret_file=Path("/tmp/client.json"),
        )
        credentials = MagicMock()
        credentials.has_scopes.return_value = False
        credentials.valid = True
        authorized = MagicMock()
        authorized.email = "user@example.com"
        authorized.credentials = object()
        google = ModuleType("google")
        auth = ModuleType("google.auth")
        transport = ModuleType("google.auth.transport")
        requests = ModuleType("google.auth.transport.requests")
        oauth2 = ModuleType("google.oauth2")
        credentials_mod = ModuleType("google.oauth2.credentials")
        requests.Request = MagicMock()
        credentials_mod.Credentials = MagicMock()
        credentials_mod.Credentials.from_authorized_user_file.return_value = credentials
        oauth2.credentials = credentials_mod
        transport.requests = requests
        auth.transport = transport
        google.auth = auth
        google.oauth2 = oauth2
        with patch("gcal_cli.auth.authorize_account", return_value=authorized), patch.dict(
            "sys.modules",
            {
                "google": google,
                "google.auth": auth,
                "google.auth.transport": transport,
                "google.auth.transport.requests": requests,
                "google.oauth2": oauth2,
                "google.oauth2.credentials": credentials_mod,
            },
        ), patch("gcal_cli.auth.ensure_dirs"), patch(
            "gcal_cli.auth.token_file_for_email", return_value=Path("/tmp/token.json")
        ), patch("pathlib.Path.exists", return_value=True):
            loaded = load_credentials(account)
        self.assertIs(loaded, authorized.credentials)
