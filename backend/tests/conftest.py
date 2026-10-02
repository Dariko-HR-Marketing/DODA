"""Session-wide test isolation guards — no business logic here.

This project's own dev `.env` (gitignored, never committed) now
routinely carries real, working AI-provider credentials (Gemini/Claude/
OpenAI keys, each verified against the real provider API via a one-off
script — see CLAUDE.md's running log), so a developer can manually
confirm a real integration from this same checkout. But
`tests/integration/test_conversations_api.py`'s own module docstring
(and every test built on top of it) states a flat assumption: "No real
provider credential is configured in this test environment, so every
turn runs against NullModelGateway." That assumption was only ever true
by accident — nothing enforced it, it just happened to hold because no
real key had been added to `.env` yet. The moment one was, 10 tests
across the AI-chat surface broke for the same single reason: `doda.
config.get_settings()` reads `.env` live, with no override, so a real
key in that file makes `doda.ai.factory.get_gateway` return a REAL
adapter instead of `NullModelGateway` inside the test process itself.

This fixture makes the assumption true on purpose, for every test,
regardless of what an operator's local `.env` happens to contain —
Settings() always resolves openai_api_key/gemini_api_key/claude_api_key
to None unless a test explicitly provides its own value. That "unless"
is not a gap: pydantic-settings' own precedence (explicit init kwargs
beat environment variables, which beat the `.env` file) means a test
that already does `Settings(openai_api_key="fake-test-key")` (see
tests/test_config.py's own SecretStr-masking tests) is completely
unaffected — its explicit kwarg still wins over this fixture's
`setdefault`.
"""

import pytest

from doda import config as config_module


@pytest.fixture(autouse=True)
def _no_real_ai_provider_keys_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    original_init = config_module.Settings.__init__

    def _patched_init(self: config_module.Settings, **kwargs: object) -> None:
        kwargs.setdefault("openai_api_key", None)
        kwargs.setdefault("gemini_api_key", None)
        kwargs.setdefault("claude_api_key", None)
        original_init(self, **kwargs)

    monkeypatch.setattr(config_module.Settings, "__init__", _patched_init)
    config_module.get_settings.cache_clear()
    yield
    config_module.get_settings.cache_clear()
