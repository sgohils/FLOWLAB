"""``FLOWLAB_CORS_ORIGINS`` is validated, not merely parsed.

The API has no authentication of any kind, so the browser origin list is the
only thing between a page the user visits and every stored trajectory.  It used
to be split on commas and handed to Starlette unchanged, which made
``FLOWLAB_CORS_ORIGINS=*`` a supported spelling of "every website can read this".

The policy is fail fast: a refused entry stops the process with a message that
names the value and the accepted form, because an operator who widens the list
and watches the API start must not be left believing their host is allowed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from backend.config import (
    CORS_ORIGIN_FORMAT,
    DEFAULT_CORS_ORIGINS,
    LOOPBACK_HOSTS,
    UNSAFE_CORS_FLAG,
    build_settings,
    is_loopback_origin,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _origins(value: str, monkeypatch) -> tuple[str, ...]:
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", value)
    return build_settings().cors_origins


# ------------------------------------------------------------- what is accepted


def test_the_default_list_is_unchanged_and_itself_valid():
    """Behaviour on the default path must not move, and it has to pass its own check."""
    assert DEFAULT_CORS_ORIGINS == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )
    assert build_settings().cors_origins == DEFAULT_CORS_ORIGINS
    assert all(is_loopback_origin(origin) for origin in DEFAULT_CORS_ORIGINS)


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "https://localhost:5173",
        "http://127.0.0.1:8080",
        "http://[::1]:5173",
        "http://[::1]",
        "http://localhost",
        "http://LOCALHOST:5173",  # host case is not identity
        "http://localhost:5173/",  # a trailing slash is the same origin
        "http://localhost:5173/app",  # a path is meaningless, and harmless
    ],
)
def test_loopback_origins_are_accepted(origin, monkeypatch):
    assert is_loopback_origin(origin)
    assert _origins(origin, monkeypatch) == (origin,)


def test_ports_and_a_list_of_several_origins_are_accepted(monkeypatch):
    value = " http://localhost:1 , ,http://127.0.0.1:65535,http://[::1]:4173,"
    assert _origins(value, monkeypatch) == (
        "http://localhost:1",
        "http://127.0.0.1:65535",
        "http://[::1]:4173",
    )


# ------------------------------------------------------------- what is refused


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://evil.example",
        "http://localhost.evil.com",  # the suffix trap
        "http://127.0.0.1.evil.com",
        "https://localhost.evil.com:5173",
        "http://evil.com/?next=http://localhost",
        "http://localhost:5173@evil.example",  # userinfo hides the real host
        "http://user:pass@localhost:5173",
        "http://[::2]:5173",  # a routable IPv6 address
        "localhost:5173",  # no scheme: not an origin a browser can send
        "//localhost:5173",
        "ftp://localhost:5173",
        "file:///etc/passwd",
        "http://192.168.1.10:5173",
    ],
)
def test_a_routable_or_wildcard_origin_is_refused(origin, monkeypatch):
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", origin)
    with pytest.raises(ValueError) as raised:
        build_settings()
    message = str(raised.value)
    assert origin in message, "the error must name the value the operator wrote"
    assert CORS_ORIGIN_FORMAT in message, "the error must state the accepted form"
    assert UNSAFE_CORS_FLAG in message
    assert "FLOWLAB_CORS_ORIGINS" in message
    assert "authentication" in message


def test_a_wildcard_is_refused_with_its_own_reason(monkeypatch):
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", "*")
    with pytest.raises(ValueError) as raised:
        build_settings()
    message = str(raised.value)
    assert "'*'" in message
    assert "wildcard" in message
    assert "every site" in message


def test_one_bad_entry_refuses_the_whole_list(monkeypatch):
    """A list is one decision: a typo in the last entry must not widen the first."""
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", "http://localhost:5173,https://evil.example")
    with pytest.raises(ValueError):
        build_settings()


def test_the_substring_trap_is_why_membership_is_not_a_substring_test():
    """Documented, because the obvious implementation passes this case."""
    assert "localhost" in "http://localhost.evil.com"
    assert "http://localhost.evil.com" not in LOOPBACK_HOSTS
    assert not is_loopback_origin("http://localhost.evil.com")


# ------------------------------------------------------------- empty and default


@pytest.mark.parametrize("value", ["", "   ", " , , "])
def test_an_empty_setting_falls_back_to_the_safe_default(value, monkeypatch):
    """Unset, not "allow nothing" and never "allow everything"."""
    assert _origins(value, monkeypatch) == DEFAULT_CORS_ORIGINS


def test_unset_falls_back_to_the_safe_default(monkeypatch):
    monkeypatch.delenv("FLOWLAB_CORS_ORIGINS", raising=False)
    assert build_settings().cors_origins == DEFAULT_CORS_ORIGINS


# ------------------------------------------------------------- the escape hatch


def test_the_escape_hatch_is_opt_in(monkeypatch):
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", "*")
    with pytest.raises(ValueError):
        build_settings()
    monkeypatch.setenv(UNSAFE_CORS_FLAG, "1")
    assert build_settings().cors_origins == ("*",)


def test_the_escape_hatch_is_loud_about_what_it_allowed(monkeypatch, caplog):
    monkeypatch.setenv("FLOWLAB_CORS_ORIGINS", "https://intranet.example")
    monkeypatch.setenv(UNSAFE_CORS_FLAG, "true")
    with caplog.at_level(logging.WARNING, logger="backend.config"):
        assert build_settings().cors_origins == ("https://intranet.example",)
    warning = "\n".join(record.getMessage() for record in caplog.records)
    assert UNSAFE_CORS_FLAG in warning
    assert "https://intranet.example" in warning
    assert "no authentication" in warning


def test_the_escape_hatch_does_not_change_the_default(monkeypatch):
    """Setting the flag alone must not loosen anything."""
    monkeypatch.delenv("FLOWLAB_CORS_ORIGINS", raising=False)
    monkeypatch.setenv(UNSAFE_CORS_FLAG, "1")
    assert build_settings().cors_origins == DEFAULT_CORS_ORIGINS


# ------------------------------------------------------------- what ships with it


def test_the_running_application_never_allow_lists_a_routable_host():
    from backend import main

    origins = [
        origin
        for middleware in main.app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
        for origin in middleware.kwargs["allow_origins"]
    ]
    assert origins
    assert [origin for origin in origins if not is_loopback_origin(origin)] == []


def test_the_compose_file_configures_only_loopback_origins():
    """The value docker-compose.yml passes is accepted by the validation above."""
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    raw = services["backend"]["environment"]["FLOWLAB_CORS_ORIGINS"]
    # A ${VAR:-default} interpolation: the default is the part that must validate.
    value = raw.split(":-", 1)[1].rstrip("}")
    origins = tuple(part.strip() for part in value.split(","))
    assert origins == DEFAULT_CORS_ORIGINS
    assert all(is_loopback_origin(origin) for origin in origins)
    # And nothing reads it on the Vite service, where it was a no-op.
    assert "FLOWLAB_CORS_ORIGINS" not in services["frontend"].get("environment", {})
