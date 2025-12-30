"""Local filesystem artifact storage implementation."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from runtm_shared.errors import ArtifactNotFoundError, StorageReadError, StorageWriteError
from runtm_shared.storage.base import ArtifactStore


class LocalFileStore(ArtifactStore):
    """Local filesystem implementation of ArtifactStore.

    Stores artifacts on a local filesystem path, typically a Docker volume
    shared between API and Worker containers in development.

    Usage:
        store = LocalFileStore("/artifacts")
        store.put("artifacts/dep_abc123/artifact.zip", data)
        data = store.get("artifacts/dep_abc123/artifact.zip")
    """

    def __init__(self, base_path: str):
        """Initialize local file store.

        Args:
            base_path: Base directory for artifact storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        """Resolve storage key to filesystem path.

        Args:
            key: Storage key

        Returns:
            Absolute filesystem path
        """
        # Prevent directory traversal attacks
        resolved = (self.base_path / key).resolve()
        if not str(resolved).startswith(str(self.base_path.resolve())):
            raise StorageWriteError(key, "Invalid key: path traversal detected")
        return resolved

    def put(self, key: str, data: bytes) -> str:
        """Store artifact data.

        Args:
            key: Storage key (path-like string)
            data: Raw bytes to store

        Returns:
            URI of the stored artifact (file:// path)

        Raises:
            StorageWriteError: If write fails
        """
        path = self._resolve_path(key)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return self.get_uri(key)
        except OSError as e:
            raise StorageWriteError(key, str(e)) from e

    def get(self, key: str) -> bytes:
        """Retrieve artifact data.

        Args:
            key: Storage key (path-like string)

        Returns:
            Raw bytes of the artifact

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
            StorageReadError: If read fails
        """
        path = self._resolve_path(key)

        if not path.exists():
            raise ArtifactNotFoundError(key)

        try:
            return path.read_bytes()
        except OSError as e:
            raise StorageReadError(key, str(e)) from e

    def delete(self, key: str) -> None:
        """Delete artifact.

        Args:
            key: Storage key (path-like string)

        Raises:
            StorageWriteError: If delete fails
        """
        path = self._resolve_path(key)

        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        except OSError as e:
            raise StorageWriteError(key, str(e)) from e

    def exists(self, key: str) -> bool:
        """Check if artifact exists.

        Args:
            key: Storage key (path-like string)

        Returns:
            True if artifact exists, False otherwise
        """
        path = self._resolve_path(key)
        return path.exists()

    def get_uri(self, key: str) -> str:
        """Get the URI for an artifact.

        Args:
            key: Storage key (path-like string)

        Returns:
            file:// URI for the artifact
        """
        path = self._resolve_path(key)
        return f"file://{path}"

    def get_path(self, key: str) -> Path:
        """Get the filesystem path for an artifact.

        Args:
            key: Storage key (path-like string)

        Returns:
            Filesystem path
        """
        return self._resolve_path(key)

    def get_size(self, key: str) -> Optional[int]:
        """Get the size of an artifact in bytes.

        Args:
            key: Storage key (path-like string)

        Returns:
            Size in bytes, or None if doesn't exist
        """
        path = self._resolve_path(key)
        if path.exists():
            return path.stat().st_size
        return None

    def put_file(self, key: str, file_path: str) -> str:
        """Store artifact from file path (optimized copy).

        Args:
            key: Storage key (path-like string)
            file_path: Path to file to store

        Returns:
            URI of the stored artifact
        """
        dest_path = self._resolve_path(key)

        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest_path)
            return self.get_uri(key)
        except OSError as e:
            raise StorageWriteError(key, str(e)) from e

    def get_to_file(self, key: str, file_path: str) -> None:
        """Retrieve artifact to file path (optimized copy).

        Args:
            key: Storage key (path-like string)
            file_path: Path to write artifact to
        """
        src_path = self._resolve_path(key)

        if not src_path.exists():
            raise ArtifactNotFoundError(key)

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, file_path)
        except OSError as e:
            raise StorageReadError(key, str(e)) from e

