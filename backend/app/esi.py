from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .config import settings


class EsiClient:
    def __init__(self) -> None:
        compatibility_date = (datetime.now(timezone.utc) - timedelta(hours=11)).date().isoformat()
        self.headers = {
            "User-Agent": settings.esi_user_agent,
            "X-Compatibility-Date": compatibility_date,
        }

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> httpx.Response:
        response = await client.get(path, params=params)
        response.raise_for_status()
        return response

    async def fetch_market_orders(self, region_id: int) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=settings.esi_base_url,
            headers=self.headers,
            timeout=settings.request_timeout_seconds,
        ) as client:
            first = await self._get(
                client,
                f"/markets/{region_id}/orders/",
                {"order_type": "all", "page": 1},
            )
            total_pages = int(first.headers.get("X-Pages", "1"))
            max_pages = settings.market_max_pages
            if max_pages > 0:
                total_pages = min(total_pages, max_pages)

            orders = list(first.json())
            if total_pages <= 1:
                return orders

            semaphore = asyncio.Semaphore(8)

            async def fetch_page(page: int) -> list[dict[str, Any]]:
                async with semaphore:
                    response = await self._get(
                        client,
                        f"/markets/{region_id}/orders/",
                        {"order_type": "all", "page": page},
                    )
                    return list(response.json())

            pages = await asyncio.gather(*(fetch_page(page) for page in range(2, total_pages + 1)))
            for page_orders in pages:
                orders.extend(page_orders)
            return orders

    async def fetch_history(self, region_id: int, type_id: int) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=settings.esi_base_url,
            headers=self.headers,
            timeout=settings.request_timeout_seconds,
        ) as client:
            response = await self._get(
                client,
                f"/markets/{region_id}/history/",
                {"type_id": type_id},
            )
            return list(response.json())

    async def fetch_histories(self, region_id: int, type_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        semaphore = asyncio.Semaphore(8)
        histories: dict[int, list[dict[str, Any]]] = {}

        async def fetch_one(type_id: int) -> None:
            async with semaphore:
                try:
                    histories[type_id] = await self.fetch_history(region_id, type_id)
                except httpx.HTTPError:
                    histories[type_id] = []

        await asyncio.gather(*(fetch_one(type_id) for type_id in type_ids))
        return histories

    async def resolve_names(self, type_ids: list[int]) -> dict[int, str]:
        if not type_ids:
            return {}

        names: dict[int, str] = {}
        async with httpx.AsyncClient(
            base_url=settings.esi_base_url,
            headers=self.headers,
            timeout=settings.request_timeout_seconds,
        ) as client:
            for start in range(0, len(type_ids), 1000):
                batch = type_ids[start : start + 1000]
                response = await client.post("/universe/names/", json=batch)
                response.raise_for_status()
                for item in response.json():
                    if item.get("category") == "inventory_type":
                        names[int(item["id"])] = item["name"]
        return names
