"""Explicit local-test storage adapter for synthetic lifecycle tests."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.engine import URL, make_url

LOCAL_TEST_ENVIRONMENT = "local-test"
LOCAL_NAMESPACE_ENVIRONMENT = "disposable-test"
LOCAL_STORAGE_ENDPOINT = "https://vervfy.invalid"
LOCAL_STORAGE_BUCKET = "synthetic"
DEFAULT_STORAGE_ROOT = Path("/tmp/vervfy-staging-storage")
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_OBJECT_PATH = re.compile(
    rf"v2/{_UUID}/[A-Za-z0-9_-]{{1,32}}/"
    rf"(?:audio|track-cover|album-cover|artist-photo|staged-audio)/"
    rf"{_UUID}\.[a-z0-9]{{1,5}}"
)
_DATABASE_ROLES = {
    "DATABASE_URL": "app_runtime",
    "MIGRATION_DATABASE_URL": "migration_owner",
    "GOOGLE_IDENTITY_LOOKUP_DATABASE_URL": "google_auth_lookup",
}


class LocalStorageConfigurationError(RuntimeError):
    """Local storage was requested without a safe disposable-test configuration."""


class LocalStorageError(RuntimeError):
    """A local object path or filesystem operation was unsafe or failed."""


class LocalObjectNotFound(LocalStorageError):
    """A managed object is absent from the local filesystem."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LocalStorageConfigurationError(message)


def _disposable_socket(url: URL, expected_role: str | None = None) -> str:
    _require(
        url.get_backend_name() == "postgresql"
        and url.database == "postgres"
        and url.host is None
        and not url.password,
        "Local storage requires a disposable PostgreSQL Unix socket",
    )
    if expected_role is not None:
        _require(url.username == expected_role, "Local database role is not approved")
    socket_path = url.query.get("host")
    _require(
        isinstance(socket_path, str) and Path(socket_path).is_absolute(),
        "Local database must use an approved Unix socket",
    )
    path = Path(socket_path)
    _require(
        path.parent == Path("/tmp")
        and path.name.startswith("vervfy-storage-pg-")
        and path.is_dir()
        and not path.is_symlink()
        and path.resolve(strict=True) == path,
        "Database destination is not a disposable local test cluster",
    )
    _require(
        set(url.query) == {"host"},
        "Local database URL contains unsupported connection options",
    )
    return socket_path


def validate_local_configuration() -> Path:
    """Validate opt-in, credentials, database destinations, and storage root."""
    _require(
        os.environ.get("VERVFY_ENVIRONMENT", "").strip().lower()
        == LOCAL_TEST_ENVIRONMENT,
        "Filesystem storage is restricted to VERVFY_ENVIRONMENT=local-test",
    )
    _require(
        os.environ.get("VERVFY_STORAGE_BACKEND", "").strip().lower()
        == "filesystem",
        "Explicit VERVFY_STORAGE_BACKEND=filesystem is required",
    )
    _require(
        not os.environ.get("SUPABASE_URL", "").strip()
        and not os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        and not os.environ.get("SUPABASE_BUCKET", "").strip(),
        "Supabase endpoints and credentials must be unset in local-test mode",
    )
    _require(
        not any(name.startswith("PG") for name in os.environ),
        "PG* overrides are not allowed in local-test mode",
    )

    urls: dict[str, URL] = {}
    for setting, role in _DATABASE_ROLES.items():
        raw = os.environ.get(setting, "").strip()
        if not raw:
            if setting == "DATABASE_URL":
                raise LocalStorageConfigurationError(
                    "DATABASE_URL must target the disposable local test cluster"
                )
            continue
        try:
            url = make_url(raw)
            _disposable_socket(url, role)
        except (TypeError, ValueError):
            raise LocalStorageConfigurationError(
                f"{setting} is not a disposable local test database"
            ) from None
        urls[setting] = url

    configured_database = urls["DATABASE_URL"]
    configured_socket = str(configured_database.query["host"])
    for url in urls.values():
        _require(
            url.database == configured_database.database
            and url.query["host"] == configured_socket,
            "All local database URLs must target the same disposable cluster",
        )

    raw_root = os.environ.get("VERVFY_LOCAL_STORAGE_ROOT", str(DEFAULT_STORAGE_ROOT))
    root = Path(raw_root)
    _require(
        root.is_absolute()
        and root.parent == Path("/tmp")
        and Path("/tmp").resolve(strict=True) == Path("/tmp")
        and root.name not in {"", ".", ".."},
        "Local storage root must be a dedicated direct child of /tmp",
    )
    _require(
        not root.name.startswith("vervfy-storage-pg-"),
        "Local storage root cannot overlap the disposable database directory",
    )
    _require(
        not root.is_symlink()
        and (not root.exists() or root.is_dir())
        and (not root.exists() or root.resolve(strict=True) == root),
        "Local storage root must not be a symlink",
    )
    return root


def validate_local_source(path: str) -> None:
    """Keep local test uploads away from repository and user-home files."""
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise LocalStorageError("Local upload source must be a regular synthetic file")
    try:
        resolved = source.resolve(strict=True)
    except OSError:
        raise LocalStorageError("Local upload source could not be resolved") from None
    temp_root = Path("/tmp").resolve(strict=True)
    if resolved == temp_root or temp_root not in resolved.parents:
        raise LocalStorageError("Local upload source must be under /tmp")


def local_storage_selected() -> bool:
    """Return whether the explicitly selected backend is the local filesystem."""
    environment = os.environ.get("VERVFY_ENVIRONMENT", "").strip().lower()
    backend = os.environ.get("VERVFY_STORAGE_BACKEND", "").strip().lower()
    if environment == LOCAL_TEST_ENVIRONMENT and backend != "filesystem":
        raise LocalStorageConfigurationError(
            "local-test mode requires VERVFY_STORAGE_BACKEND=filesystem"
        )
    if backend and backend not in {"supabase", "filesystem"}:
        raise LocalStorageConfigurationError("Unknown storage backend")
    if backend == "filesystem":
        validate_local_configuration()
        return True
    return False


def validate_database_session(bind) -> None:
    """Recheck the actual SQLAlchemy destination before local lifecycle operations."""
    root = validate_local_configuration()
    del root
    try:
        actual = make_url(str(bind.url))
        configured = make_url(os.environ["DATABASE_URL"])
        socket_path = _disposable_socket(actual)
    except (KeyError, TypeError, ValueError):
        raise LocalStorageConfigurationError(
            "Storage lifecycle session is not on the disposable local cluster"
        ) from None
    _require(
        socket_path == configured.query.get("host")
        and actual.database == configured.database
        and actual.username
        in {"app_runtime", "storage_cleanup_worker"},
        "Storage lifecycle session targets an unapproved database",
    )


class FilesystemStorageAdapter:
    """Create-only object storage rooted under one private /tmp directory."""

    def __init__(self) -> None:
        root = validate_local_configuration()
        try:
            if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
                raise LocalStorageError(
                    "Filesystem storage requires no-follow directory operations"
                )
            root.mkdir(mode=0o700, parents=False, exist_ok=True)
            metadata = root.stat(follow_symlinks=False)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077
            ):
                raise LocalStorageError(
                    "Local storage root must be a private directory owned by this user"
                )
            self.root = root
            root_fd = self._open_root()
            os.close(root_fd)
        except LocalStorageError:
            raise
        except OSError as exc:
            raise LocalStorageError(
                f"Local storage root could not be opened ({type(exc).__name__})"
            ) from None

    @classmethod
    def from_environment(cls) -> FilesystemStorageAdapter:
        if not local_storage_selected():
            raise LocalStorageConfigurationError(
                "The local filesystem backend was not explicitly selected"
            )
        return cls()

    @staticmethod
    def _flags() -> int:
        return (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )

    def _open_root(self) -> int:
        return os.open(self.root, self._flags())

    @staticmethod
    def _segments(path: str) -> list[str]:
        if (
            not isinstance(path, str)
            or not _OBJECT_PATH.fullmatch(path)
            or "\\" in path
            or "\x00" in path
        ):
            raise LocalStorageError("Invalid managed object path")
        return path.split("/")

    def _open_parent(self, path: str, *, create: bool) -> tuple[int, str]:
        segments = self._segments(path)
        try:
            current = self._open_root()
        except OSError:
            raise LocalStorageError("Local storage root could not be opened safely") from None
        try:
            for segment in segments[:-1]:
                if create:
                    try:
                        os.mkdir(segment, mode=0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                child = os.open(segment, self._flags(), dir_fd=current)
                os.close(current)
                current = child
            return current, segments[-1]
        except FileNotFoundError:
            os.close(current)
            raise LocalObjectNotFound("Local object is absent") from None
        except OSError:
            os.close(current)
            raise LocalStorageError("Unsafe local object path") from None
        except BaseException:
            os.close(current)
            raise

    @staticmethod
    def _read_chunks(source: BinaryIO):
        while chunk := source.read(64 * 1024):
            if not isinstance(chunk, bytes):
                raise LocalStorageError("Local upload source must return bytes")
            yield chunk

    def upload_file(
        self, path: str, source: BinaryIO, size: int, expected_digest: bytes
    ) -> None:
        parent, name = self._open_parent(path, create=True)
        fd = None
        try:
            fd = os.open(
                name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=parent,
            )
            digest = hashlib.sha256()
            count = 0
            for chunk in self._read_chunks(source):
                count += len(chunk)
                if count > size:
                    raise LocalStorageError("Local upload size mismatch")
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise LocalStorageError("Local upload write made no progress")
                    view = view[written:]
            if count != size or digest.digest() != expected_digest:
                raise LocalStorageError("Local upload digest mismatch")
            os.fsync(fd)
            os.fsync(parent)
        except FileExistsError:
            raise LocalStorageError("Create-only upload path already exists") from None
        except LocalStorageError:
            raise
        except FileNotFoundError:
            raise LocalObjectNotFound("Local object is absent") from None
        except OSError as exc:
            raise LocalStorageError(
                f"Local upload failed ({type(exc).__name__})"
            ) from None
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)
        self.verify(path, size, expected_digest)

    def _open_file(self, path: str) -> int:
        parent, name = self._open_parent(path, create=False)
        try:
            fd = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent,
            )
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                raise LocalStorageError("Managed object is not a regular file")
            return fd
        except LocalStorageError:
            raise
        except FileNotFoundError:
            raise LocalObjectNotFound("Local object is absent") from None
        except OSError as exc:
            raise LocalStorageError(
                f"Local object could not be opened ({type(exc).__name__})"
            ) from None
        finally:
            os.close(parent)

    def verify(self, path: str, size: int, expected_digest: bytes) -> None:
        fd = self._open_file(path)
        digest = hashlib.sha256()
        count = 0
        try:
            while chunk := os.read(fd, 64 * 1024):
                count += len(chunk)
                if count > size:
                    raise LocalStorageError("Local verification size mismatch")
                digest.update(chunk)
        finally:
            os.close(fd)
        if count != size or digest.digest() != expected_digest:
            raise LocalStorageError("Local verification digest mismatch")

    def download_to_file(self, path: str, destination: str, max_bytes: int) -> int:
        if max_bytes < 0:
            raise LocalStorageError("Invalid local download size limit")
        destination_path = Path(destination)
        if not destination_path.is_absolute():
            raise LocalStorageError("Local download destination must be absolute")
        parent = destination_path.parent
        try:
            resolved_parent = parent.resolve(strict=True)
        except OSError:
            raise LocalStorageError(
                "Local download destination directory is unavailable"
            ) from None
        if (
            (parent != Path("/tmp") and parent.parent != Path("/tmp"))
            or parent.is_symlink()
            or resolved_parent != parent
        ):
            raise LocalStorageError(
                "Local download destination must be a non-symlink /tmp path"
            )
        target = destination_path.resolve(strict=False)
        temp_root = Path("/tmp").resolve(strict=True)
        if (
            target == self.root
            or self.root in target.parents
            or target == temp_root
            or temp_root not in target.parents
        ):
            raise LocalStorageError(
                "Local download destination must be a separate /tmp file"
            )
        source_fd = self._open_file(path)
        target_fd = None
        count = 0
        try:
            target_fd = os.open(
                destination,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_TRUNC
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            while chunk := os.read(source_fd, 64 * 1024):
                count += len(chunk)
                if count > max_bytes:
                    raise LocalStorageError("Local object exceeds download size limit")
                view = memoryview(chunk)
                while view:
                    written = os.write(target_fd, view)
                    if written <= 0:
                        raise LocalStorageError("Local download write made no progress")
                    view = view[written:]
        except LocalStorageError:
            raise
        except OSError as exc:
            raise LocalStorageError(
                f"Local download failed ({type(exc).__name__})"
            ) from None
        finally:
            os.close(source_fd)
            if target_fd is not None:
                os.close(target_fd)
        return count

    def read_range(self, path: str, start: int, end: int) -> bytes:
        if start < 0 or end < start:
            raise LocalStorageError("Invalid byte range")
        fd = self._open_file(path)
        try:
            os.lseek(fd, start, os.SEEK_SET)
            return os.read(fd, end - start + 1)
        except OSError as exc:
            raise LocalStorageError(
                f"Local range read failed ({type(exc).__name__})"
            ) from None
        finally:
            os.close(fd)

    def object_size(self, path: str) -> int | None:
        try:
            fd = self._open_file(path)
        except LocalObjectNotFound:
            return None
        try:
            return os.fstat(fd).st_size
        finally:
            os.close(fd)

    def is_private(self) -> bool:
        metadata = self.root.stat(follow_symlinks=False)
        return stat.S_ISDIR(metadata.st_mode) and not metadata.st_mode & 0o077

    def delete_if_present(self, path: str) -> None:
        try:
            parent, name = self._open_parent(path, create=False)
        except LocalObjectNotFound:
            return
        try:
            try:
                metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            if not stat.S_ISREG(metadata.st_mode):
                raise LocalStorageError("Refusing to delete a non-regular object")
            os.unlink(name, dir_fd=parent)
            os.fsync(parent)
        except LocalStorageError:
            raise
        except OSError as exc:
            raise LocalStorageError(
                f"Local delete failed ({type(exc).__name__})"
            ) from None
        finally:
            os.close(parent)
