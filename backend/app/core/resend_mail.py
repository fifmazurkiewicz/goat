from html import escape

import httpx

from app.core.config import settings


async def notify_pending_account(account_email: str | None) -> None:
    if settings.resend_api_key is None:
        raise RuntimeError("RESEND_API_KEY is not configured")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}"},
            json={
                "from": settings.resend_from,
                "to": [settings.resend_mail],
                "subject": "GOAT: nowe konto do akceptacji",
                "text": f"Nowe konto: {account_email or 'nieznany adres'}\n\nOtwórz panel administratora: https://goat.fmazurkiewicz.dev/admin",
                "html": f"""<p>Nowe konto oczekuje na akceptację w <strong>GOAT</strong>.</p>
<p><strong>Konto:</strong> {escape(account_email or 'nieznany adres')}</p>
<p><a href=\"https://goat.fmazurkiewicz.dev/admin\">Otwórz panel administratora</a></p>""",
            },
        )
    response.raise_for_status()
