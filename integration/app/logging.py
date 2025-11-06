import datetime
import json
import logging
import os
import re
import uuid


def sanitize_message(message):
    """Sanitize sensitive data in log messages"""
    if not message:
        return message

    if isinstance(message, str):
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


class TSLGJSONFormatter(logging.Formatter):
    """Formatter for TSLG-compliant JSON logs"""

    def __init__(self) -> None:
        super().__init__()

    def _format_date_time(self, now) -> str:
        return now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def _get_level_mapping(self, level):
        level_mapping = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO',
            'WARNING': 'WARN',
            'ERROR': 'ERROR',
            'CRITICAL': 'FATAL'
        }
        return level_mapping.get(level, 'INFO')

    def format(self, record) -> str:
        try:
            now = datetime.datetime.utcnow()

            # Get environment variables with defaults
            app_name = os.getenv('APP_NAME', 'integration')
            project_code = os.getenv('PROJECT_CODE', 'sum')
            ris_code = os.getenv('RIS_CODE', '1404')
            namespace = os.getenv('KUBERNETES_NAMESPACE', 'dk1-sumd01-sumd-core')
            pod_ip = os.getenv('POD_IP', '10.244.1.25')
            node_name = os.getenv('NODE_NAME', 'dk1-sumd01-node-05')
            pod_name = os.getenv('POD_NAME', 'surm-backend-7c8b5d9f6-abc123')

            json_log_obj = {
                "eventId": str(uuid.uuid4()),
                "appName": app_name,
                "level": self._get_level_mapping(record.levelname),
                "text": sanitize_message(record.getMessage()),
                "localTime": self._format_date_time(now),
                "namespace": namespace,
                "risCode": ris_code,
                "projectCode": project_code,
                "tslgClientVersion": "1.0.0",
                "appType": "PYTHON",
                "envType": "K8S",
                "agrType": "TRACING",
                "loggerName": record.name,
                "threadName": record.threadName if hasattr(record, 'threadName') else str(record.thread),
                "callerMethod": record.funcName,
                "callerLine": record.lineno,
                "podIp": pod_ip,
                "nodeName": node_name,
                "podName": pod_name
            }

            # Add stack trace if available
            if record.exc_info and record.exc_info[0]:
                import traceback
                json_log_obj["stack"] = ''.join(traceback.format_exception(*record.exc_info))

            return json.dumps(json_log_obj, ensure_ascii=False)
        except Exception as e:
            # Fallback to basic format if JSON formatting fails
            return f"[FALLBACK] {record.levelname} in {record.name}: {record.getMessage()}"


class SanitizedFormatter(logging.Formatter):
    """Formatter that sanitizes sensitive data"""

    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)

    def format(self, record):
        record.msg = sanitize_message(str(record.msg))
        if record.args:
            record.args = tuple(sanitize_message(str(arg)) if isinstance(arg, str) else arg
                              for arg in record.args)
        return super().format(record)