import { PlayCircle } from "lucide-react";
import { formatIsk } from "../lib/api.js";
import { StatCard } from "../components/StatCard.jsx";
import { RiskBadge } from "../components/RiskBadge.jsx";

export function Dashboard({ stats, portfolio, onScan }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <StatCard label="Total ISK" value={`${formatIsk(stats.totalIsk, true)} ISK`} />
        <StatCard label="Invested ISK" value={`${formatIsk(stats.invested, true)} ISK`} />
        <StatCard label="Open Orders" value={stats.openOrders} />
        <StatCard label="Realized Profit" value={`${formatIsk(stats.realized, true)} ISK`} />
        <StatCard
          label="Best Opportunity Today"
          value={stats.bestOpportunity?.item_name ?? "Run scan"}
          detail={stats.bestOpportunity ? `${formatIsk(stats.bestOpportunity.expected_profit, true)} ISK expected` : ""}
        />
        <StatCard label="Risk Level" value={stats.bestOpportunity ? <RiskBadge risk={stats.bestOpportunity.risk} /> : "None"} />
      </section>

      <section className="flex flex-col gap-4 border-y border-line py-6 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Jita trade scanner</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Find public-market station trading ideas, then place any orders manually in EVE. The app estimates fees, volume, quantity, and risk before showing a recommendation.
          </p>
        </div>
        <button
          onClick={onScan}
          className="inline-flex items-center justify-center gap-2 rounded-md bg-cyan px-5 py-3 font-semibold text-hull hover:bg-cyan/90"
        >
          <PlayCircle size={20} />
          Scan Market
        </button>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-line bg-panel p-4">
          <h3 className="text-base font-semibold text-white">Portfolio snapshot</h3>
          <div className="mt-4 space-y-3 text-sm text-slate-300">
            <Row label="ROI" value={`${(portfolio?.roi_percent ?? 0).toFixed(2)}%`} />
            <Row label="Best item" value={portfolio?.best_item ?? "No closed trades"} />
            <Row label="Worst item" value={portfolio?.worst_item ?? "No closed trades"} />
          </div>
        </div>
        <div className="rounded-lg border border-line bg-panel p-4">
          <h3 className="text-base font-semibold text-white">Safety rule</h3>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            This app never clicks, controls, injects into, or automates the EVE client. It only turns public data and your manual entries into readable recommendations.
          </p>
        </div>
      </section>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-slate-400">{label}</span>
      <span className="text-right font-medium text-slate-100">{value}</span>
    </div>
  );
}
