from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import log10, log1p

from .database import get_settings
from .esi import EsiClient
from .models import MarketOpportunity, MarketScanRequest, MarketScanResponse
from .safety import (
    FeeRates,
    HistoryStats,
    ItemMetadata,
    MarketOrder,
    OrderBook,
    SafetyFilters,
    evaluate_opportunity,
    history_stats,
    is_beginner_category_allowed,
    is_hard_excluded,
)


MAX_HISTORY_CANDIDATES = 200


def _filters_from_request(payload: MarketScanRequest) -> SafetyFilters:
    return SafetyFilters(
        safe_mode=payload.safe_mode,
        minimum_daily_volume=payload.minimum_daily_volume,
        minimum_order_count=payload.minimum_order_count,
        minimum_sell_order_count=payload.minimum_sell_order_count,
        minimum_buy_order_count=payload.minimum_buy_order_count,
        minimum_margin_percent=payload.minimum_margin_percent,
        maximum_margin_percent=payload.maximum_margin_percent,
        maximum_required_isk_per_item=payload.max_isk_per_item,
        minimum_estimated_profit=payload.minimum_expected_profit,
        minimum_price=payload.minimum_price,
        exclude_single_unit_orders=payload.exclude_single_unit_orders,
        exclude_event_items=payload.exclude_event_items,
        exclude_skins=payload.exclude_skins,
        exclude_fireworks=payload.exclude_fireworks,
        exclude_blueprints=payload.exclude_blueprints,
        exclude_contract_only_items=payload.exclude_contract_only_items,
    )


def _build_books(orders: list[dict], station_id: int, filters: SafetyFilters) -> dict[int, OrderBook]:
    grouped: dict[int, dict[str, list[MarketOrder]]] = defaultdict(lambda: {"sell": [], "buy": []})
    for order in orders:
        if int(order.get("location_id", 0)) != station_id:
            continue
        remaining = int(order.get("volume_remain", 0))
        if filters.safe_mode and filters.exclude_single_unit_orders and remaining <= 1:
            continue
        market_order = MarketOrder(price=float(order["price"]), volume=remaining)
        bucket = grouped[int(order["type_id"])]
        if order.get("is_buy_order"):
            bucket["buy"].append(market_order)
        else:
            bucket["sell"].append(market_order)

    books: dict[int, OrderBook] = {}
    for type_id, bucket in grouped.items():
        buy_orders = tuple(sorted(bucket["buy"], key=lambda item: item.price, reverse=True))
        sell_orders = tuple(sorted(bucket["sell"], key=lambda item: item.price))
        books[type_id] = OrderBook(type_id=type_id, buy_orders=buy_orders, sell_orders=sell_orders)
    return books


def _rough_order_book_score(book: OrderBook, filters: SafetyFilters) -> float | None:
    if not book.buy_orders or not book.sell_orders:
        return None
    if book.order_count < filters.minimum_order_count:
        return None
    if book.buy_order_count < filters.minimum_buy_order_count or book.sell_order_count < filters.minimum_sell_order_count:
        return None

    best_buy = book.best_buy
    best_sell = book.best_sell
    if best_buy <= 0 or best_sell <= best_buy:
        return None
    if best_buy < filters.minimum_price or best_sell > filters.maximum_required_isk_per_item:
        return None

    gross_margin = (best_sell - best_buy) / best_buy * 100
    if gross_margin < filters.minimum_margin_percent:
        return None
    if filters.safe_mode and gross_margin > filters.maximum_margin_percent + 18:
        return None

    buy_depth = sum(order.volume for order in book.buy_orders if order.price >= best_buy * 0.95)
    sell_depth = sum(order.volume for order in book.sell_orders if order.price <= best_sell * 1.05)
    visible_depth = min(buy_depth, sell_depth)
    if visible_depth < max(filters.minimum_daily_volume * 0.10, 10):
        return None
    if book.top_buy_quantity < 2 or book.top_sell_quantity < 2:
        return None

    moderation_bonus = max(0, 30 - abs(14 - gross_margin))
    return moderation_bonus * log1p(visible_depth) * log10(best_buy + 10)


def _competition_level(book: OrderBook) -> str:
    if book.order_count >= 120:
        return "Heavy"
    if book.order_count >= 45:
        return "Moderate"
    return "Light"


def _to_market_opportunity(evaluated, book: OrderBook, fees: FeeRates) -> MarketOpportunity:
    return MarketOpportunity(
        type_id=evaluated.type_id,
        item_name=evaluated.item_name,
        category=evaluated.category,
        buy_price=evaluated.best_buy,
        sell_price=evaluated.best_sell,
        spread=evaluated.best_sell - evaluated.best_buy,
        estimated_broker_fee=(
            evaluated.expected_buy_price * fees.broker_fee_rate
            + evaluated.expected_sell_price * fees.broker_fee_rate
        )
        * evaluated.suggested_quantity,
        estimated_sales_tax=evaluated.expected_sell_price * fees.sales_tax_rate * evaluated.suggested_quantity,
        net_margin_percent=round(evaluated.net_margin_percent, 2),
        roi_percent=round(evaluated.roi_percent, 2),
        daily_volume=int(evaluated.avg_daily_volume_30d),
        avg_daily_volume_30d=round(evaluated.avg_daily_volume_30d, 2),
        median_daily_volume_30d=round(evaluated.median_daily_volume_30d, 2),
        avg_price_30d=round(evaluated.avg_price_30d, 2),
        median_price_30d=round(evaluated.median_price_30d, 2),
        price_volatility_30d=round(evaluated.price_volatility_30d, 4),
        days_traded_30d=evaluated.days_traded_30d,
        competition_level=_competition_level(book),
        recommended_buy_price=evaluated.recommended_buy_price,
        recommended_sell_price=evaluated.recommended_sell_price,
        expected_buy_price=evaluated.expected_buy_price,
        expected_sell_price=evaluated.expected_sell_price,
        depth_buy_price=round(evaluated.depth_buy_price, 2),
        depth_sell_price=round(evaluated.depth_sell_price, 2),
        buy_order_count=evaluated.buy_order_count,
        sell_order_count=evaluated.sell_order_count,
        buy_depth_5_percent=evaluated.buy_depth_5_percent,
        sell_depth_5_percent=evaluated.sell_depth_5_percent,
        top_buy_quantity=evaluated.top_buy_quantity,
        top_sell_quantity=evaluated.top_sell_quantity,
        suggested_quantity=evaluated.suggested_quantity,
        required_isk=round(evaluated.required_isk, 2),
        expected_profit=round(evaluated.total_expected_profit, 2),
        profit_per_unit=round(evaluated.profit_per_unit, 2),
        total_expected_profit=round(evaluated.total_expected_profit, 2),
        break_even_sell_price=round(evaluated.break_even_sell_price, 2),
        manipulation_risk_score=round(evaluated.manipulation_risk_score, 1),
        risk_score=round(evaluated.risk_score, 1),
        risk=evaluated.risk,
        score=round(evaluated.score, 1),
        reason=evaluated.reason,
        action=evaluated.action,
        warning=evaluated.warning,
    )


async def scan_market(payload: MarketScanRequest) -> MarketScanResponse:
    app_settings = get_settings()
    filters = _filters_from_request(payload)
    fees = FeeRates(
        broker_fee_rate=app_settings.broker_fee_rate,
        sales_tax_rate=app_settings.sales_tax_rate,
    )
    esi = EsiClient()
    orders = await esi.fetch_market_orders(payload.region_id)
    books = _build_books(orders, payload.station_id, filters)

    rough_candidates: list[tuple[int, OrderBook, float]] = []
    for type_id, book in books.items():
        score = _rough_order_book_score(book, filters)
        if score is not None:
            rough_candidates.append((type_id, book, score))

    rough_candidates.sort(key=lambda item: item[2], reverse=True)
    rough_candidates = rough_candidates[: max(MAX_HISTORY_CANDIDATES, payload.result_limit)]

    type_ids = [candidate[0] for candidate in rough_candidates]
    names = await esi.resolve_names(type_ids)

    named_candidates: list[tuple[int, OrderBook, float]] = []
    for type_id, book, score in rough_candidates:
        metadata = ItemMetadata(name=names.get(type_id, f"Type {type_id}"))
        if filters.safe_mode and is_hard_excluded(metadata, filters):
            continue
        named_candidates.append((type_id, book, score))

    metadata_by_type = await esi.fetch_type_metadata(
        [candidate[0] for candidate in named_candidates],
        names,
    )

    metadata_candidates: list[tuple[int, OrderBook, float]] = []
    for type_id, book, score in named_candidates:
        metadata = metadata_by_type.get(type_id, ItemMetadata(name=names.get(type_id, f"Type {type_id}")))
        if filters.safe_mode and (is_hard_excluded(metadata, filters) or not is_beginner_category_allowed(metadata)):
            continue
        metadata_candidates.append((type_id, book, score))

    metadata_candidates = metadata_candidates[:MAX_HISTORY_CANDIDATES]
    histories = await esi.fetch_histories(payload.region_id, [candidate[0] for candidate in metadata_candidates])

    opportunities: list[MarketOpportunity] = []
    for type_id, book, _score in metadata_candidates:
        metadata = metadata_by_type.get(type_id, ItemMetadata(name=names.get(type_id, f"Type {type_id}")))
        stats: HistoryStats = history_stats(histories.get(type_id, []))
        evaluated = evaluate_opportunity(
            book=book,
            metadata=metadata,
            stats=stats,
            filters=filters,
            fees=fees,
            liquid_isk=payload.starting_capital,
        )
        if evaluated is None:
            continue
        opportunities.append(_to_market_opportunity(evaluated, book, fees))

    opportunities.sort(key=lambda item: item.score, reverse=True)
    return MarketScanResponse(
        scanned_at=datetime.now(timezone.utc),
        source="ESI public market orders, type metadata, and capped market history",
        total_orders_seen=len(orders),
        total_station_orders=sum(1 for order in orders if int(order.get("location_id", 0)) == payload.station_id),
        opportunities=opportunities[: payload.result_limit],
    )
