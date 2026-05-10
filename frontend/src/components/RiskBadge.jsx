import React from "react";

export function RiskBadge({ risk }) {
  const classes = {
    Low: "border-mint/40 bg-mint/12 text-mint",
    Medium: "border-amber/40 bg-amber/12 text-amber",
    High: "border-danger/40 bg-danger/12 text-danger",
  };
  return (
    <span className={`inline-flex min-w-16 justify-center rounded border px-2 py-1 text-xs font-semibold ${classes[risk] ?? classes.High}`}>
      {risk}
    </span>
  );
}
