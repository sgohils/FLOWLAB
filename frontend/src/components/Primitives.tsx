import type { ReactNode } from "react";

export function Section({
  title,
  subtitle,
  actions,
  children,
  ...rest
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  "data-testid"?: string;
  [key: `data-${string}`]: string | undefined;
}) {
  return (
    <section className="mb-10" {...rest}>
      <div className="mb-3 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-faint">
            {title}
          </h2>
          {subtitle && <p className="mt-1 text-[13px] text-ink-soft">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-md border border-rule bg-surface ${className}`}>{children}</div>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return (
    <span className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-faint">
      {children}
    </span>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "caution" | "error" | "success";
  title?: string;
  children: ReactNode;
}) {
  const tones = {
    info: "border-rule bg-surface text-ink-soft",
    caution: "border-caution/30 bg-caution-soft text-caution",
    error: "border-red-300 bg-red-50 text-red-800",
    success: "border-positive/30 bg-positive-soft text-positive",
  } as const;
  return (
    <div className={`rounded-md border px-4 py-3 text-[13px] leading-relaxed ${tones[tone]}`}>
      {title && <p className="mb-1 font-medium">{title}</p>}
      {children}
    </div>
  );
}

export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "caution" | "positive";
}) {
  const tones = {
    neutral: "border-rule text-ink-faint",
    accent: "border-accent/30 bg-accent-soft text-accent",
    caution: "border-caution/30 bg-caution-soft text-caution",
    positive: "border-positive/30 bg-positive-soft text-positive",
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  type = "button",
  disabled = false,
  className = "",
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost";
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
  title?: string;
}) {
  const variants = {
    primary:
      "bg-ink text-paper border-ink hover:bg-ink-soft disabled:bg-ink-faint disabled:border-ink-faint",
    secondary:
      "bg-surface text-ink border-rule hover:border-ink-faint disabled:text-ink-faint",
    ghost: "bg-transparent text-ink-soft border-transparent hover:text-ink",
  } as const;
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded border px-4 py-2 text-[13px] font-medium transition-colors disabled:cursor-not-allowed ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
