import logging
import os
import re
import subprocess
from datetime import datetime
from typing import List, Optional

from app.schemas.logs import LogEntry, LogsRequest

logger = logging.getLogger(__name__)


class LogsService:
    """Сервис для работы с логами приложения"""

    def __init__(self):
        self.log_pattern = re.compile(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(.+?):\s+(.+)"
        )
        self.in_memory_logs = []

    async def get_logs(self, request: LogsRequest) -> tuple[List[LogEntry], int]:
        """
        Получение логов с фильтрацией

        Args:
            request: Параметры запроса логов

        Returns:
            Tuple[List[LogEntry], int]: Список логов и общее количество
        """
        try:
            logs_data = await self._get_application_logs(request)

            filtered_logs = self._filter_logs(logs_data, request)

            total_count = len(filtered_logs)
            start_idx = request.offset or 0
            end_idx = start_idx + (request.limit or 100)
            paginated_logs = filtered_logs[start_idx:end_idx]

            return paginated_logs, total_count

        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return [], 0

    async def _get_application_logs(self, request: LogsRequest) -> List[str]:
        """Получение логов приложения из различных источников"""
        logs_data = []

        try:
            file_logs = await self._get_file_logs()
            if file_logs:
                logs_data.extend(file_logs)
        except Exception as e:
            logger.debug(f"File logs not available: {e}")

        if not logs_data:
            try:
                docker_logs = await self._get_docker_logs(request)
                if docker_logs:
                    logs_data.extend(docker_logs)
            except Exception as e:
                logger.debug(f"Docker logs not available: {e}")

        if not logs_data:
            memory_logs = self._get_memory_logs()
            if memory_logs:
                logs_data.extend(memory_logs)

        if not logs_data:
            logs_data = self._generate_demo_logs()

        return logs_data

    def _get_memory_logs(self) -> List[str]:
        """Получение логов из памяти Python logging"""
        try:
            import logging

            log_lines = []

            root_logger = logging.getLogger()

            for handler in root_logger.handlers:
                if hasattr(handler, "stream") and hasattr(handler.stream, "getvalue"):
                    content = handler.stream.getvalue()
                    if content:
                        log_lines.extend(content.strip().split("\n"))
                elif hasattr(handler, "baseFilename"):
                    try:
                        with open(handler.baseFilename, "r", encoding="utf-8") as f:
                            log_lines.extend(f.readlines())
                    except Exception as e:
                        logger.debug(
                            f"Could not read log file {handler.baseFilename}: {e}"
                        )

            return [line.strip() for line in log_lines if line.strip()]

        except Exception as e:
            logger.debug(f"Error getting memory logs: {e}")
            return []

    def _generate_demo_logs(self) -> List[str]:
        """Генерирует демонстрационные логи для тестирования"""
        from datetime import datetime, timedelta

        demo_logs = []
        base_time = datetime.now()

        log_entries = [
            ("INFO", "app.main", "--- Application startup ---"),
            ("INFO", "app.main", "Project Name: Toy Exchange API"),
            ("INFO", "app.main", "API Version: 0.1.0"),
            ("INFO", "app.main", "Debug mode: False"),
            ("INFO", "app.main", "Checking database connection..."),
            ("INFO", "app.main", "Database connection checked successfully."),
            ("INFO", "uvicorn.error", "Application startup complete."),
            (
                "INFO",
                "uvicorn.error",
                "Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)",
            ),
            ("INFO", "app.main", "Ping received"),
            ("INFO", "app.api.routers.logs", "Logs endpoint accessed"),
            ("DEBUG", "app.services.logs_service", "Processing logs request"),
            (
                "WARNING",
                "app.services.logs_service",
                "Using demo logs - no real logs found",
            ),
            ("ERROR", "app.services.logs_service", "Example error log entry"),
            ("CRITICAL", "app.core.config", "Example critical log entry"),
        ]

        for i, (level, logger_name, message) in enumerate(log_entries):
            timestamp = base_time - timedelta(minutes=len(log_entries) - i)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            log_line = f"{timestamp_str} {level} {logger_name}: {message}"
            demo_logs.append(log_line)

        return demo_logs

    async def _get_docker_logs(self, request: LogsRequest) -> List[str]:
        """Получение логов из Docker контейнера"""
        try:
            cmd = ["docker", "logs"]

            if request.start_time:
                cmd.extend(["--since", request.start_time.isoformat()])
            if request.end_time:
                cmd.extend(["--until", request.end_time.isoformat()])

            cmd.append("--timestamps")

            container_name = await self._get_container_name()
            if not container_name:
                logger.warning("No container found, trying to read from log file")
                return await self._get_file_logs()

            cmd.append(container_name)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )
            else:
                logger.error(f"Docker logs command failed: {result.stderr}")
                return await self._get_file_logs()

        except subprocess.TimeoutExpired:
            logger.error("Docker logs command timed out")
            return []
        except Exception as e:
            logger.error(f"Error getting docker logs: {e}")
            return await self._get_file_logs()

    async def _get_container_name(self) -> Optional[str]:
        """Получение имени контейнера с приложением"""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--format",
                    "{{.Names}}",
                    "--filter",
                    "status=running",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                containers = result.stdout.strip().split("\n")
                for container in containers:
                    if "stock" in container.lower() or "api" in container.lower():
                        return container
                return containers[0] if containers else None

            return None
        except Exception as e:
            logger.error(f"Error getting container name: {e}")
            return None

    async def _get_file_logs(self) -> List[str]:
        """Получение логов из файла"""
        try:
            possible_log_paths = ["/app/logs/app.log", "app.log", "*.log"]

            log_lines = []

            for log_path in possible_log_paths[:2]:
                try:
                    if os.path.exists(log_path):
                        with open(log_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            log_lines.extend(
                                [line.strip() for line in lines if line.strip()]
                            )
                        logger.info(
                            f"Successfully read {len(lines)} lines from {log_path}"
                        )
                        break
                except Exception as e:
                    logger.debug(f"Could not read {log_path}: {e}")

            if not log_lines:
                import glob

                log_files = glob.glob("*.log")
                if log_files:
                    latest_log = max(log_files, key=os.path.getctime)
                    with open(latest_log, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        log_lines.extend(
                            [line.strip() for line in lines if line.strip()]
                        )
                    logger.info(
                        f"Successfully read {len(lines)} lines from {latest_log}"
                    )

            return log_lines

        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            return []

    def _filter_logs(
        self, logs_data: List[str], request: LogsRequest
    ) -> List[LogEntry]:
        """Фильтрация и парсинг логов"""
        filtered_logs = []

        for log_line in logs_data:
            if not log_line.strip():
                continue

            try:
                log_entry = self._parse_log_line(log_line)
                if not log_entry:
                    continue

                if request.level and log_entry.level.upper() != request.level.upper():
                    continue

                if request.start_time and log_entry.timestamp < request.start_time:
                    continue
                if request.end_time and log_entry.timestamp > request.end_time:
                    continue

                filtered_logs.append(log_entry)

            except Exception as e:
                logger.debug(f"Error parsing log line: {e}")
                continue

        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)

        return filtered_logs

    def _parse_log_line(self, log_line: str) -> Optional[LogEntry]:
        """Парсинг строки лога"""
        try:
            match = self.log_pattern.match(log_line.strip())
            if match:
                timestamp_str, level, logger_name, message = match.groups()

                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")

                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    message=message.strip(),
                    logger_name=logger_name,
                )

            if log_line.startswith("20"):
                parts = log_line.split(" ", 1)
                if len(parts) >= 2:
                    timestamp_str = parts[0]
                    message_part = parts[1]

                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )

                    level_match = re.search(
                        r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b", message_part
                    )
                    level = level_match.group(1) if level_match else "INFO"

                    logger_match = re.search(r"(\w+(?:\.\w+)*):.*", message_part)
                    logger_name = logger_match.group(1) if logger_match else None

                    return LogEntry(
                        timestamp=timestamp,
                        level=level,
                        message=message_part.strip(),
                        logger_name=logger_name,
                    )

            return LogEntry(
                timestamp=datetime.now(),
                level="INFO",
                message=log_line.strip(),
                logger_name=None,
            )

        except Exception as e:
            logger.debug(f"Error parsing log line '{log_line}': {e}")
            return None
