"""Tests for deploy metadata."""

from app.core.version import get_deploy_info, normalize_app_version, resolve_app_version


def test_get_deploy_info_from_render_env(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123def456789")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    info = get_deploy_info(environment="production")

    assert info.app_version == "0.2.0"
    assert info.git_sha == "abc123d"
    assert info.git_sha_full == "abc123def456789"
    assert info.git_branch == "main"
    assert info.environment == "production"


def test_get_deploy_info_app_override(monkeypatch) -> None:
    monkeypatch.setenv("APP_GIT_SHA", "deadbeef")
    monkeypatch.setenv("APP_GIT_BRANCH", "feature/x")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "ignored")

    info = get_deploy_info(environment="local")

    assert info.git_sha == "deadbeef"
    assert info.git_branch == "feature/x"


def test_resolve_app_version_from_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    assert resolve_app_version() == "1.2.3"


def test_normalize_app_version_rejects_invalid() -> None:
    assert normalize_app_version("not-a-version") == "0.0.0"
    assert normalize_app_version("2.0.0-beta.1") == "2.0.0-beta.1"
