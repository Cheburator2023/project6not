import re
import smtplib
from email.message import EmailMessage
from app import app


def remove_cyrillic(word: str) -> str:
    if re.search(r"[а-яА-ЯёЁ]", word):
        symbols = ("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
                   "abvgdeejzijklmnoprstufhzcss_y_euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y_EUA")
        tr = {ord(a): ord(b) for a, b in zip(*symbols)}
        return word.translate(tr)
    else:
        return word


def create_email_message(email_from: str, email_to: str, email_subject: str, email_for_content: str,
                         email_content: str) -> str:
    msg = EmailMessage()
    msg['FROM'] = email_from
    msg['TO'] = email_to
    msg['Subject'] = email_subject
    email_content = f'Message from "{email_for_content}"\n{email_content}'
    msg.set_content(email_content)
    return msg.as_string()


class SMTPClient:
    def __init__(self, smtp_host: str, smtp_port: int, email_login: str, email_password: str, email_from: str,
                 is_external_smtp_relay: bool, enable_auth: bool):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.login = email_login
        self.password = email_password
        self.email_from = email_from
        self.is_external_smtp_relay = is_external_smtp_relay
        self.enable_auth = enable_auth
        self.smtp_obj = None

    @classmethod
    def create_from_object(cls, obj):
        return cls(smtp_host=obj.config['SMTP_RELAY_HOST'],
                   smtp_port=obj.config['SMTP_RELAY_PORT'],
                   email_login=obj.config['EMAIL_LOGIN'],
                   email_password=obj.config['EMAIL_PASSWORD'],
                   email_from=obj.config['EMAIL_FROM'],
                   is_external_smtp_relay=obj.config['IS_EXTERNAL_SMTP_RELAY'],
                   enable_auth=obj.config['ENABLE_AUTHENTICATION'])

    def start_connection(self) -> None:
        app.logger.debug(f"initialize SMTP instance with {self.smtp_host}:{self.smtp_port}")
        self.smtp_obj = smtplib.SMTP(self.smtp_host, self.smtp_port)
        try:
            app.logger.debug(f"start TLS")
            self.smtp_obj.starttls()
        except Exception as e:
            app.logger.exception(e)

        if self.enable_auth:
            try:
                app.logger.debug(f"login to SMTP")
                self.smtp_obj.login(self.login, self.password)
            except Exception as e:
                app.logger.exception(e)

    def close_connection(self) -> None:
        try:
            app.logger.debug(f"close SMTP connection")
            self.smtp_obj.quit()
        except Exception as e:
            app.logger.exception("Can't run quit for SMTP connection")
            app.logger.exception(e)

    def send_msg(self, email_from: str, email_to: str, email_subject: str, email_content: str) -> dict:
        app.logger.debug(f"start SMTP connection")
        self.start_connection()
        try:
            app.logger.debug(f"generate email for send")
            email_message = create_email_message(self.email_from, email_to, email_subject, email_from, email_content)
            app.logger.debug(f"send email")
            res = self.smtp_obj.sendmail(self.email_from, email_to, email_message)
        finally:
            self.close_connection()
        return res

    def send_msg2(self, email_from: str, email_to: str, email_subject: str, email_content: str):
        app.logger.debug(f"generate email for send")
        email_message = create_email_message(self.email_from, email_to, email_subject, email_from, email_content)
        app.logger.debug(f"send email")
        self.smtp_obj.sendmail(self.email_from, email_to, email_message)
