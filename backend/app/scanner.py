from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import log10, log1p
from statistics import mean

from .database import get_settings
from .esi import EsiClient
from .models import MarketOpportunity, MarketScanRequest, MarketScanResponse


@dataclass
class OrderBook:
    type_id: int
    sell_prices: list[float]
    buy_prices: list[float]
    sell_volume: int
    buy_volume: int
    order_count: int


RISK_BUDGET = {
    "conservative": 0.06,
    "normal": 0.12,
    "aggressive": 0.22,
}

VOLUME_TURNOVER = {
    "conservative": 0.04,
    "normal": 0.08,
    "aggressive": 0.16,
}


def _average_daily_volume(history: list[dict]) -> int:
    if not history:
        return 0
    recent = history[-14:]
    return int(mean(day.get("volume", 0) for day in recent))


def _competition_level(order_count: int, spread_percent: float) -> str:
    if order_count > 120 or spread_percent < 4:
        return "Heavy"
    if order_count > 45 or spread_percent < 9:
        return "Moderate"
    return "Light"


def _score(
    net_margin_percent: float,
    daily_volume: int,
    minimum_daily_volume: int,
    competition_level: str,
    required_isk: float,
    item_budget: float,
) -> float:
    margin_score = min(net_margin_percent / 20, 1) * 35
    volume_score = min(daily_volume / max(minimum_daily_volume * 4, 1), 1) * 30
    competition_multiplier = {"Light": 1.0, "Moderate": 0.72, "Heavy": 0.42}[competition_level]
    competition_score = competition_multiplier * 20
    affordability_score = max(0, 1 - (required_isk / max(item_budget, 1))) * 15
    return round(margin_score + volume_score + competition_score + affordability_score, 1)


def _risk_badge(net_margin_percent: float, daily_volume: int, competition: str, minimum_daily_volume: int) -> str:
    if daily_volume >= minimum_daily_volume * 4 and net_margin_percent >= 8 and competition != "Heavy":
        return "Low"
    if daily_volume >= minimum_daily_volume * 2 and net_margin_percent >= 5:
        return "Medium"
    return "High"


def _build_reason(name: str, margin: float, volume: int, competition: str, risk: str) -> str:
    return (
        f"{name} has a {margin:.1f}% estimated net margin after fees, "
        f"about {volume:,} units moving per day, and {competition.lower()} visible order competition. "
        f"Risk is marked {risk.lower()} based on margin, volume, and order pressure."
    )


def _build_books(orders: list[dict], station_id: int) -> dict[int, OrderBook]:
    grouped: dict[int, dict[str, list]] = defaultdict(lambda: {"sell": [], "buy": [], "sell_vol": 0, "buy_vol": 0})
    for order in orders:
        if int(order.get("location_id", 0)) != station_id:
            continue
        type_id = int(order["type_id"])
        price = float(order["price"])
        remaining = int(order.get("volume_remain", 0))
        bucket = grouped[type_id]
        if order.get("is_buy_order"):
            bucket["buy"].append(price)
            bucket["buy_vol"] += remaining
        else:
            bucket["sell"].append(price)
            bucket["sell_vol"] += remaining

    books: dict[int, OrderBook] = {}
    for type_id, bucket in grouped.items():
        books[type_id] = OrderBook(
            type_id=type_id,
            sell_prices=bucket["sell"],
            buy_prices=bucket["buy"],
            sell_volume=bucket["sell_vol"],
            buy_volume=bucket["buy_vol"],
            order_count=len(bucket["sell"]) + len(bucket["buy"]),
        )
    return books


async def scan_market(payload: MarketScanRequest) -> MarketScanResponse:
    app_settings = get_settings()
    esi = EsiClient()
    orders = await esi.fetch_market_orders(payload.region_id)
    books = _build_books(orders, payload.station_id)

    rough_candidates: list[tuple[int, OrderBook, float, float, float, float]] = []
    for type_id, book in books.items():
        if not book.sell_prices or not book.buy_prices:
            continue
        best_sell = min(book.sell_prices)
        best_buy = max(book.buy_prices)
        if best_sell <= best_buy or best_sell <= 0:
            continue
        spread_percent = ((best_sell - best_buy) / best_buy) * 100
        if spread_percent < payload.minimum_margin_percent:
            continue
        if spread_percent > 80:
            continue
        if payload.max_isk_per_item and best_sell > payload.max_isk_per_item:
            continue
        visible_depth = min(book.sell_volume, book.buy_volume)
        if visible_depth <= 0:
            continue
        plausibility_score = min(spread_percent, 30) * log1p(visible_depth) * log10(best_buy + 10)
        rough_candidates.append((type_id, book, best_buy, best_sell, spread_percent, plausibility_score))

    rough_candidates.sort(key=lambda item: item[5], reverse=True)
    rough_candidates = rough_candidates[: min(350, max(payload.result_limit * 12, 80))]

    type_ids = [candidate[0] for candidate in rough_candidates]
    histories = await esi.fetch_histories(payload.region_id, type_ids)
    names = await esi.resolve_names(type_ids)

    opportunities: list[MarketOpportunity] = []
    capital_budget = payload.starting_capital * RISK_BUDGET[payload.risk_level]
    for type_id, book, best_buy, best_sell, spread_percent, _candidate_score in rough_candidates:
        daily_volume = _average_daily_volume(histories.get(type_id, []))
        if daily_volume < payload.minimum_daily_volume:
            continue

        recommended_buy = round(best_buy * 1.0001, 2)
        recommended_sell = round(best_sell * 0.9999, 2)
        broker_fee_per_unit = (recommended_buy + recommended_sell) * app_settings.broker_fee_rate
        sales_tax_per_unit = recommended_sell * app_settings.sales_tax_rate
        net_profit_per_unit = recommended_sell - recommended_buy - broker_fee_per_unit - sales_tax_per_unit
        if net_profit_per_unit <= 0:
            continue

        required_per_unit = recommended_buy * (1 + app_settings.broker_fee_rate)
        net_margin = (net_profit_per_unit / required_per_unit) * 100
        if net_margin < payload.minimum_margin_percent:
            continue

        item_budget = payload.max_isk_per_item if payload.max_isk_per_item > 0 else capital_budget
        item_budget = min(item_budget, capital_budget)
        safe_by_budget = int(item_budget // required_per_unit)
        safe_by_volume = max(1, int(daily_volume * VOLUME_TURNOVER[payload.risk_level]))
        safe_by_supply = max(1, int(book.sell_volume * 0.08))
        suggested_quantity = max(0, min(safe_by_budget, safe_by_volume, safe_by_supply))
        if suggested_quantity <= 0:
            continue

        required_isk = required_per_unit * suggested_quantity
        expected_profit = net_profit_per_unit * suggested_quantity
        if expected_profit < payload.minimum_expected_profit:
            continue

        if spread_percent > 70 and daily_volume < payload.minimum_daily_volume * 4:
            continue

        competition = _competition_level(book.order_count, spread_percent)
        risk = _risk_badge(net_margin, daily_volume, competition, payload.minimum_daily_volume)
        score = _score(
            net_margin,
            daily_volume,
            payload.minimum_daily_volume,
            competition,
            required_isk,
            item_budget,
        )
        name = names.get(type_id, f"Type {type_id}")
        action = (
            f"Place a buy order around {recommended_buy:,.2f} ISK. "
            f"After it fills, relist around {recommended_sell:,.2f} ISK. "
            "Do this manually in the EVE client."
        )
        opportunities.append(
            MarketOpportunity(
                type_id=type_id,
                item_name=name,
                buy_price=best_buy,
                sell_price=best_sell,
                spread=best_sell - best_buy,
                estimated_broker_fee=broker_fee_per_unit * suggested_quantity,
                estimated_sales_tax=sales_tax_per_unit * suggested_quantity,
                net_margin_percent=round(net_margin, 2),
                daily_volume=daily_volume,
                competition_level=competition,
                recommended_buy_price=recommended_buy,
                recommended_sell_price=recommended_sell,
                suggested_quantity=suggested_quantity,
                required_isk=round(required_isk, 2),
                expected_profit=round(expected_profit, 2),
                risk=risk,
                score=score,
                reason=_build_reason(name, net_margin, daily_volume, competition, risk),
                action=action,
            )
        )

    opportunities.sort(key=lambda item: item.score, reverse=True)
    return MarketScanResponse(
        scanned_at=datetime.now(timezone.utc),
        source="ESI public market endpoints",
        total_orders_seen=len(orders),
        total_station_orders=sum(1 for order in orders if int(order.get("location_id", 0)) == payload.station_id),
        opportunities=opportunities[: payload.result_limit],
    )
