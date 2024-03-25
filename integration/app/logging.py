import datetime
import json
import logging


class JSONLogFormatter(logging.Formatter):

    def __init__(self) -> None:
        pass

    def _format_date_time(self, now) -> str:
        return (
            f"{now:%Y-%m-%d %H:%M:%S}"
        )

    def format(self, record) -> str:
        now = datetime.datetime.utcnow()
        json_log_obj: dict = {
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
