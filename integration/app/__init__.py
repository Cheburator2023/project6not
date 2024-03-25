import os
from logging.config import dictConfig
from pathlib import Path

from flask import Flask

from app.config import Configuration as Conf

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

app = Flask(__name__)
app.config.from_object(Conf)

# To allow flask propagating exception even if debug is set to false on notification_services
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

from app import mail_routs
