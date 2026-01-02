"""Disk spool for telemetry persistence.

Provides bounded disk storage for telemetry data that couldn't be sent,
allowing retry on next CLI invocation.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .base import TelemetryBatch

logger = logging.getLogger(__name__)


@dataclass
class SpoolConfig:
    """Configuration for disk spool."""

    # Size limits
    max_size_bytes: int = 1024 * 1024  # 1MB
    max_file_count: int = 100
    max_age_seconds: int = 86400  # 24 hours

    # File naming
    file_prefix: str = "telemetry_"
    file_suffix: str = ".ndjson"


class DiskSpool:
    """Bounded disk spool for telemetry persistence.

    Features:
    - Writes telemetry to newline-delimited JSON files
    - Rotates oldest files when size limit exceeded
    - Provides iterator for reading spooled data
    - Cleans up successfully sent data
    """

    DEFAULT_PATH = Path.home() / ".runtm" / "telemetry_spool"

    def __init__(
        self,
        spool_path: Optional[Path] = None,
        config: Optional[SpoolConfig] = None,
    ) -> None:
        """Initialize the disk spool.

        Args:
            spool_path: Path to spool directory
            config: Spool configuration
        """
        self._spool_path = spool_path or self.DEFAULT_PATH
        self._config = config or SpoolConfig()
        self._current_file: Optional[Path] = None
        self._current_size = 0

    def ensure_directory(self) -> bool:
        """Ensure the spool directory exists.

        Returns:
            True if directory exists or was created
        """
        try:
            self._spool_path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:
            logger.debug(f"Failed to create spool directory: {e}")
            return False

    def write(self, batch: TelemetryBatch) -> bool:
        """Write a batch to disk.

        Args:
            batch: The telemetry batch to write

        Returns:
            True if written successfully
        """
        if batch.is_empty():
            return True

        if not self.ensure_directory():
            return False

        try:
            # Serialize batch
            data = json.dumps(batch.to_dict())
            data_size = len(data.encode("utf-8"))

            # Check if we need to rotate
            self._maybe_rotate(data_size)

            # Get or create current file
            file_path = self._get_current_file()

            # Append to file
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(data + "\n")

            self._current_size += data_size + 1
            return True

        except Exception as e:
            logger.debug(f"Failed to write to spool: {e}")
            return False

    def read_all(self) -> Iterator[tuple[Path, TelemetryBatch]]:
        """Read all spooled batches.

        Yields:
            Tuples of (file_path, batch) for each spooled batch
        """
        if not self._spool_path.exists():
            return

        # Clean up old files first
        self._cleanup_old_files()

        for file_path in sorted(
            self._spool_path.glob(f"{self._config.file_prefix}*{self._config.file_suffix}")
        ):
            try:
                with open(file_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            batch = TelemetryBatch.from_dict(data)
                            yield file_path, batch
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.debug(f"Invalid spool entry: {e}")
                            continue
            except OSError as e:
                logger.debug(f"Failed to read spool file {file_path}: {e}")
                continue

    def delete_file(self, file_path: Path) -> bool:
        """Delete a spool file after successful send.

        Args:
            file_path: Path to the file to delete

        Returns:
            True if deleted successfully
        """
        try:
            file_path.unlink(missing_ok=True)
            return True
        except OSError as e:
            logger.debug(f"Failed to delete spool file: {e}")
            return False

    def clear(self) -> int:
        """Clear all spooled data.

        Returns:
            Number of files deleted
        """
        if not self._spool_path.exists():
            return 0

        count = 0
        for file_path in self._spool_path.glob(
            f"{self._config.file_prefix}*{self._config.file_suffix}"
        ):
            try:
                file_path.unlink()
                count += 1
            except OSError:
                pass

        self._current_file = None
        self._current_size = 0
        return count

    def get_size(self) -> int:
        """Get total size of spooled data in bytes.

        Returns:
            Total size in bytes
        """
        if not self._spool_path.exists():
            return 0

        total = 0
        for file_path in self._spool_path.glob(
            f"{self._config.file_prefix}*{self._config.file_suffix}"
        ):
            try:
                total += file_path.stat().st_size
            except OSError:
                pass
        return total

    def get_file_count(self) -> int:
        """Get number of spool files.

        Returns:
            Number of spool files
        """
        if not self._spool_path.exists():
            return 0

        return len(
            list(self._spool_path.glob(f"{self._config.file_prefix}*{self._config.file_suffix}"))
        )

    def _get_current_file(self) -> Path:
        """Get the current spool file, creating if needed.

        Returns:
            Path to current spool file
        """
        if self._current_file is None or not self._current_file.exists():
            timestamp = int(time.time() * 1000)
            self._current_file = self._spool_path / (
                f"{self._config.file_prefix}{timestamp}{self._config.file_suffix}"
            )
            self._current_size = 0
        return self._current_file

    def _maybe_rotate(self, pending_size: int) -> None:
        """Rotate spool if size limits exceeded.

        Args:
            pending_size: Size of data about to be written
        """
        current_total = self.get_size()

        # Check if adding new data would exceed limit
        if current_total + pending_size <= self._config.max_size_bytes:
            return

        # Need to delete oldest files
        files = sorted(
            self._spool_path.glob(f"{self._config.file_prefix}*{self._config.file_suffix}"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
        )

        # Delete oldest files until we have room
        bytes_freed = 0
        for file_path in files:
            if current_total - bytes_freed + pending_size <= self._config.max_size_bytes:
                break
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                bytes_freed += file_size

                # Clear current file reference if deleted
                if file_path == self._current_file:
                    self._current_file = None
                    self._current_size = 0
            except OSError:
                pass

        # Also enforce max file count
        self._enforce_file_limit()

    def _enforce_file_limit(self) -> None:
        """Delete oldest files if count exceeds limit."""
        files = sorted(
            self._spool_path.glob(f"{self._config.file_prefix}*{self._config.file_suffix}"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
        )

        while len(files) > self._config.max_file_count:
            try:
                files[0].unlink()
                files = files[1:]
            except OSError:
                break

    def _cleanup_old_files(self) -> None:
        """Delete files older than max age."""
        if not self._spool_path.exists():
            return

        now = time.time()
        for file_path in self._spool_path.glob(
            f"{self._config.file_prefix}*{self._config.file_suffix}"
        ):
            try:
                mtime = file_path.stat().st_mtime
                if now - mtime > self._config.max_age_seconds:
                    file_path.unlink()
            except OSError:
                pass
