import os
from logging.config import dictConfig
from pathlib import Path

from flask import Flask

from app.config import Configuration as Conf

os.environ['PYTHONWARNINGS'] = 'ignore:Unverified HTTPS request'
UPLOAD_FOLDER = '/home/user/tmp'

log_level = os.getenv('TSLG_LOG_LEVEL', 'INFO').upper()
console_output = os.getenv('TSLG_CONSOLE_OUTPUT', 'true').lower() == 'true'

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "main_format": {
            "()": "app.logging.SanitizedFormatter",
            "format": "[%(asctime)s] [%(process)d] [%(levelname)s] in %(module)s: %(message)s",
            "datefmt": "%d-%m-%Y %H:%M:%S",
        },
        "logJSON": {
            "()": "app.logging.TSLGJSONFormatter"
        },
        "tslg_format": {
            "()": "app.logging.TSLGJSONFormatter"
        }
    },
    "handlers": {
        "wsgi": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "stream": "ext://flask.logging.wsgi_errors_stream",
            "formatter": "tslg_format",
        },
        "tslg": {
            "()": "app.tslg_handler.TSLGHandler",
            "level": log_level,
            "formatter": "tslg_format",
        }
    },
    "root": {
        "level": log_level,
        "handlers": ["tslg"] + (["wsgi"] if console_output else [])
    },
    "loggers": {
        "app": {
            "level": log_level,
            "handlers": ["tslg"] + (["wsgi"] if console_output else []),
            "propagate": False
        },
        "gunicorn": {
            "level": log_level,
            "handlers": ["tslg"] + (["wsgi"] if console_output else []),
            "propagate": False
        },
        "gunicorn.error": {
            "level": log_level,
            "handlers": ["tslg"] + (["wsgi"] if console_output else []),
            "propagate": False
        },
        "gunicorn.access": {
            "level": log_level,
            "handlers": ["tslg"] + (["wsgi"] if console_output else []),
            "propagate": False
        },
        "celery": {
            "level": log_level,
            "handlers": ["tslg"] + (["wsgi"] if console_output else []),
            "propagate": False
        }
    }
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

app = Flask(__name__)
app.config.from_object(Conf)

# To allow flask propagating exception even if debug is set to false on notification_services
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

from app import mail_routs

app.logger.info("TSLG logging configured successfully")
app.logger.info(f"TSLG Agent: {os.getenv('TSLG_AGENT_HOST', 'tslg-agent-svc-main.dk1-sumd01-sumd-core.svc.cluster.local')}:{os.getenv('TSLG_AGENT_PORT', '5170')}")
app.logger.info(f"Buffer size: {os.getenv('TSLG_MAX_BUFFER_SIZE', '500')}, Flush interval: {os.getenv('TSLG_BUFFER_FLUSH_INTERVAL_MS', '100')}ms")
app.logger.info(f"Console output: {console_output}, Log level: {log_level}"