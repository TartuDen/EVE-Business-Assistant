import React from "react";
import { Factory } from "lucide-react";

export function Manufacturing() {
  return (
    <section className="rounded-lg border border-line bg-panel p-5">
      <div className="flex items-center gap-2">
        <Factory className="text-cyan" size={20} />
        <h2 className="text-lg font-semibold text-white">Manufacturing</h2>
      </div>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
        Planned after the trading MVP: blueprint inputs, material shopping lists, facility tax, production time, sell price, market volume, and a build/do-not-build recommendation.
      </p>
    </section>
  );
}
