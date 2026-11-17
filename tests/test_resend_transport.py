"""Mocked Resend transport regression coverage; no network calls."""
import unittest
from unittest.mock import patch

import httpx

import email_smtp


class ResendTransportTests(unittest.TestCase):
    def setUp(self):
        self.settings = email_smtp.ResendSettings(
            api_key="re_synthetic", mail_from="Vervfy <no-reply@vervfy.com>"
        )
        self.message = email_smtp.build_email_verification_message(
            to_email="recipient@example.com",
            verification_url="https://vervfy.com/reset-password#verify=synthetic",
            mail_from=self.settings.mail_from,
        )

    def test_success_and_payload(self):
        def handler(request):
            self.assertEqual(request.url, httpx.URL(email_smtp.RESEND_SEND_URL))
            self.assertEqual(request.headers["Authorization"], "Bearer re_synthetic")
            payload = __import__("json").loads(request.content)
            self.assertEqual(payload["to"], ["recipient@example.com"])
            self.assertEqual(payload["from"], self.settings.mail_from)
            self.assertIn("verify=synthetic", payload["html"])
            return httpx.Response(200, json={"id": "email_synthetic"})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            email_smtp.ResendApiTransport(self.settings, client=client).send(self.message)

    def test_error_codes(self):
        for status, reason in (
            (401, email_smtp.SMTP_REASON_AUTHENTICATION_FAILURE),
            (429, email_smtp.SMTP_REASON_RATE_LIMITED),
            (422, email_smtp.SMTP_REASON_MESSAGE_REJECTED),
            (503, email_smtp.SMTP_REASON_PROVIDER_ERROR),
        ):
            with self.subTest(status=status):
                with httpx.Client(
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(status, json={"message": "secret"})
                    )
                ) as client:
                    with self.assertRaises(email_smtp.SmtpSendError) as raised:
                        email_smtp.ResendApiTransport(self.settings, client=client).send(
                            self.message
                        )
                self.assertEqual(raised.exception.reason, reason)
                self.assertNotIn("secret", str(raised.exception))

    def test_malformed_success_rejected(self):
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
        ) as client:
            with self.assertRaises(email_smtp.SmtpSendError) as raised:
                email_smtp.ResendApiTransport(self.settings, client=client).send(
                    self.message
                )
        self.assertEqual(raised.exception.reason, email_smtp.SMTP_REASON_MALFORMED_RESPONSE)

    def test_missing_key_fails_closed(self):
        with patch.dict("os.environ", {"RESEND_API_KEY": ""}):
            with self.assertRaises(email_smtp.SmtpConfigError):
                email_smtp.ResendSettings().require_ready()

    def test_transport_selection(self):
        with patch.dict("os.environ", {"EMAIL_TRANSPORT": "resend"}):
            self.assertIsInstance(
                email_smtp.build_default_transport(), email_smtp.ResendApiTransport
            )

    def test_production_sender_restricted(self):
        with patch.dict("os.environ", {"VERVFY_ENVIRONMENT": "production"}):
            with self.assertRaises(email_smtp.SmtpConfigError):
                email_smtp.ResendSettings(
                    api_key="re_synthetic", mail_from="vervfy.dev@proton.me"
                ).require_ready()


if __name__ == "__main__":
    unittest.main()
