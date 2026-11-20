"""CLI uses offline SDK transport in tests; no credential or paid provider call."""

import pytest

from hawaii_activity_forecaster.cli import main
from hawaii_activity_forecaster.model_runtime.prompts import SATURDAY_PROFILE
from release_samples import adapter
from test_agent_release import ROOT


def args(tmp_path,request='Where should I snorkel tomorrow morning?'):
    return ['run',request,'--fixtures',str(ROOT),'--config','haf.release.example.toml','--trace-directory',str(tmp_path)]


def test_cli_requires_explicit_live_switch_before_constructing_client(tmp_path,monkeypatch,capsys):
    def forbidden(*a,**kw): pytest.fail('No client before explicit opt-in')
    monkeypatch.setattr('hawaii_activity_forecaster.agents.cli.create_adapter',forbidden)
    assert main(args(tmp_path))==2
    assert '--live' in capsys.readouterr().err


def test_cli_missing_credential_is_sanitized_and_sends_nothing(tmp_path,monkeypatch,capsys):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert main(args(tmp_path)+['--live'])==2
    assert 'MODEL_CREDENTIAL_REQUIRED' in capsys.readouterr().err
    assert not list(tmp_path.glob('*.jsonl'))


def test_cli_prints_only_validated_output_and_trace_path(tmp_path,monkeypatch,capsys):
    calls=[]
    monkeypatch.setattr('hawaii_activity_forecaster.agents.cli.create_adapter',lambda settings:adapter(calls,profile=SATURDAY_PROFILE))
    assert main(args(tmp_path)+['--live','--max-investigations','1'])==0
    out=capsys.readouterr().out
    assert 'SYNTHETIC' in out and 'Local trace:' in out and 'Fictional Test Beach' in out
    assert len(calls)==5


def test_interactive_cli_runs_a_correlated_followup_then_quits(tmp_path,monkeypatch,capsys):
    calls=[]; answers=iter(['Actually near Napili instead.','/quit'])
    monkeypatch.setattr('hawaii_activity_forecaster.agents.cli.create_adapter',lambda settings:adapter(calls,profile=SATURDAY_PROFILE))
    monkeypatch.setattr('builtins.input',lambda _:next(answers))
    assert main(args(tmp_path)+['--live','--interactive'])==0
    assert len(list(tmp_path.glob('*.jsonl')))==2 and len(calls)==10


def test_cli_clarification_does_not_dispatch_specialists(tmp_path,monkeypatch,capsys):
    calls=[]
    monkeypatch.setattr('hawaii_activity_forecaster.agents.cli.create_adapter',lambda settings:adapter(calls,profile=SATURDAY_PROFILE))
    assert main(args(tmp_path,'Where tomorrow morning?')+['--live'])==2
    assert 'Clarification needed' in capsys.readouterr().out and len(calls)==1
