import os
import json
import logging
import socket
import threading
import time
import uuid
from datetime import datetime
from queue import Queue, Empty
from logging import Handler, LogRecord

from app.logging import sanitize_message


class TSLGHandler(Handler):
    def __init__(self):
        super().__init__()

        self.host = os.getenv('TSLG_AGENT_HOST', 'tslg-agent-svc-main.dk1-sumd01-sumd-core.svc.cluster.local')
        self.port = int(os.getenv('TSLG_AGENT_PORT', 5170))
        self.reconnection_delay = int(os.getenv('TSLG_RECONNECTION_DELAY_MS', 2000)) / 1000.0
        self.connection_ttl = int(os.getenv('TSLG_CONNECTION_TTL_MS', 2000)) / 1000.0
        self.max_buffer_size = int(os.getenv('TSLG_MAX_BUFFER_SIZE', 500))
        self.socket_timeout = int(os.getenv('TSLG_SOCKET_TIMEOUT_MS', 5000)) / 1000.0
        self.max_connection_attempts = int(os.getenv('TSLG_MAX_CONNECTION_ATTEMPTS', 10))
        self.buffer_flush_interval = int(os.getenv('TSLG_BUFFER_FLUSH_INTERVAL_MS', 100)) / 1000.0
        self.sanitize_sensitive_data = os.getenv('TSLG_SANITIZE_SENSITIVE_DATA', 'true').lower() == 'true'
        self.sanitize_percentage = int(os.getenv('TSLG_SANITIZE_PERCENTAGE', 60))
        self.enable_trace_fields = os.getenv('TSLG_ENABLE_TRACE_FIELDS', 'true').lower() == 'true'
        self.enable_full_context = os.getenv('TSLG_ENABLE_FULL_CONTEXT', 'true').lower() == 'true'
        self.client_version = os.getenv('TSLG_CLIENT_VERSION', '1.0.0')

        self.app_name = os.getenv('APP_NAME', 'integration')
        self.project_code = os.getenv('PROJECT_CODE', 'sum')
        self.ris_code = os.getenv('RIS_CODE', '1404')
        self.namespace = os.getenv('KUBERNETES_NAMESPACE', 'dk1-sumd01-sumd-core')
        self.pod_ip = os.getenv('POD_IP', '10.244.1.25')
        self.node_name = os.getenv('NODE_NAME', 'dk1-sumd01-node-05')
        self.pod_name = os.getenv('POD_NAME', 'surm-backend-7c8b5d9f6-abc123')

        self.buffer = Queue()
        self.socket = None
        self.last_connection_time = 0
        self.connection_attempts = 0
        self.is_running = True
        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.flush_thread.start()

    def _get_level_mapping(self, level):
        level_mapping = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO',
            'WARNING': 'WARN',
            'ERROR': 'ERROR',
            'CRITICAL': 'FATAL'
        }
        return level_mapping.get(level, 'INFO')

    def _create_log_record(self, record):
        """Create TSLG-compliant log record"""

        log_data = {
            "eventId": str(uuid.uuid4()),
            "appName": self.app_name,
            "level": self._get_level_mapping(record.levelname),
            "text": sanitize_message(record.getMessage()) if self.sanitize_sensitive_data else record.getMessage(),
            "localTime": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "namespace": self.namespace,
            "risCode": self.ris_code,
            "projectCode": self.project_code,
            "tslgClientVersion": self.client_version,
            "appType": "PYTHON",
            "envType": "K8S",
            "agrType": "TRACING",
            "loggerName": record.name,
            "threadName": record.threadName if hasattr(record, 'threadName') else str(record.thread),
        }

        if self.enable_trace_fields:
            log_data.update({
                "callerMethod": record.funcName,
                "callerLine": record.lineno,
            })

        if self.enable_full_context:
            log_data.update({
                "podIp": self.pod_ip,
                "nodeName": self.node_name,
                "podName": self.pod_name,
            })

            if record.exc_info and record.exc_info[0]:
                import traceback
                log_data["stack"] = ''.join(traceback.format_exception(*record.exc_info))

        return log_data

    def _ensure_connection(self):
        """Ensure we have a valid connection to TSLG agent"""
        current_time = time.time()

        if (self.socket and
            current_time - self.last_connection_time > self.connection_ttl):
            self._close_connection()

        if not self.socket:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.socket_timeout)
                self.socket.connect((self.host, self.port))
                self.last_connection_time = current_time
                self.connection_attempts = 0
            except Exception as e:
                self._close_connection()
                self.connection_attempts += 1
                if self.connection_attempts <= self.max_connection_attempts:
                    time.sleep(self.reconnection_delay)
                raise e

    def _close_connection(self):
        """Close current connection"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def _send_batch(self, batch):
        """Send batch of logs to TSLG agent"""
        if not batch:
            return

        try:
            self._ensure_connection()
            log_data = '\n'.join([json.dumps(record) for record in batch]) + '\n'
            self.socket.sendall(log_data.encode('utf-8'))
        except Exception as e:
            self._close_connection()
            for record in batch:
                self.buffer.put(record)
            raise e

    def _flush_worker(self):
        """Background worker to flush logs periodically"""
        while self.is_running:
            try:
                batch = []
                start_time = time.time()

                while (len(batch) < self.max_buffer_size and
                       time.time() - start_time < self.buffer_flush_interval):
                    try:
                        record = self.buffer.get(timeout=0.1)
                        batch.append(record)
                    except Empty:
                        break

                if batch:
                    self._send_batch(batch)

            except Exception:
                time.sleep(self.reconnection_delay)

    def emit(self, record):
        """Process log record"""
        if not self.is_running:
            return

        try:
            log_record = self._create_log_record(record)
            self.buffer.put(log_record)
        except Exception:
            self.handleError(record)

    def close(self):
        """Cleanup handler"""
        self.is_running = False
        if self.flush_thread.is_alive():
            self.flush_thread.join(timeout=5.0)
        self._close_connection()
        super().close()