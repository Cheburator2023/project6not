import os
from distutils.util import strtobool


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, default)
    try:
        value = strtobool(str(value))
    except ValueError:
        value = default
    return bool(value)


class Configuration:
    # SMTP CONFIG #
    SMTP_RELAY_HOST = os.getenv('smtp_relay_host')
    SMTP_RELAY_PORT = int(os.getenv('smtp_relay_port'))
    IS_EXTERNAL_SMTP_RELAY = get_env_bool('is_external_smtp_relay', False)
    EMAIL_LOGIN = os.getenv('email_login')  # email for login
    EMAIL_PASSWORD = os.getenv('email_password')  # password for login
    ENABLE_AUTHENTICATION = get_env_bool('enable_authentication', True)
    EMAIL_FROM = os.getenv('email_from')  # email for name in FROM:

    # REDIS CONFIG #
    REDIS_HOST = os.getenv("redis_host", "redis.ds1-lpad01-sumd-system.svc.cluster.local")
    REDIS_PORT = int(os.getenv("redis_port", 6379))
    REDIS_HEALTHCHECK_INTERVAL = int(os.getenv("redis_healthcheck_interval", 30))
    REDIS_MESSAGE_TTL = int(os.getenv("redis_message_ttl", 43200))
    REDIS_PASSWORD = os.getenv("redis_password")
    redis_password = REDIS_PASSWORD
    REDIS_USERNAME = os.getenv("redis_username")
    redis_username = REDIS_USERNAME

    # CELERY CONFIG #
    CELERY_REDIS_USERNAME = REDIS_USERNAME
    CELERY_REDIS_PASSWORD = REDIS_PASSWORD

    celery_base_url = "redis://"
    if REDIS_PASSWORD:
        user_name = "" if not REDIS_USERNAME else REDIS_USERNAME
        celery_base_url = f"{celery_base_url}{user_name}:{REDIS_PASSWORD}@"
    celery_base_url = f"{celery_base_url}{REDIS_HOST}:{REDIS_PORT}"
    CELERY_BROKER_URL = f"{celery_base_url}/0"
    BROKER_URL = CELERY_BROKER_URL  # для совместимости с инициализацией celery.config_from_object
    broker_url = CELERY_BROKER_URL
    CELERY_RESULT_BACKEND = f"{celery_base_url}/1"
    result_backend = CELERY_RESULT_BACKEND

    task_soft_time_limit = int(os.getenv('task_soft_time_limit', 300))
    task_time_limit = int(os.getenv('task_time_limit', 600))
    max_retries = int(os.getenv('max_retries', 10))
    time_to_retries = int(os.getenv('time_to_retries', 180))
    time_to_retries_range = int(os.getenv('time_to_retries_range', 30))

    # NOTIFICATION SERVICE CONFIG #
    NOTIFY_PATH_TO_LOG = os.getenv('notify_path_to_log', '/app/logs/log-notification')

    # CACHE CONFIG #
    CACHE_PREFIX = os.getenv("cache_prefix", "notification-service")

    # LOGGING CONFIG #
    LOGGING_LEVEL = os.getenv('logging_level', 'INFO')
    LOGS_DIRECTORY = os.environ.get("logs_directory", "")  # /app/logs

    # TSLG CONFIG #
    TSLG_AGENT_HOST = os.getenv('TSLG_AGENT_HOST', 'tslg-agent-svc-main.dk1-sumd01-sumd-core.svc.cluster.local')
    TSLG_AGENT_PORT = int(os.getenv('TSLG_AGENT_PORT', 5170))
    TSLG_LOG_LEVEL = os.getenv('TSLG_LOG_LEVEL', 'INFO')
    TSLG_CONSOLE_OUTPUT = get_env_bool('TSLG_CONSOLE_OUTPUT', True)