import os
from logging.config import dictConfig
from pathlib import Path
import queue
from logging.handlers import QueueHandler, QueueListener
import functools
import logging

from flask import Flask

from app.config import Configuration as Conf
from app.tslg_logging import TSLGBufferedSocketHandler, TSLGJSONLogFormatter

os.environ['PYTHONWARNINGS'] = 'ignore:Unverified HTTPS request'
UPLOAD_FOLDER = '/home/user/tmp'

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "main_format": {
            "format": "[%(asctime)s] [%(process)d] [%(levelname)s] in %(module)s: %(message)s",
            "datefmt": "%d-%m-%Y %H:%M:%S",
        },
        "logJSON": {
            "()": "app.logging.JSONLogFormatter"
        },
        "tslg": {
            "()": "app.tslg_logging.TSLGJSONLogFormatter"
        },
    },
    "handlers": {
        "wsgi": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "stream": "ext://flask.logging.wsgi_errors_stream",
            "formatter": "main_format",
        },
    },
    "root": {"level": Conf.LOGGING_LEVEL, "handlers": ["wsgi"]},
}

if Conf.LOGS_DIRECTORY:
    logs_dir: Path = Path(Conf.LOGS_DIRECTORY)
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True)
    log_file_name: Path = logs_dir / Path("notification.log")
    handler_name = 'file'
    file_handler = {
        handler_name: {
            "class": "logging.FileHandler",
            "formatter": "logJSON",
            "filename": str(log_file_name),
        }
    }
    log_config["handlers"].update(file_handler)
    log_config["root"]["handlers"].append(handler_name)

dictConfig(log_config)

log_queue = queue.Queue(maxsize=10000)

tslg_handler = TSLGBufferedSocketHandler(
    host=os.getenv('TSLG_AGENT_HOST', 'tslg-agent-svc-main.dk1-sumd01-sumd-core.svc.cluster.local'),
    port=int(os.getenv('TSLG_AGENT_PORT', '5170')),
    max_buffer_size=int(os.getenv('TSLG_MAX_BUFFER_SIZE', '500')),
    flush_interval_ms=int(os.getenv('TSLG_BUFFER_FLUSH_INTERVAL_MS', '100')),
    connection_ttl_ms=int(os.getenv('TSLG_CONNECTION_TTL_MS', '2000')),
    reconnection_delay_ms=int(os.getenv('TSLG_RECONNECTION_DELAY_MS', '2000')),
    socket_timeout_ms=int(os.getenv('TSLG_SOCKET_TIMEOUT_MS', '5000')),
    max_connection_attempts=int(os.getenv('TSLG_MAX_CONNECTION_ATTEMPTS', '10'))
)

tslg_log_level = os.getenv('TSLG_LOG_LEVEL', 'info').upper()
tslg_handler.setLevel(getattr(logging, tslg_log_level, logging.INFO))

tslg_formatter = TSLGJSONLogFormatter()
tslg_handler.setFormatter(tslg_formatter)

queue_listener = QueueListener(log_queue, tslg_handler)
queue_listener.start()

root_logger = logging.getLogger()
queue_handler = QueueHandler(log_queue)
root_logger.addHandler(queue_handler)

app = Flask(__name__)
app.config.from_object(Conf)

# To allow flask propagating exception even if debug is set to false on notification_services
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.logger.info("TSLG logging configured successfully")
app.logger.info(f"TSLG Agent: {os.getenv('TSLG_AGENT_HOST')}:{os.getenv('TSLG_AGENT_PORT')}")

from app import mail_routs