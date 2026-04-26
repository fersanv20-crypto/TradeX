export default function DashboardAtAGlance() {
  const stats = [
    { label: "24h Volume", value: "$1.2M", tone: "text-cyan-300" },
    { label: "Win Rate", value: "61.8%", tone: "text-emerald-300" },
    { label: "Open Orders", value: "4", tone: "text-slate-200" },
    { label: "Bot Risk", value: "Medium", tone: "text-amber-300" },
  ];

  return (
    <section className="mx-auto mt-6 grid w-full max-w-6xl gap-4 px-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-4 lg:px-8">
      {stats.map((stat) => (
        <article key={stat.label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">{stat.label}</div>
          <div className={`mt-2 text-2xl font-semibold ${stat.tone}`}>{stat.value}</div>
        </article>
      ))}
    </section>
  );
}