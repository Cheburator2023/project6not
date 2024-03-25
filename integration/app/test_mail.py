import pytest

from app.config import Configuration as Conf
from app.smtp_client import SMTPClient


@pytest.mark.parametrize(
    "email_from, email_to, subject, text_content",
    [
        ('', "efwefweffwewfe@yandex.ru", "LETTTER", "hello")
    ]
)
def test_smtp_client(email_from, email_to, subject, text_content):
    smtp = SMTPClient(smtp_host=Conf.SMTP_RELAY_HOST,
                      smtp_port=Conf.SMTP_RELAY_PORT,
                      email_login=Conf.EMAIL_LOGIN,
                      email_password=Conf.EMAIL_PASSWORD,
                      email_from=Conf.EMAIL_FROM,
                      is_external_smtp_relay=Conf.IS_EXTERNAL_SMTP_RELAY,
                      enable_auth=Conf.ENABLE_AUTHENTICATION)

    res = smtp.send_msg(email_from,
                        email_to,
                        subject,
                        text_content)

    assert res.get(email_to, None) is None
    # if there are no errors, the response body will be empty.
