import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow?: string;
  title?: string;
  description?: string;
  action?: ReactNode;
};

export default function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: PageHeaderProps) {
  return (
    <div className="border-b border-slate-800/80 bg-slate-900/50 px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          {eyebrow && (
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">
              {eyebrow}
            </div>
          )}
          {title && <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>}
          {description && <p className="max-w-3xl text-sm text-slate-300">{description}</p>}
        </div>
        {action && <div className="w-full lg:w-auto">{action}</div>}
      </div>
    </div>
  );
}