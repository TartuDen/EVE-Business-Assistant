from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from statistics import mean, median, pstdev


@dataclass(frozen=True)
class MarketOrder:
    price: float
    volume: int


@dataclass(frozen=True)
class ItemMetadata:
    name: str
    category: str = "Unknown"
    group: str = "Unknown"


@dataclass(frozen=True)
class FeeRates:
    broker_fee_rate: float
    sales_tax_rate: float


@dataclass(frozen=True)
class SafetyFilters:
    safe_mode: bool = True
    minimum_daily_volume: int = 500
    minimum_order_count: int = 20
    minimum_sell_order_count: int = 10
    minimum_buy_order_count: int = 10
    minimum_margin_percent: float = 4
    maximum_margin_percent: float = 25
    maximum_required_isk_per_item: float = 25_000_000
    maximum_total_position_fraction: float = 0.05
    minimum_estimated_profit: float = 100_000
    minimum_price: float = 1_000
    exclude_single_unit_orders: bool = True
    exclude_event_items: bool = True
    exclude_skins: bool = True
    exclude_fireworks: bool = True
    exclude_blueprints: bool = True
    exclude_contract_only_items: bool = True


@dataclass(frozen=True)
class OrderBook:
    type_id: int
    buy_orders: tuple[MarketOrder, ...]
    sell_orders: tuple[MarketOrder, ...]

    @property
    def best_buy(self) -> float:
        return self.buy_orders[0].price if self.buy_orders else 0

    @property
    def best_sell(self) -> float:
        return self.sell_orders[0].price if self.sell_orders else 0

    @property
    def top_buy_quantity(self) -> int:
        return self.buy_orders[0].volume if self.buy_orders else 0

    @property
    def top_sell_quantity(self) -> int:
        return self.sell_orders[0].volume if self.sell_orders else 0

    @property
    def buy_order_count(self) -> int:
        return len(self.buy_orders)

    @property
    def sell_order_count(self) -> int:
        return len(self.sell_orders)

    @property
    def order_count(self) -> int:
        return self.buy_order_count + self.sell_order_count


@dataclass(frozen=True)
class HistoryStats:
    avg_daily_volume_30d: float
    median_daily_volume_30d: float
    avg_price_30d: float
    median_price_30d: float
    avg_price_7d: float
    price_volatility_30d: float
    days_traded_30d: int


@dataclass(frozen=True)
class FeeResult:
    broker_fee_buy: float
    broker_fee_sell: float
    sales_tax: float
    net_profit_per_unit: float
    margin_percent: float
    break_even_sell_price: float


@dataclass(frozen=True)
class EvaluatedOpportunity:
    type_id: int
    item_name: str
    category: str
    best_buy: float
    best_sell: float
    recommended_buy_price: float
    recommended_sell_price: float
    expected_buy_price: float
    expected_sell_price: float
    depth_buy_price: float
    depth_sell_price: float
    buy_order_count: int
    sell_order_count: int
    buy_depth_5_percent: int
    sell_depth_5_percent: int
    top_buy_quantity: int
    top_sell_quantity: int
    avg_daily_volume_30d: float
    median_daily_volume_30d: float
    avg_price_30d: float
    median_price_30d: float
    price_volatility_30d: float
    days_traded_30d: int
    profit_per_unit: float
    total_expected_profit: float
    required_isk: float
    break_even_sell_price: float
    net_margin_percent: float
    roi_percent: float
    suggested_quantity: int
    manipulation_risk_score: float
    risk_score: float
    risk: str
    score: float
    reason: str
    action: str
    warning: str


@lru_cache(maxsize=1)
def load_scanner_config() -> dict[str, list[str]]:
    path = Path(__file__).with_name("scanner_config.json")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def history_stats(history: list[dict]) -> HistoryStats:
    recent = history[-30:]
    if not recent:
        return HistoryStats(0, 0, 0, 0, 0, 1, 0)

    volumes = [float(day.get("volume", 0)) for day in recent]
    prices = [float(day.get("average", 0)) for day in recent if float(day.get("average", 0)) > 0]
    if not prices:
        prices = [0]
    avg_price = mean(prices)
    volatility = pstdev(prices) / avg_price if avg_price > 0 and len(prices) > 1 else 0
    return HistoryStats(
        avg_daily_volume_30d=mean(volumes),
        median_daily_volume_30d=median(volumes),
        avg_price_30d=avg_price,
        median_price_30d=median(prices),
        avg_price_7d=mean(prices[-7:]),
        price_volatility_30d=volatility,
        days_traded_30d=sum(1 for volume in volumes if volume > 0),
    )


def calculate_fees(expected_buy_price: float, expected_sell_price: float, fees: FeeRates) -> FeeResult:
    broker_fee_buy = expected_buy_price * fees.broker_fee_rate
    broker_fee_sell = expected_sell_price * fees.broker_fee_rate
    sales_tax = expected_sell_price * fees.sales_tax_rate
    net_profit = expected_sell_price - expected_buy_price - broker_fee_buy - broker_fee_sell - sales_tax
    margin = net_profit / expected_buy_price * 100 if expected_buy_price else 0
    sell_fee_factor = 1 - fees.broker_fee_rate - fees.sales_tax_rate
    break_even = expected_buy_price * (1 + fees.broker_fee_rate) / sell_fee_factor if sell_fee_factor > 0 else 0
    return FeeResult(
        broker_fee_buy=broker_fee_buy,
        broker_fee_sell=broker_fee_sell,
        sales_tax=sales_tax,
        net_profit_per_unit=net_profit,
        margin_percent=margin,
        break_even_sell_price=break_even,
    )


def depth_within_percent(orders: tuple[MarketOrder, ...], anchor_price: float, percent: float, buy_side: bool) -> int:
    if not orders or anchor_price <= 0:
        return 0
    if buy_side:
        cutoff = anchor_price * (1 - percent)
        return sum(order.volume for order in orders if order.price >= cutoff)
    cutoff = anchor_price * (1 + percent)
    return sum(order.volume for order in orders if order.price <= cutoff)


def weighted_average_for_quantity(orders: tuple[MarketOrder, ...], quantity: int) -> float:
    if quantity <= 0 or not orders:
        return 0

    remaining = quantity
    total_value = 0.0
    total_units = 0
    for order in orders:
        take = min(remaining, order.volume)
        total_value += take * order.price
        total_units += take
        remaining -= take
        if remaining <= 0:
            break
    return total_value / total_units if total_units else 0


def suggested_quantity(
    stats: HistoryStats,
    expected_buy_price: float,
    liquid_isk: float,
    buy_depth_5_percent: int,
    sell_depth_5_percent: int,
    filters: SafetyFilters,
    fees: FeeRates,
) -> int:
    max_position_isk = liquid_isk * filters.maximum_total_position_fraction
    cost_per_unit = expected_buy_price * (1 + fees.broker_fee_rate)
    affordable_quantity = int(max_position_isk // cost_per_unit) if cost_per_unit > 0 else 0
    limits = [
        int(stats.avg_daily_volume_30d * 0.05),
        int(stats.median_daily_volume_30d * 0.10),
        affordable_quantity,
        int(buy_depth_5_percent * 0.25),
        int(sell_depth_5_percent * 0.25),
    ]
    return max(0, min(limits))


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def is_hard_excluded(metadata: ItemMetadata, filters: SafetyFilters) -> bool:
    config = load_scanner_config()
    combined = f"{metadata.name} {metadata.category} {metadata.group}"
    if _contains_any(combined, config["excluded_keywords"]):
        return True

    name = metadata.name.lower()
    if filters.exclude_fireworks and "firework" in name:
        return True
    if filters.exclude_skins and "skin" in combined.lower():
        return True
    if filters.exclude_blueprints and "blueprint" in combined.lower():
        return True
    if filters.exclude_event_items and _contains_any(combined, ["festival", "event", "collector", "crate"]):
        return True
    return False


def is_beginner_category_allowed(metadata: ItemMetadata) -> bool:
    config = load_scanner_config()
    combined = f"{metadata.category} {metadata.group} {metadata.name}"
    return _contains_any(combined, config["allowed_category_keywords"]) or _contains_any(
        combined,
        config["allowed_group_keywords"],
    )


def manipulation_risk(
    metadata: ItemMetadata,
    stats: HistoryStats,
    net_margin_percent: float,
    best_buy: float,
    best_sell: float,
    buy_order_count: int,
    sell_order_count: int,
    top_buy_quantity: int,
    top_sell_quantity: int,
    filters: SafetyFilters,
) -> float:
    risk = 0.0
    if is_hard_excluded(metadata, filters):
        risk += 75
    if filters.safe_mode and net_margin_percent > filters.maximum_margin_percent:
        risk += 35
    if stats.median_price_30d > 0:
        if best_sell > stats.median_price_30d * 1.25:
            risk += 25
        if best_buy < stats.median_price_30d * 0.60:
            risk += 25
    if buy_order_count + sell_order_count < filters.minimum_order_count:
        risk += 25
    if stats.avg_daily_volume_30d < filters.minimum_daily_volume:
        risk += 25
    if min(top_buy_quantity, top_sell_quantity) < max(5, stats.median_daily_volume_30d * 0.01):
        risk += 20
    if not is_beginner_category_allowed(metadata):
        risk += 30
    return min(100, risk)


def risk_label(risk_score: float) -> str:
    if risk_score <= 30:
        return "Low"
    if risk_score <= 55:
        return "Medium"
    if risk_score <= 75:
        return "High"
    return "Avoid"


def _risk_components(
    manipulation: float,
    volatility: float,
    stats: HistoryStats,
    buy_depth_5_percent: int,
    sell_depth_5_percent: int,
    filters: SafetyFilters,
) -> tuple[float, float, float, float]:
    volatility_risk = min(100, volatility / 0.35 * 100)
    low_volume_risk = max(0, 100 - (stats.avg_daily_volume_30d / max(filters.minimum_daily_volume, 1) * 100))
    depth_floor = max(filters.minimum_daily_volume * 0.25, 1)
    low_depth_risk = max(0, 100 - (min(buy_depth_5_percent, sell_depth_5_percent) / depth_floor * 100))
    risk_score = manipulation * 0.35 + volatility_risk * 0.25 + low_volume_risk * 0.20 + low_depth_risk * 0.20
    return min(100, risk_score), volatility_risk, low_volume_risk, low_depth_risk


def evaluate_opportunity(
    book: OrderBook,
    metadata: ItemMetadata,
    stats: HistoryStats,
    filters: SafetyFilters,
    fees: FeeRates,
    liquid_isk: float,
) -> EvaluatedOpportunity | None:
    if not book.buy_orders or not book.sell_orders:
        return None
    if filters.safe_mode and is_hard_excluded(metadata, filters):
        return None
    if filters.safe_mode and not is_beginner_category_allowed(metadata):
        return None

    best_buy = book.best_buy
    best_sell = book.best_sell
    if best_buy <= 0 or best_sell <= best_buy:
        return None
    if best_buy < filters.minimum_price or best_sell > filters.maximum_required_isk_per_item:
        return None
    if book.order_count < filters.minimum_order_count:
        return None
    if book.buy_order_count < filters.minimum_buy_order_count or book.sell_order_count < filters.minimum_sell_order_count:
        return None

    recommended_buy = round(best_buy * 1.0001, 2)
    recommended_sell = round(best_sell * 0.9999, 2)
    conservative_sell = recommended_sell
    if stats.avg_price_7d > 0:
        conservative_sell = min(conservative_sell, stats.avg_price_7d * 1.10)

    fee_result = calculate_fees(recommended_buy, conservative_sell, fees)
    if fee_result.net_profit_per_unit <= 0:
        return None
    if fee_result.margin_percent < filters.minimum_margin_percent:
        return None
    if filters.safe_mode and fee_result.margin_percent > filters.maximum_margin_percent:
        return None

    buy_depth_5 = depth_within_percent(book.buy_orders, best_buy, 0.05, buy_side=True)
    sell_depth_5 = depth_within_percent(book.sell_orders, best_sell, 0.05, buy_side=False)
    quantity = suggested_quantity(stats, recommended_buy, liquid_isk, buy_depth_5, sell_depth_5, filters, fees)
    if quantity <= 0:
        return None
    if book.top_buy_quantity < quantity * 0.25 or book.top_sell_quantity < quantity * 0.25:
        return None
    if buy_depth_5 < quantity * 4 or sell_depth_5 < quantity * 4:
        return None

    required_isk = recommended_buy * (1 + fees.broker_fee_rate) * quantity
    total_profit = fee_result.net_profit_per_unit * quantity
    if total_profit < filters.minimum_estimated_profit:
        return None

    if filters.safe_mode:
        if stats.avg_daily_volume_30d < filters.minimum_daily_volume:
            return None
        if stats.days_traded_30d < 20:
            return None
        if stats.price_volatility_30d > 0.35:
            return None
        if stats.median_price_30d > 0:
            if best_sell > stats.median_price_30d * 1.25:
                return None
            if best_buy < stats.median_price_30d * 0.60:
                return None

    manipulation = manipulation_risk(
        metadata,
        stats,
        fee_result.margin_percent,
        best_buy,
        best_sell,
        book.buy_order_count,
        book.sell_order_count,
        book.top_buy_quantity,
        book.top_sell_quantity,
        filters,
    )
    risk_score_value, volatility_risk, low_volume_risk, low_depth_risk = _risk_components(
        manipulation,
        stats.price_volatility_30d,
        stats,
        buy_depth_5,
        sell_depth_5,
        filters,
    )
    risk = risk_label(risk_score_value)
    if filters.safe_mode and (manipulation >= 35 or risk not in {"Low", "Medium"}):
        return None

    margin_quality = 100 - abs(10 - fee_result.margin_percent) * 4
    volume_quality = min(100, stats.avg_daily_volume_30d / max(filters.minimum_daily_volume, 1) * 30)
    depth_quality = min(100, min(buy_depth_5, sell_depth_5) / max(quantity * 8, 1) * 100)
    stability_quality = max(0, 100 - volatility_risk)
    score = max(0, min(100, margin_quality * 0.30 + volume_quality * 0.25 + depth_quality * 0.25 + stability_quality * 0.20))

    reason = (
        f"This item is recommended because it has good 30-day volume, enough buy/sell orders, "
        f"and a moderate {fee_result.margin_percent:.1f}% net margin after estimated fees. "
        f"Avoid buying more than {quantity:,} units."
    )
    action = (
        f"Place a buy order near {recommended_buy:,.2f} ISK. "
        f"After it fills, sell near {recommended_sell:,.2f} ISK manually."
    )
    warning = "Do not buy instantly from sell orders unless the app specifically says instant flip is profitable."

    return EvaluatedOpportunity(
        type_id=book.type_id,
        item_name=metadata.name,
        category=metadata.group if metadata.group != "Unknown" else metadata.category,
        best_buy=best_buy,
        best_sell=best_sell,
        recommended_buy_price=recommended_buy,
        recommended_sell_price=recommended_sell,
        expected_buy_price=recommended_buy,
        expected_sell_price=conservative_sell,
        depth_buy_price=weighted_average_for_quantity(book.buy_orders, quantity),
        depth_sell_price=weighted_average_for_quantity(book.sell_orders, quantity),
        buy_order_count=book.buy_order_count,
        sell_order_count=book.sell_order_count,
        buy_depth_5_percent=buy_depth_5,
        sell_depth_5_percent=sell_depth_5,
        top_buy_quantity=book.top_buy_quantity,
        top_sell_quantity=book.top_sell_quantity,
        avg_daily_volume_30d=stats.avg_daily_volume_30d,
        median_daily_volume_30d=stats.median_daily_volume_30d,
        avg_price_30d=stats.avg_price_30d,
        median_price_30d=stats.median_price_30d,
        price_volatility_30d=stats.price_volatility_30d,
        days_traded_30d=stats.days_traded_30d,
        profit_per_unit=fee_result.net_profit_per_unit,
        total_expected_profit=total_profit,
        required_isk=required_isk,
        break_even_sell_price=fee_result.break_even_sell_price,
        net_margin_percent=fee_result.margin_percent,
        roi_percent=fee_result.margin_percent,
        suggested_quantity=quantity,
        manipulation_risk_score=manipulation,
        risk_score=risk_score_value,
        risk=risk,
        score=score,
        reason=reason,
        action=action,
        warning=warning,
    )
