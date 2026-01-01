"""
Research v2 - Structured Logging Infrastructure

All logs are:
- Structured (JSON)
- Timestamped
- Module-scoped
- Human-readable

Every module logs:
- Initialization
- Inputs received
- Outputs produced
- Explicit error states
- Suggested fix hints where possible
"""

import json
import logging
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ResearchLogger:
    """
    Structured JSON logger for research pipeline.
    
    All log entries include:
    - timestamp: ISO 8601 format
    - module: Source module name
    - level: Severity level
    - message: Human-readable message
    - Additional context fields as needed
    """
    
    def __init__(
        self,
        module_name: str,
        log_dir: Optional[Path] = None,
        console_output: bool = True,
        file_output: bool = True,
    ):
        """
        Initialize logger for a specific module.
        
        Args:
            module_name: Name of the module (e.g., "VehicleSpawner")
            log_dir: Directory for log files
            console_output: Whether to print to console
            file_output: Whether to write to file
        """
        self.module_name = module_name
        self.log_dir = log_dir
        self.console_output = console_output
        self.file_output = file_output
        self._log_file = None
        self._entries = []
        
        if log_dir and file_output:
            self.log_dir = Path(log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._log_file = self.log_dir / f"{module_name.lower()}_{timestamp}.jsonl"
    
    def _format_entry(
        self,
        level: LogLevel,
        message: str,
        **kwargs: Any
    ) -> dict:
        """Create structured log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "module": self.module_name,
            "level": level.value,
            "message": message,
        }
        
        # Add any additional context
        for key, value in kwargs.items():
            # Convert non-serializable types
            if hasattr(value, "__dict__"):
                value = str(value)
            elif isinstance(value, Path):
                value = str(value)
            entry[key] = value
        
        return entry
    
    def _output(self, entry: dict) -> None:
        """Output log entry to configured destinations."""
        json_str = json.dumps(entry, default=str)
        
        if self.console_output:
            # Color-coded console output
            level = entry["level"]
            colors = {
                "DEBUG": "\033[36m",     # Cyan
                "INFO": "\033[32m",      # Green
                "WARNING": "\033[33m",   # Yellow
                "ERROR": "\033[31m",     # Red
                "CRITICAL": "\033[35m",  # Magenta
            }
            reset = "\033[0m"
            color = colors.get(level, "")
            print(f"{color}[{entry['module']}] {entry['message']}{reset}")
            
            # Print additional fields on separate lines
            for key in entry:
                if key not in ["timestamp", "module", "level", "message"]:
                    print(f"  {key}: {entry[key]}")
        
        if self._log_file and self.file_output:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json_str + "\n")
        
        self._entries.append(entry)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        entry = self._format_entry(LogLevel.DEBUG, message, **kwargs)
        self._output(entry)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        entry = self._format_entry(LogLevel.INFO, message, **kwargs)
        self._output(entry)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        entry = self._format_entry(LogLevel.WARNING, message, **kwargs)
        self._output(entry)
    
    def error(
        self,
        message: str,
        reason: Optional[str] = None,
        suggested_fix: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Log error message with required context.
        
        Args:
            message: Error description
            reason: Why the error occurred
            suggested_fix: How to potentially fix it
        """
        if reason:
            kwargs["reason"] = reason
        if suggested_fix:
            kwargs["suggested_fix"] = suggested_fix
        entry = self._format_entry(LogLevel.ERROR, message, **kwargs)
        self._output(entry)
    
    def critical(
        self,
        message: str,
        reason: Optional[str] = None,
        suggested_fix: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Log critical error - pipeline should abort."""
        if reason:
            kwargs["reason"] = reason
        if suggested_fix:
            kwargs["suggested_fix"] = suggested_fix
        entry = self._format_entry(LogLevel.CRITICAL, message, **kwargs)
        self._output(entry)
    
    def log_init(self, **params: Any) -> None:
        """Log module initialization with parameters."""
        self.info(f"{self.module_name} initialized", **params)
    
    def log_input(self, description: str, **data: Any) -> None:
        """Log input received by module."""
        self.debug(f"Input: {description}", **data)
    
    def log_output(self, description: str, **data: Any) -> None:
        """Log output produced by module."""
        self.debug(f"Output: {description}", **data)
    
    def get_entries(self, level: Optional[LogLevel] = None) -> list[dict]:
        """Get all log entries, optionally filtered by level."""
        if level is None:
            return self._entries.copy()
        return [e for e in self._entries if e["level"] == level.value]
    
    def get_error_count(self) -> int:
        """Count error and critical entries."""
        return sum(
            1 for e in self._entries
            if e["level"] in ["ERROR", "CRITICAL"]
        )
    
    def get_summary(self) -> dict:
        """Get summary of all log entries."""
        counts = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        for entry in self._entries:
            counts[entry["level"]] += 1
        return {
            "module": self.module_name,
            "total_entries": len(self._entries),
            "by_level": counts,
            "log_file": str(self._log_file) if self._log_file else None,
        }


class PipelineLogger:
    """
    Aggregated logger for entire pipeline.
    Collects logs from all modules.
    """
    
    def __init__(self, log_dir: Path):
        """Initialize pipeline logger."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._module_loggers: dict[str, ResearchLogger] = {}
        
        # Master log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._master_log = self.log_dir / f"pipeline_{timestamp}.jsonl"
    
    def get_logger(self, module_name: str) -> ResearchLogger:
        """Get or create logger for a module."""
        if module_name not in self._module_loggers:
            self._module_loggers[module_name] = ResearchLogger(
                module_name=module_name,
                log_dir=self.log_dir,
                console_output=True,
                file_output=True,
            )
        return self._module_loggers[module_name]
    
    def get_all_errors(self) -> list[dict]:
        """Get all errors from all modules."""
        errors = []
        for logger in self._module_loggers.values():
            errors.extend(logger.get_entries(LogLevel.ERROR))
            errors.extend(logger.get_entries(LogLevel.CRITICAL))
        return sorted(errors, key=lambda e: e["timestamp"])
    
    def get_pipeline_summary(self) -> dict:
        """Get summary of entire pipeline logging."""
        return {
            "log_directory": str(self.log_dir),
            "modules": {
                name: logger.get_summary()
                for name, logger in self._module_loggers.items()
            },
            "total_errors": sum(
                l.get_error_count() for l in self._module_loggers.values()
            ),
        }
    
    def write_summary(self) -> Path:
        """Write pipeline summary to file."""
        summary_path = self.log_dir / "pipeline_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(self.get_pipeline_summary(), f, indent=2, default=str)
        return summary_path
