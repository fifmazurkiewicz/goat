"""Testy metadanych deployu."""

import os

from app.core.version import get_deploy_info


def test_get_deploy_info_from_render_env(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123def456789")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.delenv("APP_GIT_SHA", raising=False)

    info = get_deploy_info(environment="production")

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
