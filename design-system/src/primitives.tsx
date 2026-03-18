import clsx from "clsx";
import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

interface DsContainerProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

interface DsPanelProps extends HTMLAttributes<HTMLElement> {
  kicker?: string;
  title?: string;
  description?: string;
  actions?: ReactNode;
  strong?: boolean;
}

interface DsHeroProps {
  kicker: string;
  title: string;
  description: string;
  actions?: ReactNode;
  meta?: ReactNode;
}

interface DsButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger";
  size?: "md" | "sm";
}

interface DsChipProps extends HTMLAttributes<HTMLSpanElement> {
  active?: boolean;
  soft?: boolean;
}

interface DsStatCardProps {
  label: string;
  value: string;
  meta?: string;
}

interface DsFieldProps extends HTMLAttributes<HTMLLabelElement> {
  label: string;
  full?: boolean;
  hint?: string;
  children: ReactNode;
}

export function DsTheme({ children, className, ...props }: DsContainerProps) {
  return (
    <div {...props} className={clsx("ds-theme", className)}>
      {children}
    </div>
  );
}

export function DsStage({ children, className, ...props }: DsContainerProps) {
  return (
    <div {...props} className={clsx("ds-stage", className)}>
      {children}
    </div>
  );
}

export function DsStack({ children, className, ...props }: DsContainerProps) {
  return (
    <div {...props} className={clsx("ds-stack", className)}>
      {children}
    </div>
  );
}

export function DsHero({ actions, description, kicker, meta, title }: DsHeroProps) {
  return (
    <section className="ds-panel ds-hero">
      <div className="ds-panel__content">
        <div>
          <p className="ds-kicker">{kicker}</p>
          <h2>{title}</h2>
        </div>
        <p className="ds-copy">{description}</p>
        {actions ? <div className="ds-inline-actions">{actions}</div> : null}
      </div>
      {meta ? <div className="ds-hero__meta">{meta}</div> : null}
    </section>
  );
}

export function DsPanel({
  actions,
  children,
  className,
  description,
  kicker,
  strong = false,
  title,
  ...props
}: DsPanelProps) {
  return (
    <section {...props} className={clsx("ds-panel", strong && "ds-panel--strong", className)}>
      {kicker || title || actions ? (
        <div className="ds-panel__header">
          <div>
            {kicker ? <p className="ds-kicker">{kicker}</p> : null}
            {title ? <h3>{title}</h3> : null}
            {description ? <p className="ds-copy ds-copy--tight">{description}</p> : null}
          </div>
          {actions}
        </div>
      ) : null}
      <div className="ds-panel__content">{children}</div>
    </section>
  );
}

export function DsButton({
  children,
  className,
  size = "md",
  type = "button",
  variant = "ghost",
  ...props
}: DsButtonProps) {
  return (
    <button
      {...props}
      type={type}
      className={clsx("ds-button", `ds-button--${variant}`, size === "sm" && "ds-button--sm", className)}
    >
      {children}
    </button>
  );
}

export function DsChip({ active = false, children, className, soft = false, ...props }: DsChipProps) {
  return (
    <span
      {...props}
      className={clsx("ds-chip", active && "ds-chip--active", soft && "ds-chip--soft", className)}
    >
      {children}
    </span>
  );
}

export function DsStatCard({ label, meta, value }: DsStatCardProps) {
  return (
    <article className="ds-stat-card">
      <p>{label}</p>
      <strong className="ds-value">{value}</strong>
      {meta ? <span>{meta}</span> : null}
    </article>
  );
}

export function DsField({ children, className, full = false, hint, label, ...props }: DsFieldProps) {
  return (
    <label {...props} className={clsx("ds-field", full && "ds-field--full", className)}>
      <span>{label}</span>
      {children}
      {hint ? <span className="ds-caption">{hint}</span> : null}
    </label>
  );
}

export function DsInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx("ds-input", props.className)} />;
}

export function DsSelect(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={clsx("ds-select", props.className)} />;
}

export function DsTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={clsx("ds-textarea", props.className)} />;
}

export function DsCodeBlock({ children }: { children: string }) {
  return <pre className="ds-code">{children}</pre>;
}
