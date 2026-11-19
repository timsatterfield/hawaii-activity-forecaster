"""Exclusive, append-only local event files with a durable boundary per event."""

from pathlib import Path
import json
import os
import re
from threading import RLock

from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.models import TraceEvent
from .privacy import sanitize_event

TERMINAL = {
    "INVESTIGATION_COMPLETED": "COMPLETED",
    "INVESTIGATION_ABSTAINED": "ABSTAINED",
    "INVESTIGATION_FAILED": "FAILED",
}


class TraceWriteError(RuntimeError):
    """The mandatory local sink is unusable; the message contains no path/payload."""


class JsonlTraceWriter:
    """One investigation, one exclusive file, one serialized producer boundary.

    Never resumes, repairs, truncates or overwrites an existing investigation.
    A partial write remains on disk for diagnosis. Each successful append fsyncs
    before returning, so later work/publication cannot outrun mandatory recording.
    """

    def __init__(self, settings: TraceSettings, *, trace_id: str, investigation_id: str,
                 session_id: str, request_revision: int):
        self._lock = RLock()
        self._fd = None
        self._failed = False
        self._last = 0
        self._bytes = 0
        self._ids = set()
        self._identity = trace_id, investigation_id, session_id, request_revision
        try:
            settings = TraceSettings.model_validate(settings.model_dump())
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", investigation_id):
                raise ValueError("Unsafe investigation file name")
            directory = settings.directory.resolve()
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.path = directory / (investigation_id + ".jsonl")
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_WRONLY, 0o600)
            os.fsync(self._fd)
        except (OSError, ValueError, TypeError, AttributeError):
            self._fail()
            raise TraceWriteError("Cannot initialize the required local investigation trace.") from None

    def _fail(self):
        self._failed = True
        if self._fd is not None:
            fd, self._fd = self._fd, None
            try:
                os.close(fd)
            except OSError:
                pass

    def append(self, event: TraceEvent) -> None:
        with self._lock:
            if self._fd is None or self._failed:
                raise TraceWriteError("The local investigation trace is closed.")
            try:
                event = sanitize_event(event)
                descriptor = os.fstat(self._fd)
                destination = self.path.stat(follow_symlinks=False)
                if (descriptor.st_dev, descriptor.st_ino, descriptor.st_size) != (
                        destination.st_dev, destination.st_ino, self._bytes) or descriptor.st_nlink == 0 or destination.st_size != self._bytes:
                    raise OSError("Trace destination was replaced or changed")
                identity = (event.trace_id, event.details.get("investigation_id"),
                            event.details.get("session_id"), event.request_revision)
                if (identity != self._identity or event.event_id in self._ids
                        or event.sequence_number != self._last + 1
                        or (self._last == 0 and event.event_type != "INVESTIGATION_STARTED")
                        or (self._last > 0 and event.event_type == "INVESTIGATION_STARTED")):
                    raise ValueError("Invalid trace event identity or order")
                payload = (json.dumps(event.model_dump(mode="json"), ensure_ascii=True,
                                      allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
                pending = memoryview(payload)
                while pending:
                    written = os.write(self._fd, pending)
                    if written <= 0:
                        raise OSError("Incomplete trace write")
                    pending = pending[written:]
                os.fsync(self._fd)
                self._bytes += len(payload)
                self._last = event.sequence_number
                self._ids.add(event.event_id)
                if event.event_type in TERMINAL:
                    self.close()
            except (OSError, ValueError, TypeError, AttributeError):
                self._fail()
                raise TraceWriteError("Cannot append a mandatory local investigation event.") from None

    def close(self) -> None:
        with self._lock:
            if self._fd is not None:
                fd, self._fd = self._fd, None
                try:
                    os.fsync(fd)
                    os.close(fd)
                except OSError:
                    self._failed = True
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    raise TraceWriteError("Cannot close the required local investigation trace.") from None
