"""M1.1-C configuration checks against CFG §§6–8/10–12.

This suite validates settings. Dispatch guards, timed execution, logging failures,
and session resets require runtime components and are not claimed as passing here.
"""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from hawaii_activity_forecaster.config import (
    AppConfig, ConfigurationError, EnvironmentalSettings, ExecutionTimeouts,
    InvestigationLimits, LangSmithSettings, LLMSettings, TraceSettings, load_config,
)

# Independent expected baseline from m1-configuration-baseline.md §§6–8.
APPROVED_LIMITS = {
    "max_coordinator_iterations": 5,
    "max_environmental_tool_invocations": 12,
    "max_retries_per_failed_invocation": 1,
    "max_fallback_attempts_per_evidence_gap": 1,
    "max_concurrent_specialists": 2,
    "max_recommendations": 3,
    "max_llm_invocations": 12,
}
APPROVED_TIMEOUTS = {"llm_request_seconds": 30, "synthetic_tool_seconds": 10}


def test_approved_defaults_cfg_t01():
    config = AppConfig()
    assert config.limits.model_dump() == APPROVED_LIMITS
    assert config.timeouts.model_dump() == APPROVED_TIMEOUTS
    assert config.environment.mode == "synthetic"
    assert config.llm.enabled is False
    assert config.llm.provider is None
    assert config.llm.model_identifier is None
    assert config.trace.format == "jsonl"
    assert config.trace.directory == Path("traces")
    assert config.trace.write_failure_policy == "fail_closed"
    assert config.langsmith.enabled is False


BUDGET_MODELS = [
    (InvestigationLimits, field, value) for field, value in APPROVED_LIMITS.items()
] + [
    (ExecutionTimeouts, field, value) for field, value in APPROVED_TIMEOUTS.items()
]


@pytest.mark.parametrize("model,field,approved", BUDGET_MODELS)
@pytest.mark.parametrize("invalid", [0, -1, True, False, "12", 12.0, None])
def test_budget_and_timeout_values_reject_invalid_types_or_values_cfg_t16(model, field, approved, invalid):
    with pytest.raises(ValidationError):
        model.model_validate({field: invalid})


@pytest.mark.parametrize("model,field,approved", BUDGET_MODELS)
@pytest.mark.parametrize("difference", [-1, 1])
def test_changes_to_approved_values_require_revised_baseline(model, field, approved, difference):
    with pytest.raises(ValidationError):
        model.model_validate({field: approved + difference})


@pytest.mark.parametrize("invalid", [float("inf"), float("nan"), "30", 0.5, 30.0])
def test_timeout_seconds_are_finite_approved_integers(invalid):
    with pytest.raises(ValidationError):
        ExecutionTimeouts(llm_request_seconds=invalid)


@pytest.mark.parametrize("model", [AppConfig, InvestigationLimits, ExecutionTimeouts,
                                  EnvironmentalSettings, LLMSettings, TraceSettings, LangSmithSettings])
def test_unknown_settings_are_rejected_cfg_t16(model):
    with pytest.raises(ValidationError):
        model.model_validate({"invented_setting": True})


@pytest.mark.parametrize("updates", [
    {"limits": None}, {"timeouts": []}, {"environment": {"mode": "live"}},
    {"trace": {"format": "remote"}}, {"trace": {"write_failure_policy": "continue"}},
    {"llm": {"enabled": "false"}}, {"langsmith": {"enabled": "false"}},
    {"limits": {"max_llm_invocations": True}}, {"live_retrieval_enabled": True},
    {"mutation_tools_enabled": True}, {"whole_investigation_timeout_seconds": 60},
    {"llm": {"automatic_retries": 1}}, {"llm": {"token_budget": 1000}},
])
def test_application_rejects_malformed_or_unapproved_configuration(updates):
    with pytest.raises(ValidationError):
        AppConfig.model_validate(updates)


@pytest.mark.parametrize("provider,model", [(None, None), ("synthetic-provider", None),
                                          (None, "synthetic-model")])
def test_missing_model_configuration_blocks_activation_cfg_t14(provider, model):
    with pytest.raises(ValidationError, match="requires explicit provider and model_identifier"):
        LLMSettings(enabled=True, provider=provider, model_identifier=model)


def test_provider_metadata_does_not_authorize_real_model_execution():
    with pytest.raises(ValidationError, match="pending provider activation review"):
        LLMSettings(enabled=True, provider="synthetic-provider", model_identifier="synthetic-model")
    settings = LLMSettings(provider="synthetic-provider", model_identifier="synthetic-model")
    assert settings.enabled is False


@pytest.mark.parametrize("field,value", [("provider", ""), ("model_identifier", "  "),
                                        ("provider", True), ("model_identifier", 12)])
def test_model_identifiers_cannot_be_blank_or_coerced(field, value):
    with pytest.raises(ValidationError):
        LLMSettings.model_validate({field: value})


@pytest.mark.parametrize("directory", ["", "  ", "\x00", "https://example.invalid/traces", "s3://bucket", 12, None])
def test_trace_directory_must_be_local_path(directory):
    with pytest.raises(ValidationError):
        TraceSettings(directory=directory)


def test_models_are_json_serializable_and_frozen():
    config = AppConfig()
    assert AppConfig.model_validate_json(config.model_dump_json()) == config
    with pytest.raises(ValidationError, match="frozen"):
        config.limits.max_environmental_tool_invocations = 13
    with pytest.raises(ValidationError, match="frozen"):
        config.llm.enabled = True


def test_loading_defaults_has_no_filesystem_or_environment_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    before = dict(os.environ)
    config = load_config()
    assert config.llm.provider is None
    assert config.llm.model_identifier is None
    assert config.langsmith.enabled is False
    assert config.trace.directory == tmp_path / "traces"
    assert list(tmp_path.iterdir()) == []
    assert dict(os.environ) == before


def test_unrelated_sdk_environment_is_ignored():
    config = load_config(environ={
        "LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true",
        "OPENAI_MODEL": "synthetic-model", "ANTHROPIC_API_KEY": "synthetic-secret",
    })
    assert config.llm == LLMSettings()
    assert config.langsmith.enabled is False


def test_example_toml_matches_baseline():
    example = Path(__file__).resolve().parents[1] / "haf.example.toml"
    config = load_config(example, environ={})
    assert config.limits.model_dump() == APPROVED_LIMITS
    assert config.timeouts.model_dump() == APPROVED_TIMEOUTS
    assert config.trace.directory == example.parent / "traces"
    assert config.llm == LLMSettings()
    assert config.langsmith.enabled is False


def test_loader_does_not_implicitly_discover_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "haf.example.toml").write_text("invalid toml [")
    assert load_config(environ={}).limits.model_dump() == APPROVED_LIMITS


def test_toml_and_environment_precedence_and_relative_paths(tmp_path, monkeypatch):
    config_dir = tmp_path / "configuration"
    config_dir.mkdir()
    path = config_dir / "local.toml"
    path.write_text('''[llm]
provider = "file-provider"
model_identifier = "file-model"
[trace]
directory = "file-traces"
[langsmith]
enabled = true
''')
    work_dir = tmp_path / "other-directory"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    config = load_config(path, environ={
        "HAF_LLM_PROVIDER": "env-provider", "HAF_LLM_MODEL_IDENTIFIER": "env-model",
        "HAF_TRACE_DIRECTORY": "env-traces", "HAF_LANGSMITH_ENABLED": "false",
    })
    assert config.llm.provider == "env-provider"
    assert config.llm.model_identifier == "env-model"
    assert config.llm.enabled is False
    assert config.trace.directory == config_dir / "env-traces"
    assert config.langsmith.enabled is False
    assert not config.trace.directory.exists()
    assert load_config(path, environ={}).trace.directory == config_dir / "file-traces"


def test_absolute_trace_directory_is_preserved(tmp_path):
    directory = tmp_path / "absolute-traces"
    config = load_config(environ={"HAF_TRACE_DIRECTORY": str(directory)})
    assert config.trace.directory == directory
    assert not directory.exists()


@pytest.mark.parametrize("value,expected", [("true", True), ("TRUE", True), ("false", False), ("False", False)])
def test_explicit_langsmith_opt_in_is_only_a_setting(value, expected, monkeypatch):
    before = dict(os.environ)
    config = load_config(environ={"HAF_LANGSMITH_ENABLED": value})
    assert config.langsmith.enabled is expected
    assert dict(os.environ) == before


@pytest.mark.parametrize("value", ["1", "0", "yes", "", " true", "true "])
def test_environment_boolean_parsing_rejects_ambiguous_values(value):
    with pytest.raises(ConfigurationError, match="require true or false"):
        load_config(environ={"HAF_LANGSMITH_ENABLED": value})


def test_llm_activation_rejected_when_loaded_from_environment():
    with pytest.raises(ConfigurationError, match="requires explicit provider"):
        load_config(environ={"HAF_LLM_ENABLED": "true"})
    with pytest.raises(ConfigurationError, match="pending provider activation review"):
        load_config(environ={"HAF_LLM_ENABLED": "true", "HAF_LLM_PROVIDER": "synthetic-provider",
                             "HAF_LLM_MODEL_IDENTIFIER": "synthetic-model"})


def test_environment_cannot_enable_live_retrieval():
    with pytest.raises(ConfigurationError, match="environment.mode"):
        load_config(environ={"HAF_ENVIRONMENT_MODE": "live"})


@pytest.mark.parametrize("environment", [{"HAF_LLM_MODLE": "typo"}, {"HAF_LANGSMITH_ENABLED": True}])
def test_invalid_environment_configuration_is_rejected(environment):
    with pytest.raises(ConfigurationError):
        load_config(environ=environment)


@pytest.mark.parametrize("contents", ["[llm", "duplicate = 1\nduplicate = 2", "\xff"])
def test_invalid_toml_is_reported_as_configuration_error(contents, tmp_path):
    path = tmp_path / "invalid.toml"
    path.write_bytes(contents.encode("latin-1"))
    with pytest.raises(ConfigurationError, match="Invalid TOML configuration"):
        load_config(path, environ={})


def test_missing_explicit_configuration_is_not_silently_ignored(tmp_path):
    with pytest.raises(ConfigurationError, match="Cannot read"):
        load_config(tmp_path / "missing.toml", environ={})


def test_malformed_table_cannot_be_overridden_as_a_valid_section(tmp_path):
    path = tmp_path / "invalid.toml"
    path.write_text('llm = "not a table"')
    with pytest.raises(ConfigurationError, match="sections must be TOML tables"):
        load_config(path, environ={"HAF_LLM_ENABLED": "false"})


def test_toml_budget_expansion_is_rejected_cfg_t16(tmp_path):
    path = tmp_path / "invalid.toml"
    path.write_text("[limits]\nmax_environmental_tool_invocations = 13")
    with pytest.raises(ConfigurationError, match="limits.max_environmental_tool_invocations"):
        load_config(path, environ={})


def test_invalid_configuration_error_does_not_echo_secret_values(tmp_path):
    path = tmp_path / "invalid.toml"
    path.write_text('[llm]\napi_key = "synthetic-secret-do-not-echo"')
    with pytest.raises(ConfigurationError) as error:
        load_config(path, environ={})
    assert "synthetic-secret-do-not-echo" not in str(error.value)
    assert "Extra inputs" in str(error.value)


def test_revalidates_unsafe_nested_model_copies():
    invalid_limits = InvestigationLimits().model_copy(update={"max_coordinator_iterations": 6})
    with pytest.raises(ValidationError):
        AppConfig(limits=invalid_limits)
