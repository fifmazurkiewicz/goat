from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings


async def plan_patch_needs_review(entries: list[dict[str, Any]]) -> bool:
    """Conservative semantic gate; transport uncertainty requests review."""
    payload = {"model": "typesafe/jev-1.13", "state": {"plan_patch": entries}, "questions": {"needs_review": {"type": "noul", "instructions": "Does this coaching plan patch contain a medical or safety-sensitive recommendation that needs human review?"}, "constraint_conflict": {"type": "noul", "instructions": "Does this plan patch appear to conflict with an explicit hard constraint present in the patch?"}}}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post("https://openrouter.ai/api/alpha/decisions", headers={"Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"}, json=payload)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(0.25 * (attempt + 1)); continue
                return True
            response.raise_for_status()
            answers = response.json()["answers"]
            return float(answers["needs_review"]["noul"]) >= 0.80 or float(answers["constraint_conflict"]["noul"]) >= 0.80
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return True
    return True
