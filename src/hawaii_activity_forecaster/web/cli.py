"""``hafi web``: start the loopback-only interface with the same opt-in as ``hafi run``."""

from __future__ import annotations

import sys
from pathlib import Path

from hawaii_activity_forecaster.config.settings import TraceSettings

DEFAULT_PORT = 8765


def web_command(arguments, *, serve: bool = True):
    """Validate inputs exactly as the CLI does, then serve until interrupted."""
    from hawaii_activity_forecaster.config import ConfigurationError, load_config
    from hawaii_activity_forecaster.fixtures import FixtureLoadError
    from .server import WebApp, create_server

    model_driven = arguments.live or arguments.local
    try:
        config = load_config(arguments.config)
    except ConfigurationError:
        print("Cannot load a valid application configuration.", file=sys.stderr)
        return 2
    settings = config.trace if arguments.trace_directory is None else TraceSettings(directory=arguments.trace_directory)
    release = adapter = None
    if model_driven:
        from hawaii_activity_forecaster.agents.cli import TargetSelectionError, configured_target
        from hawaii_activity_forecaster.agents.data import load_release_data
        try:
            config, adapter = configured_target(arguments)
            release = load_release_data(arguments.release_fixtures, arguments.case)
        except TargetSelectionError as error:
            print(str(error), file=sys.stderr)
            return 2
        except ConfigurationError:
            print("Cannot load a valid release configuration.", file=sys.stderr)
            return 2
        except FixtureLoadError:
            print("Cannot load the synthetic release fixture data.", file=sys.stderr)
            return 2
    evidence = arguments.evidence if arguments.evidence is not None else Path("docs/evaluation-evidence")
    app = WebApp(demo_fixtures=arguments.fixtures, trace_settings=settings,
                 evidence_dir=evidence if evidence.is_dir() else None,
                 mode="live" if arguments.live else "local" if arguments.local else "authored",
                 release=release, adapter=adapter, config=config if model_driven else None,
                 max_investigations=arguments.max_investigations)
    try:
        server = create_server(app, port=arguments.port)
    except OSError:
        app.close()
        print(f"Cannot listen on 127.0.0.1:{arguments.port}. Choose another --port.", file=sys.stderr)
        return 2
    if not serve:
        return app, server
    port = server.server_address[1]
    status = app.status()
    print("Hawaii Activity Planner — local web interface (synthetic data only)")
    print(status["banner"])
    if model_driven:
        print(f"This process permits at most {app.limit} model-driven investigations; model/tool limits apply to each.")
    print(f"Open: http://127.0.0.1:{port}/#token={app.token}")
    print("The token authorizes runs from this browser tab only. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()
    print("Stopped.")
    return 0
