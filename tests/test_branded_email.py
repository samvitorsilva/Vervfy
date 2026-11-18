"""Regression tests for Vervfy's branded transactional emails."""
import unittest
from unittest.mock import patch
from email_smtp import build_email_verification_message, build_password_reset_message


class BrandedEmailTests(unittest.TestCase):
    def test_verification_email_uses_public_logo_and_preserves_token(self):
        with patch.dict("os.environ", {"FRONTEND_URL": "https://vervfy.com", "VERVFY_ENVIRONMENT": "production"}):
            message = build_email_verification_message(
                to_email="user@example.com",
                verification_url="https://vervfy.com/reset-password#verify=synthetic",
                mail_from="Vervfy <no-reply@vervfy.com>",
            )
        html = message.get_body(preferencelist=("html",)).get_content()
        plain = message.get_body(preferencelist=("plain",)).get_content()
        self.assertIn('src="https://vervfy.com/apple-icon.png"', html)
        self.assertIn("Verify your email", html)
        self.assertIn('href="https://vervfy.com/reset-password#verify=synthetic"', html)
        self.assertIn("verify=synthetic", plain)
        self.assertNotIn("<html", plain)

    def test_reset_email_escapes_html_without_changing_plain_text(self):
        with patch.dict("os.environ", {"FRONTEND_URL": "https://vervfy.com", "VERVFY_ENVIRONMENT": "production"}):
            message = build_password_reset_message(
                to_email="user@example.com",
                reset_url="https://vervfy.com/reset-password#token=a&b",
                mail_from="Vervfy <no-reply@vervfy.com>",
            )
        html = message.get_body(preferencelist=("html",)).get_content()
        plain = message.get_body(preferencelist=("plain",)).get_content()
        self.assertIn("https://vervfy.com/apple-icon.png", html)
        self.assertIn("Choose a new password", html)
        self.assertIn("token=a&amp;b", html)
        self.assertIn("token=a&b", plain)


if __name__ == "__main__":
    unittest.main()
