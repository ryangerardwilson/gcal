import unittest

from gcal_cli.auth import SCOPES


class AuthTests(unittest.TestCase):
    def test_scopes_include_openid(self) -> None:
        self.assertIn("openid", SCOPES)
