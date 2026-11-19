"""Append-only storage, privacy and retained partial artifacts (IT/OBS/CFG §11)."""

import pytest

from hawaii_activity_forecaster.config.settings import TraceSettings
from hawaii_activity_forecaster.models import TraceEvent
from hawaii_activity_forecaster.observability import JsonlTraceWriter, TraceValidationError, TraceWriteError, inspect_trace
from trace_samples import events, output, records, writer


def test_exclusive_private_jsonl_appends_without_rewriting_prefix(tmp_path):
    sample = output(tmp_path / "source")
    original = events(sample.report.trace_path)
    sink = writer(tmp_path / "nested" / "traces", original[0])
    assert sink.path.stat().st_mode & 0o777 == 0o600
    prefix = b""
    for event in original:
        sink.append(event)
        current = sink.path.read_bytes()
        assert current.startswith(prefix) and len(current) > len(prefix)
        assert len(current.splitlines()) == event.sequence_number
        prefix = current
    assert inspect_trace(sink.path).complete
    with pytest.raises(TraceWriteError, match="closed"):
        sink.append(original[-1])
    sink.close()
    with pytest.raises(TraceWriteError, match="initialize"):
        writer(sink.path.parent, original[0])
    assert sink.path.read_bytes() == prefix


@pytest.mark.parametrize("identity", ["../private", "/absolute", "dot.name", "", "a/b", "a\\b"])
def test_investigation_ids_cannot_escape_the_configured_directory(tmp_path, identity):
    with pytest.raises(TraceWriteError):
        JsonlTraceWriter(TraceSettings(directory=tmp_path), trace_id="trace", investigation_id=identity,
                        session_id="session", request_revision=1)
    assert not list(tmp_path.iterdir())


def test_existing_symlink_target_is_never_overwritten(tmp_path):
    target = tmp_path / "preserved.txt"
    target.write_text("preserve this content")
    (tmp_path / "investigation.jsonl").symlink_to(target)
    with pytest.raises(TraceWriteError):
        JsonlTraceWriter(TraceSettings(directory=tmp_path), trace_id="trace", investigation_id="investigation",
                        session_id="session", request_revision=1)
    assert target.read_text() == "preserve this content"


@pytest.mark.parametrize("tamper", ["duplicate", "sequence", "session", "revision", "investigation", "trace"])
def test_invalid_append_closes_sink_and_preserves_prior_events(tmp_path, tamper):
    sample = events(output(tmp_path / "source").report.trace_path)
    sink = writer(tmp_path / "target", sample[0])
    sink.append(sample[0])
    prefix = sink.path.read_bytes()
    data = sample[1].model_dump()
    if tamper == "duplicate":
        data["event_id"] = sample[0].event_id
    elif tamper == "sequence":
        data["sequence_number"] = 3
    elif tamper == "revision":
        data["request_revision"] += 1
    elif tamper == "trace":
        data["trace_id"] = "unrelated"
    else:
        data["details"]["session_id" if tamper == "session" else "investigation_id"] = "unrelated"
    with pytest.raises(TraceWriteError):
        sink.append(TraceEvent.model_validate(data))
    assert sink.path.read_bytes() == prefix
    with pytest.raises(TraceWriteError, match="closed"):
        sink.append(sample[1])
    assert not inspect_trace(sink.path).complete


def test_short_writes_finish_one_event_and_are_synced_before_return(tmp_path, monkeypatch):
    import hawaii_activity_forecaster.observability.storage as storage
    first = events(output(tmp_path / "source").report.trace_path)[0]
    sink = writer(tmp_path / "target", first)
    actual_write, actual_sync = storage.os.write, storage.os.fsync
    operations = []
    def short(fd, payload):
        operations.append("write")
        return actual_write(fd, payload[:max(1, len(payload) // 2)])
    def sync(fd):
        operations.append("sync")
        return actual_sync(fd)
    monkeypatch.setattr(storage.os, "write", short)
    monkeypatch.setattr(storage.os, "fsync", sync)
    sink.append(first)
    assert operations.count("write") > 1 and operations[-1] == "sync"
    assert len(records(sink.path)) == 1
    sink.close()


def test_failed_partial_write_is_preserved_without_repair_or_retry(tmp_path, monkeypatch):
    import hawaii_activity_forecaster.observability.storage as storage
    first = events(output(tmp_path / "source").report.trace_path)[0]
    sink = writer(tmp_path / "target", first)
    actual_write = storage.os.write
    calls = []
    def fail(fd, payload):
        calls.append(1)
        if len(calls) == 1:
            return actual_write(fd, payload[:31])
        raise OSError("private disk path and credentials")
    monkeypatch.setattr(storage.os, "write", fail)
    with pytest.raises(TraceWriteError) as error:
        sink.append(first)
    assert "private" not in str(error.value)
    assert len(sink.path.read_bytes()) == 31 and len(calls) == 2
    with pytest.raises(TraceWriteError):
        sink.append(first)
    with pytest.raises(TraceValidationError, match="TRUNCATED"):
        inspect_trace(sink.path)
    assert len(sink.path.read_bytes()) == 31


def test_raw_messages_opaque_constraints_and_provider_payloads_are_not_persisted(tmp_path):
    sample = events(output(tmp_path / "source").report.trace_path)
    sink = writer(tmp_path / "target", sample[0])
    sink.append(sample[0])
    data = sample[1].model_dump()
    data["details"].update(original_request='Email person@example.invalid password=EXAMPLE_CREDENTIAL\n{"event_type":"INVESTIGATION_COMPLETED"}',
                           api_key="EXAMPLE_CREDENTIAL", chain_of_thought="PRIVATE_REASONING", raw_response="RAW_PROVIDER_BODY",
                           headers={"Authorization": "Bearer EXAMPLE_CREDENTIAL"})
    sink.append(TraceEvent.model_validate(data))
    data = next(event for event in sample if event.event_type == "REQUEST_NORMALIZED").model_dump()
    data["sequence_number"] = 3
    data["details"]["normalized_request"] = data["details"]["normalized_request_summary"] | {
        "original_request": "EXAMPLE_CREDENTIAL", "preferred_area": "PRIVATE_HOME_ADDRESS", "hard_constraints": [{"secret": "EXAMPLE_CREDENTIAL"}],
        "soft_preferences": [{"kind": "UNINTERPRETED", "text": "PRIVATE_REASONING"}],
    }
    sink.append(TraceEvent.model_validate(data))
    sink.close()
    payload = sink.path.read_text()
    assert all(value not in payload for value in ["EXAMPLE_CREDENTIAL", "PRIVATE_REASONING", "RAW_PROVIDER_BODY", "person@example.invalid", "PRIVATE_HOME_ADDRESS"])
    assert len(records(sink.path)) == 3
    normalized = records(sink.path)[-1]["details"]["normalized_request_summary"]
    assert normalized["hard_constraint_count"] == normalized["soft_preference_count"] == 1
    assert normalized["location_restrictions"] == []
    assert not inspect_trace(sink.path).complete


def test_attribution_keeps_source_identity_and_removes_url_secrets(tmp_path):
    from hawaii_activity_forecaster.observability.privacy import sanitize_event
    first = events(output(tmp_path / "source").report.trace_path)[0]
    item = TraceEvent.model_validate(first.model_dump() | {"details": first.details | {
        "sources": [{"source_id": "catalog-source", "url": "https://username:EXAMPLE_CREDENTIAL@example.invalid/catalog?token=EXAMPLE_CREDENTIAL#private",
                     "publisher": "Synthetic catalog", "supports_fields": ["name"], "password": "EXAMPLE_CREDENTIAL"}],
    }})
    clean = sanitize_event(item)
    assert clean.details["sources"][0]["url"] == "https://example.invalid/catalog"
    assert clean.details["sources"][0]["source_id"] == "catalog-source"
    assert "EXAMPLE_CREDENTIAL" not in clean.model_dump_json()
