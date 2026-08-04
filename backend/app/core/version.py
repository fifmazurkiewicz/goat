"""Metadane deployu (commit, branch) — Render/Vercel ustawiają env automatycznie."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeployInfo:
    environment: str
    git_sha: str | None
    git_sha_full: str | None
    git_branch: str | None
    build_time: str | None
    git_repo: str


def _first_env(*keys: str) -> str | None:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def _try_git(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (result.stdout or "").strip()
    return value or None


def _short_sha(full: str | None) -> str | None:
    if not full:
        return None
    return full if len(full) <= 12 else full[:7]


def get_deploy_info(*, environment: str) -> DeployInfo:
    git_sha_full = _first_env("APP_GIT_SHA", "RENDER_GIT_COMMIT", "GIT_COMMIT")
    git_branch = _first_env("APP_GIT_BRANCH", "RENDER_GIT_BRANCH", "GIT_BRANCH", "VERCEL_GIT_COMMIT_REF")

    if environment == "local" and not git_sha_full:
        git_sha_full = _try_git(["git", "rev-parse", "HEAD"])
    if environment == "local" and not git_branch:
        git_branch = _try_git(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    build_time = _first_env("APP_BUILD_TIME", "RENDER_BUILD_TIME")
    git_repo = _first_env("APP_GIT_REPO") or "fifmazurkiewicz/goat"

    return DeployInfo(
        environment=environment,
        git_sha=_short_sha(git_sha_full),
        git_sha_full=git_sha_full,
        git_branch=git_branch,
        build_time=build_time,
        git_repo=git_repo,
    )
