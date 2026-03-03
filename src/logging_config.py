"""
Structured logging configuration for audiobook generator.
"""

import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import asdict, is_dataclass


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        # Add exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Add color to levelname
        record.levelname = f"{color}{record.levelname}{reset}"
        
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    use_json: bool = False,
    use_colors: bool = True
) -> logging.Logger:
    """
    Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file name (if None, no file logging)
        log_dir: Log directory (default: ~/.novel-audiobook-generator/logs)
        max_bytes: Max bytes per log file before rotation
        backup_count: Number of backup files to keep
        use_json: Use JSON formatting for file logs
        use_colors: Use colored output for console
        
    Returns:
        Root logger instance
    """
    # Get log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger('audiobook_generator')
    logger.setLevel(log_level)
    logger.handlers = []  # Clear existing handlers
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if use_colors and sys.stdout.isatty():
        console_format = '%(levelname)s - %(name)s - %(message)s'
        console_handler.setFormatter(ColoredFormatter(console_format))
    else:
        console_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        console_handler.setFormatter(logging.Formatter(console_format))
    
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        if log_dir is None:
            log_dir = Path.home() / '.novel-audiobook-generator' / 'logs'
        else:
            log_dir = Path(log_dir)
        
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / log_file
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        
        if use_json:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_format = '%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s'
            file_handler.setFormatter(logging.Formatter(file_format))
        
        logger.addHandler(file_handler)
        
        logger.info(f"Logging to file: {log_path}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(f'audiobook_generator.{name}')


class LogContext:
    """Context manager for adding extra data to logs."""
    
    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.extra_data = kwargs
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)
    
    def _log(self, level: int, msg: str, **kwargs):
        extra = {**self.extra_data, **kwargs}
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            '(unknown file)',
            0,
            msg,
            (),
            None
        )
        record.extra_data = extra
        self.logger.handle(record)


class PerformanceLogger:
    """Logger for performance metrics."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.metrics: Dict[str, Any] = {}
    
    def record(self, name: str, value: Any):
        """Record a metric."""
        self.metrics[name] = value
        self.logger.debug(f"Metric: {name}={value}")
    
    def timer(self, name: str):
        """Context manager for timing operations."""
        return _TimerContext(self, name)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all recorded metrics."""
        return self.metrics.copy()
    
    def clear(self):
        """Clear all metrics."""
        self.metrics.clear()


class _TimerContext:
    """Timer context manager."""
    
    def __init__(self, perf_logger: PerformanceLogger, name: str):
        self.perf_logger = perf_logger
        self.name = name
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.perf_logger.record(f"{self.name}_time_sec", elapsed)
