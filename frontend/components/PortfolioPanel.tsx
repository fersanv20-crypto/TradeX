export default function PortfolioPanel() {
  const rows = [
    { asset: "USDT", amount: "9,415.28", value: "$9,415.28" },
    { asset: "BTC", amount: "0.1420", value: "$954.18" },
    { asset: "PnL (24h)", amount: "+2.7%", value: "+$253.90" },
  ];

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-lg font-semibold text-white">Portfolio Snapshot</h2>
      <div className="mt-4 space-y-3">
        {rows.map((row) => (
          <div
            key={row.asset}
            className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3"
          >
            <div>
              <div className="text-sm font-medium text-slate-100">{row.asset}</div>
              <div className="text-xs text-slate-400">{row.amount}</div>
            </div>
            <div className="text-sm font-medium text-cyan-300">{row.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}