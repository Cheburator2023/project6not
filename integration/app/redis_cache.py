from enum import Enum
from functools import lru_cache
from json import dumps
from typing import Any, Dict, List, Optional, Tuple, Union

from redis import ConnectionError, ConnectionPool
from redis import Redis as RedisClient

from app import app
from app.config import Configuration as Conf


def decode_bytes(data: Optional[bytes]) -> Optional[str]:
    if data is not None:
        data = data.decode("utf-8")
    return data


@lru_cache(1)
def get_client(redis_db: int = 0) -> RedisClient:
    pool: ConnectionPool = ConnectionPool(
        host=Conf.REDIS_HOST, port=Conf.REDIS_PORT, db=redis_db, username=Conf.REDIS_USERNAME,
        password=Conf.REDIS_PASSWORD
    )
    client: RedisClient = RedisClient(
        connection_pool=pool, health_check_interval=Conf.REDIS_HEALTHCHECK_INTERVAL
    )
    return client


class TaskStatus(Enum):
    Ok: str = "ok"
    Prepared: str = "prepare for method call"
    ValidationError: str = "validation error"
    ServiceUnavailable: str = "target service unavailable"
    ResentManually: str = "resent manually"
    Canceled: str = "canceled"
    RetryCountExceeded: str = "retry count exceeded"


class Cache(object):
    def __init__(
            self,
            message_prefix: str = "",
            task_id: str = "",
            data: Union[str, Dict[Any, Any]] = "",
            redis_db: int = 7,
    ) -> None:
        try:
            self.redis_client: RedisClient = get_client(redis_db)
        except ConnectionError as err:
            app.logger.exception(f"Error connecting to redis server. {err}")
        if isinstance(data, dict):
            data = dumps(data, sort_keys=True)
        self.data: str = data
        self.task_id: str = task_id
        self.status: TaskStatus = TaskStatus.Ok
        self.message_prefix: str = message_prefix

    def _list_all_keys(self) -> List[Tuple[str, str]]:
        return list({
            (i[0], i[1])
            for i in [
                j.decode("utf-8").split(":")
                for j in self.redis_client.keys(f"*:*")
            ]
        })

    def save_cache(self, status: TaskStatus) -> None:
        try:
            self.redis_client.set(
                f"{self.message_prefix}:{self.task_id}",
                self.data,
                ex=Conf.REDIS_MESSAGE_TTL,
            )
            self.redis_client.set(
                f"{self.message_prefix}:{self.task_id}:status",
                status.value,
                ex=Conf.REDIS_MESSAGE_TTL,
            )
        except ConnectionError as err:
            app.logger.exception(f"Error saving cache in redis. {err}")

    def get_by_data(self) -> Tuple[Optional[str], Optional[TaskStatus]]:
        cache: Optional[str] = None
        status: Optional[TaskStatus] = None
        try:
            cache = decode_bytes(
                self.redis_client.get(f"{self.message_prefix}:{self.task_id}")
            )
            if cache is not None:
                status = decode_bytes(
                    self.redis_client.get(
                        f"{self.message_prefix}:{self.task_id}:status"
                    )
                )
        except ConnectionError as err:
            app.logger.exception(
                f"Error getting cache by data, error connecting "
                f"to redis server. {err}"
            )
        return cache, status

    def get_by_id(self, task_id: str) -> Optional[str]:
        cache: Optional[str] = None
        try:
            cache = decode_bytes(
                self.redis_client.get(f"{self.message_prefix}:{task_id}")
            )
            if cache is not None:
                self.data = cache
        except ConnectionError as err:
            app.logger.exception(
                f"An error occurred while getting the cache by message id. "
                f"Error connecting to redis server. {err}"
            )
        return cache

    def get_all(self) -> List[Dict[str, Optional[str]]]:
        result: List[Dict[str, Optional[str]]] = []
        try:
            keys: List[Tuple[str, str]] = self._list_all_keys()
            for prefix, key in keys:
                cache: Optional[str] = decode_bytes(
                    self.redis_client.get(f"{prefix}:{key}")
                )
                status: Optional[str] = decode_bytes(
                    self.redis_client.get(
                        f"{prefix}:{key}:status"
                    )
                )
                result.append({"key": key, "status": status, "cache": cache})
        except ConnectionError as err:
            app.logger.exception(
                f"Error getting all cache entries. Error connecting to redis "
                f"server. {err}"
            )
        return result

    def delete_by_id(self, task_id: str, prefix: str = "") -> bool:
        try:
            if not prefix:
                prefix = {
                    k.decode("utf-8").split(":")[0] for k in
                    self.redis_client.keys(f"*:{task_id}")
                }.pop()
            deletion_result: int = self.redis_client.delete(
                f"{prefix}:{task_id}",
            )
            if not deletion_result:
                raise KeyError
            self.redis_client.delete(
                f"{prefix}:{task_id}:status"
            )
        except ConnectionError as err:
            app.logger.exception(
                f"Error while trying to delete cache entry by id '{task_id}'."
                f"Error connecting to redis server. {err}"
            )
            return False
        except KeyError:
            app.logger.exception(
                f"Error while trying to delete cache entry. The entry "
                f"with id '{task_id}' was not found in the cache."
            )
            return False
        return True

    def delete_all(self) -> bool:
        try:
            keys: List[Tuple[str, str]] = self._list_all_keys()
        except ConnectionError as err:
            app.logger.exception(
                f"Cache invalidation error. Error connecting to redis "
                f"server. {err}"
            )
            return False
        for prefix, key in keys:
            result: bool = self.delete_by_id(key, prefix)
            if not result:
                return result
        return True

    def get_all_by_error(self) -> List[Dict[str, Optional[str]]]:
        result: List[Dict[str, Optional[str]]] = []
        try:
            keys: List[Tuple[str, str]] = self._list_all_keys()
            for prefix, key in keys:
                cache: Optional[str] = decode_bytes(
                    self.redis_client.get(f"{prefix}:{key}")
                )
                status: Optional[str] = decode_bytes(
                    self.redis_client.get(
                        f"{prefix}:{key}:status"
                    )
                )
                if status not in (TaskStatus.Canceled.value, TaskStatus.Ok.value):
                    result.append({"key": key, "status": status, "cache": cache})
        except ConnectionError as err:
            app.logger.exception(
                f"Error getting all cache entries. Error connecting to redis "
                f"server. {err}"
            )
        return result
