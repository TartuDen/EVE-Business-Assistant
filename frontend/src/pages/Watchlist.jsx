import { Eye } from "lucide-react";
import { RiskBadge } from "../components/RiskBadge.jsx";
import { formatIsk } from "../lib/api.js";

export function Watchlist({ opportunities }) {
  const watched = opportunities.slice(0, 10);
  return (
    <section className="rounded-lg border border-line bg-panel p-5">
      <div className="flex items-center gap-2">
        <Eye className="text-cyan" size={20} />
        <h2 className="text-lg font-semibold text-white">Watchlist</h2>
      </div>
      <p className="mt-2 text-sm text-slate-400">
        The current MVP uses your latest scan as a temporary watchlist. Persistent watchlists can be added next.
      </p>

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {watched.map((item) => (
          <article key={item.type_id} className="rounded-lg border border-line bg-hull p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-white">{item.item_name}</h3>
                <p className="mt-1 text-sm text-slate-400">{formatIsk(item.expected_profit, true)} ISK expected profit</p>
              </div>
              <RiskBadge risk={item.risk} />
            </div>
          </article>
        ))}
      </div>

      {!watched.length ? <div className="mt-8 text-sm text-slate-400">Run a market scan to populate the watchlist.</div> : null}
    </section>
  );
}
