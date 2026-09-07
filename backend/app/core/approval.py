"""Admin allowlist for auto-approval on first `profiles` insert (ADR-22)."""

from __future__ import annotations

SOLE_ADMIN_EMAIL = "fmazurkiewicz@gmail.com"


def is_auto_approved_email(email: str | None) -> bool:
    """True only for the sole admin address and any extra `ADMIN_EMAILS` entries."""
    if not email or not str(email).strip():
        return False
    normalized = str(email).strip().lower()
    from app.core.config import settings

    allowlist = {SOLE_ADMIN_EMAIL}
    allowlist.update(
        part.strip().lower() for part in settings.admin_emails.split(",") if part.strip()
    )
    return normalized in allowlist


def email_from_claims(claims: dict[str, object]) -> str | None:
    raw = claims.get("email")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    metadata = claims.get("user_metadata")
    if isinstance(metadata, dict):
        nested = metadata.get("email")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None
