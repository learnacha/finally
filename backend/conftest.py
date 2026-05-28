"""
Root conftest.py for the backend test suite.

Adds the backend directory to sys.path so that `from app.market...` imports
work when pytest is run from inside `backend/`.

Also stubs the `massive` package if it is not installed, so tests can run
in environments without the real Polygon.io SDK.
"""
import sys
import types
from pathlib import Path

# Make sure `app` is importable when running pytest from backend/
sys.path.insert(0, str(Path(__file__).parent))


def _stub_massive():
    """Inject a minimal stub for the `massive` package."""

    # Create stub modules
    massive_mod = types.ModuleType("massive")
    rest_mod = types.ModuleType("massive.rest")
    models_mod = types.ModuleType("massive.rest.models")
    exc_mod = types.ModuleType("massive.exceptions")

    class RESTClient:
        def __init__(self, api_key: str = ""):
            self.api_key = api_key

        def get_snapshot_all(self, market: str, tickers=None):
            return []

    class TickerSnapshot:
        pass

    class AuthorizationError(Exception):
        pass

    class BadResponse(Exception):
        pass

    class NoResultsError(Exception):
        pass

    massive_mod.RESTClient = RESTClient
    models_mod.TickerSnapshot = TickerSnapshot
    exc_mod.AuthorizationError = AuthorizationError
    exc_mod.BadResponse = BadResponse
    exc_mod.NoResultsError = NoResultsError

    sys.modules.setdefault("massive", massive_mod)
    sys.modules.setdefault("massive.rest", rest_mod)
    sys.modules.setdefault("massive.rest.models", models_mod)
    sys.modules.setdefault("massive.exceptions", exc_mod)


try:
    import massive  # noqa: F401  — real package available
except ImportError:
    _stub_massive()
