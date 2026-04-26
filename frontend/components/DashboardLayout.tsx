import Link from "next/link";
import type { ReactNode } from "react";

type DashboardLayoutProps = {
  children: ReactNode;
};

const navLinks = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/backtest", label: "Backtest" },
  { href: "/settings", label: "Settings" },
];

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl">
        <aside className="hidden w-64 shrink-0 border-r border-slate-800/80 bg-slate-900/40 p-6 lg:block">
          <Link href="/" className="mb-8 block">
            <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">Trade-X</div>
            <div className="mt-2 text-xl font-semibold text-white">Paper Trading</div>
          </Link>
          <nav className="space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="block rounded-lg border border-transparent px-3 py-2 text-sm text-slate-300 transition hover:border-slate-700 hover:bg-slate-800/70 hover:text-white"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </aside>
        <main className="flex min-h-screen min-w-0 flex-1 flex-col">{children}</main>
      </div>
    </div>
  );
}