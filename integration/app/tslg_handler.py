import logging
import socket
import json
import uuid
import os
import time
import threading
from datetime import datetime
import random
import re

class TSLGBufferedSocketHandler(logging.Handler):
    def __init__(self, host, port, max_buffer_size=500, flush_interval_ms=100,
                 connection_ttl_ms=2000, reconnection_delay_ms=2000,
                 socket_timeout_ms=5000, max_connection_attempts=10):
        super().__init__()
        self.host = host
        self.port = port
        self.max_buffer_size = max_buffer_size
        self.flush_interval_ms = flush_interval_ms
        self.connection_ttl_ms = connection_ttl_ms
        self.reconnection_delay_ms = reconnection_delay_ms
        self.socket_timeout_ms = socket_timeout_ms
        self.max_connection_attempts = max_connection_attempts

        self.buffer = []
        self.buffer_lock = threading.Lock()
        self.socket = None
        self.connection_start_time = 0
        self.connection_attempts = 0
        self._shutdown = False

        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.health_check_thread = threading.Thread(target=self._health_check_worker, daemon=True)
        self.flush_thread.start()
        self.health_check_thread.start()

    def _should_reconnect(self):
        """Проверка необходимости переподключения для балансировки"""
        if not self.socket:
            return True

        current_time = time.time()
        connection_age = (current_time - self.connection_start_time) * 1000

        if connection_age >= self.connection_ttl_ms:
            return True

        return False

    def _health_check_worker(self):
        """Фоновая проверка здоровья соединения и балансировка"""
        while not self._shutdown:
            try:
                if self._should_reconnect():
                    self._reconnect()
                time.sleep(0.5)
            except Exception as e:
                logging.debug(f"TSLG health check error: {e}")

    def _reconnect(self):
        """Безопасное переподключение с отправкой текущего буфера"""
        if self.socket:
            try:
                self._flush_current_buffer()
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None

        self._create_socket()

    def _flush_current_buffer(self):
        """Отправка текущего содержимого буфера"""
        with self.buffer_lock:
            if self.buffer:
                batch_to_send = self.buffer[:]
                self.buffer = []
                self._send_batch_sync(batch_to_send)

    def _send_batch_sync(self, batch_data):
        """Синхронная отправка пачки логов"""
        if not batch_data:
            return

        try:
            if not self._ensure_connection():
                return

            log_data = '\n'.join(batch_data) + '\n'

            self.socket.sendall(log_data.encode('utf-8'))

        except Exception as e:
            with self.buffer_lock:
                self.buffer = batch_data + self.buffer
            self.socket = None

    def _create_socket(self):
        """Создание нового сокет-соединения"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.socket_timeout_ms / 1000.0)
            self.socket.connect((self.host, self.port))
            self.connection_start_time = time.time()
            self.connection_attempts = 0
            return True
        except Exception as e:
            self.connection_attempts += 1
            if self.connection_attempts >= self.max_connection_attempts:
                self.handleError(f"Max connection attempts reached: {e}")
            return False

    def _ensure_connection(self):
        """Проверка и восстановление соединения"""
        if not self.socket or self._should_reconnect():
            return self._create_socket()

        try:
            self.socket.getpeername()
            return True
        except:
            return self._create_socket()

    def _send_batch(self, batch_data):
        """Асинхронная отправка пачки логов"""
        if not batch_data:
            return

        try:
            if not self._ensure_connection():
                with self.buffer_lock:
                    self.buffer = batch_data + self.buffer
                return

            log_data = '\n'.join(batch_data) + '\n'

            self.socket.sendall(log_data.encode('utf-8'))

        except Exception as e:
            with self.buffer_lock:
                self.buffer = batch_data + self.buffer
            self.socket = None
            time.sleep(self.reconnection_delay_ms / 1000.0)

    def _flush_worker(self):
        """Фоновая задача для периодической отправки буфера"""
        while not self._shutdown:
            try:
                time.sleep(self.flush_interval_ms / 1000.0)
                self.flush()
            except Exception as e:
                pass

    def emit(self, record):
        """Обработка новой записи лога"""
        if self._shutdown:
            return

        try:
            formatted_record = self.format(record)

            with self.buffer_lock:
                self.buffer.append(formatted_record)

                if len(self.buffer) >= self.max_buffer_size:
                    batch_to_send = self.buffer[:]
                    self.buffer = []
                    threading.Thread(target=self._send_batch, args=(batch_to_send,), daemon=True).start()

        except Exception as e:
            self.handleError(record)

    def flush(self):
        """Принудительная отправка буфера"""
        with self.buffer_lock:
            if self.buffer:
                batch_to_send = self.buffer[:]
                self.buffer = []
                self._send_batch_sync(batch_to_send)

    def close(self):
        """Закрытие обработчика"""
        self._shutdown = True
        self.flush()
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        super().close()

class TSLGJSONLogFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()

        self.app_name = os.getenv('APP_NAME', 'integration')
        self.ris_code = os.getenv('RIS_CODE', '1404')
        self.project_code = os.getenv('PROJECT_CODE', 'sum')

        self.namespace = os.getenv('KUBERNETES_NAMESPACE', 'dk1-sumd01-sumd-core')
        self.pod_ip = os.getenv('POD_IP', '10.244.1.25')
        self.node_name = os.getenv('NODE_NAME', 'dk1-sumd01-node-05')
        self.pod_name = os.getenv('POD_NAME', 'surm-backend-7c8b5d9f6-abc123')

        self.tslg_client_version = os.getenv('TSLG_CLIENT_VERSION', '1.0.0')
        self.enable_trace_fields = os.getenv('TSLG_ENABLE_TRACE_FIELDS', 'true').lower() == 'true'
        self.enable_full_context = os.getenv('TSLG_ENABLE_FULL_CONTEXT', 'true').lower() == 'true'

        self.app_type = 'PYTHON'
        self.env_type = 'K8S'
        self.agr_type = 'TRACING'

    def format(self, record):
        log_data = {
            'eventId': str(uuid.uuid4()),
            'appName': self.app_name,
            'level': record.levelname,
            'text': self._format_message(record),
            'localTime': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'tslgClientVersion': self.tslg_client_version,
            'namespace': self.namespace,
            'risCode': self.ris_code,
            'projectCode': self.project_code,

            'appType': self.app_type,
            'envType': self.env_type,
            'agrType': self.agr_type,

            'loggerName': record.name,
            'threadName': record.threadName if hasattr(record, 'threadName') else str(record.thread),
            'callerClass': record.module,
            'callerMethod': record.funcName,
            'callerLine': record.lineno,
        }

        tec_data = {}
        if self.pod_ip:
            tec_data['podIp'] = self.pod_ip
        if self.node_name:
            tec_data['nodeName'] = self.node_name
        if self.pod_name:
            tec_data['podName'] = self.pod_name

        if tec_data:
            log_data['tec'] = tec_data

        if self.enable_full_context:
            mdc = self._get_mdc_data(record)
            if mdc:
                log_data['mdc'] = mdc

        if record.exc_info:
            log_data['stack'] = self.formatException(record.exc_info)

        if self.enable_trace_fields:
            self._add_trace_fields(log_data, record)

        log_data = {k: v for k, v in log_data.items() if v is not None}

        return json.dumps(log_data, ensure_ascii=False)

    def _format_message(self, record):
        """Форматирование основного сообщения с санитизацией"""
        message = record.getMessage()

        sanitize_enabled = os.getenv('TSLG_SANITIZE_SENSITIVE_DATA', 'true').lower() == 'true'
        if sanitize_enabled and message:
            message = self._sanitize_sensitive_data(message)

        return message

    def _sanitize_sensitive_data(self, text):
        """Санитизация чувствительных данных"""
        if not text or not isinstance(text, str):
            return text

        patterns = {
            'password': r'("password"\s*:\s*")[^"]*(")',
            'token': r'("token"\s*:\s*")[^"]*(")',
            'authorization': r'(Authorization:\s*)[^\s]+',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        }

        sanitized_text = text
        for key, pattern in patterns.items():
            if key in ['password', 'token']:
                sanitized_text = re.sub(pattern, r'\1***\2', sanitized_text, flags=re.IGNORECASE)
            elif key == 'authorization':
                sanitized_text = re.sub(pattern, r'\1***', sanitized_text, flags=re.IGNORECASE)
            elif key == 'email':
                sanitized_text = re.sub(pattern, '***@***.***', sanitized_text)

        return sanitized_text

    def _get_mdc_data(self, record):
        """Получение MDC данных из record"""
        mdc = {}

        extra_fields = ['process', 'processName', 'pathname', 'filename']
        for field in extra_fields:
            if hasattr(record, field):
                mdc[field] = getattr(record, field)

        for key, value in record.__dict__.items():
            if key not in ['args', 'asctime', 'created', 'exc_info', 'exc_text',
                          'filename', 'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'msg', 'name', 'pathname',
                          'process', 'processName', 'relativeCreated', 'stack_info',
                          'thread', 'threadName'] and not key.startswith('_'):
                mdc[key] = str(value)

        return mdc if mdc else None

    def _add_trace_fields(self, log_data, record):
        """Добавление trace полей для корреляции"""
        trace_fields = {}

        if not hasattr(record, 'traceId'):
            trace_fields['traceId'] = str(uuid.uuid4())

        if not hasattr(record, 'spanId'):
            trace_fields['spanId'] = str(uuid.uuid4())[:16]

        for field in ['traceId', 'spanId', 'parentSpanId', 'userId', 'logicTime']:
            value = getattr(record, field, None)
            if value is not None:
                trace_fields[field] = value

        if trace_fields:
            log_data.update(trace_fields)