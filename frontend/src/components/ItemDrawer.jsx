import React from "react";
import { X } from "lucide-react";
import { formatIsk } from "../lib/api.js";
import { RiskBadge } from "./RiskBadge.jsx";

export function ItemDrawer({ item, onClose }) {
  if (!item) return null;

  return (
    <aside className="fixed inset-y-0 right-0 z-30 w-full max-w-xl border-l border-line bg-hull shadow-2xl">
      <div className="flex h-full flex-col">
        <header className="flex items-start justify-between border-b border-line px-5 py-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-cyan">Opportunity detail</div>
            <h2 className="mt-1 text-xl font-semibold text-white">{item.item_name}</h2>
          </div>
          <button
            className="rounded-md border border-line p-2 text-slate-300 hover:border-cyan hover:text-cyan"
            onClick={onClose}
            title="Close"
          >
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5 scrollbar-thin">
          <div className="flex items-center gap-3">
            <RiskBadge risk={item.risk} />
            <span className="text-sm text-slate-400">Score {item.score}/100</span>
          </div>

          <p className="text-sm leading-6 text-slate-300">{item.reason}</p>

          <section className="grid grid-cols-2 gap-3">
            <Metric label="Buy around" value={`${formatIsk(item.recommended_buy_price)} ISK`} />
            <Metric label="Sell around" value={`${formatIsk(item.recommended_sell_price)} ISK`} />
            <Metric label="30d avg volume" value={formatIsk(item.avg_daily_volume_30d)} />
            <Metric label="30d median price" value={`${formatIsk(item.median_price_30d)} ISK`} />
            <Metric label="Net margin" value={`${item.net_margin_percent.toFixed(2)}%`} />
            <Metric label="Profit per unit" value={`${formatIsk(item.profit_per_unit)} ISK`} />
            <Metric label="Required ISK" value={`${formatIsk(item.required_isk, true)} ISK`} />
            <Metric label="Expected profit" value={`${formatIsk(item.expected_profit, true)} ISK`} />
            <Metric label="Break-even sell" value={`${formatIsk(item.break_even_sell_price)} ISK`} />
            <Metric label="Manipulation risk" value={`${item.manipulation_risk_score.toFixed(1)}/100`} />
          </section>

          <section className="grid grid-cols-2 gap-3">
            <Metric label="Buy orders" value={formatIsk(item.buy_order_count)} />
            <Metric label="Sell orders" value={formatIsk(item.sell_order_count)} />
            <Metric label="Buy depth within 5%" value={formatIsk(item.buy_depth_5_percent)} />
            <Metric label="Sell depth within 5%" value={formatIsk(item.sell_depth_5_percent)} />
            <Metric label="Top buy quantity" value={formatIsk(item.top_buy_quantity)} />
            <Metric label="Top sell quantity" value={formatIsk(item.top_sell_quantity)} />
            <Metric label="Depth buy price" value={`${formatIsk(item.depth_buy_price)} ISK`} />
            <Metric label="Depth sell price" value={`${formatIsk(item.depth_sell_price)} ISK`} />
            <Metric label="Days traded" value={`${item.days_traded_30d}/30`} />
            <Metric label="Volatility" value={`${(item.price_volatility_30d * 100).toFixed(1)}%`} />
          </section>

          <section className="rounded-lg border border-cyan/30 bg-cyan/8 p-4">
            <div className="text-xs uppercase tracking-wide text-cyan">Manual action</div>
            <p className="mt-2 text-sm leading-6 text-slate-100">{item.action}</p>
          </section>

          <section className="rounded-lg border border-line bg-panel p-4">
            <div className="text-xs uppercase tracking-wide text-slate-400">Warning</div>
            <p className="mt-2 text-sm leading-6 text-slate-300">{item.warning}</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Prices can move before your order fills. Keep the quantity near the suggestion, check the order book in game, and avoid chasing fast reprices.
            </p>
          </section>
        </div>
      </div>
    </aside>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-semibold text-white">{value}</div>
    </div>
  );
}
