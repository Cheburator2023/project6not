import datetime
import json
import logging
import os


class TSLGJSONFormatter(logging.Formatter):
    """Formatter for TSLG-compliant JSON logs"""

    def __init__(self) -> None:
        super().__init__()

    def _format_date_time(self, now) -> str:
        return now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def format(self, record) -> str:
        now = datetime.datetime.utcnow()
        json_log_obj = {
            "datetime": self._format_date_time(now),
            "timestamp": datetime.datetime.timestamp(now),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "filename": record.filename,
            "funcname": record.funcName,
            "msg": (
                record.getMessage()
                .replace("\n", "_")
                .replace("\t", "_")
                .replace("\r", "_")
            )
        }
        return json.dumps(json_log_obj)


class SanitizedFormatter(logging.Formatter):
    """Formatter that sanitizes sensitive data"""

    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)

    def _sanitize_message(self, message):
        """Sanitize sensitive data in log messages"""
        if not message:
            return message

        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        message = re.sub(email_pattern, '[EMAIL_REDACTED]', message)

        password_patterns = [
            r'password[=:]\s*[^\s]+',
            r'pwd[=:]\s*[^\s]+',
            r'token[=:]\s*[^\s]+',
            r'api[_-]?key[=:]\s*[^\s]+',
            r'auth[=:]\s*[^\s]+'
        ]

        for pattern in password_patterns:
            message = re.sub(pattern, lambda m: m.group().split('=')[0] + '=[REDACTED]', message, flags=re.IGNORECASE)

        return message

    def format(self, record):
        record.msg = self._sanitize_message(str(record.msg))
        if record.args:
            record.args = tuple(self._sanitize_message(str(arg)) if isinstance(arg, str) else arg
                              for arg in record.args)
        return super().format(record)