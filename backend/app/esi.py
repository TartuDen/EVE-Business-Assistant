from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .config import settings
from .safety import ItemMetadata


_history_cache: dict[tuple[int, int], list[dict[str, Any]]] = {}
_name_cache: dict[int, str] = {}
_type_cache: dict[int, ItemMetadata] = {}
_group_cache: dict[int, tuple[str, int]] = {}
_category_cache: dict[int, str] = {}


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
        cache_key = (region_id, type_id)
        if cache_key in _history_cache:
            return _history_cache[cache_key]

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
            history = list(response.json())
            _history_cache[cache_key] = history
            return history

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
        missing = [type_id for type_id in type_ids if type_id not in _name_cache]
        async with httpx.AsyncClient(
            base_url=settings.esi_base_url,
            headers=self.headers,
            timeout=settings.request_timeout_seconds,
        ) as client:
            for start in range(0, len(missing), 1000):
                batch = missing[start : start + 1000]
                if not batch:
                    continue
                response = await client.post("/universe/names/", json=batch)
                response.raise_for_status()
                for item in response.json():
                    if item.get("category") == "inventory_type":
                        _name_cache[int(item["id"])] = item["name"]
        for type_id in type_ids:
            if type_id in _name_cache:
                names[type_id] = _name_cache[type_id]
        return names

    async def fetch_type_metadata(self, type_ids: list[int], names: dict[int, str] | None = None) -> dict[int, ItemMetadata]:
        metadata: dict[int, ItemMetadata] = {}
        names = names or {}
        missing = [type_id for type_id in type_ids if type_id not in _type_cache]
        semaphore = asyncio.Semaphore(8)

        async with httpx.AsyncClient(
            base_url=settings.esi_base_url,
            headers=self.headers,
            timeout=settings.request_timeout_seconds,
        ) as client:

            async def get_group(group_id: int) -> tuple[str, int]:
                if group_id in _group_cache:
                    return _group_cache[group_id]
                response = await self._get(client, f"/universe/groups/{group_id}/", {})
                data = response.json()
                result = (data.get("name", "Unknown"), int(data.get("category_id", 0)))
                _group_cache[group_id] = result
                return result

            async def get_category(category_id: int) -> str:
                if category_id in _category_cache:
                    return _category_cache[category_id]
                response = await self._get(client, f"/universe/categories/{category_id}/", {})
                data = response.json()
                result = data.get("name", "Unknown")
                _category_cache[category_id] = result
                return result

            async def fetch_one(type_id: int) -> None:
                async with semaphore:
                    try:
                        response = await self._get(client, f"/universe/types/{type_id}/", {})
                        data = response.json()
                        group_name, category_id = await get_group(int(data.get("group_id", 0)))
                        category_name = await get_category(category_id) if category_id else "Unknown"
                        _type_cache[type_id] = ItemMetadata(
                            name=data.get("name") or names.get(type_id, f"Type {type_id}"),
                            category=category_name,
                            group=group_name,
                        )
                    except httpx.HTTPError:
                        _type_cache[type_id] = ItemMetadata(name=names.get(type_id, f"Type {type_id}"))

            await asyncio.gather(*(fetch_one(type_id) for type_id in missing))

        for type_id in type_ids:
            metadata[type_id] = _type_cache.get(type_id, ItemMetadata(name=names.get(type_id, f"Type {type_id}")))
        return metadata
