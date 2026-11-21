"use client";

import { useEffect, useId, useRef, type ComponentProps, type ReactNode } from "react";

function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

const BUTTON = {
  primary: "bg-emerald-700 text-white hover:bg-emerald-800 disabled:bg-emerald-700/60",
  secondary: "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-50 disabled:text-zinc-400",
  danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/60",
  ghost: "text-zinc-700 hover:bg-zinc-100",
} as const;

export function Button({
  variant = "primary",
  busy = false,
  className,
  children,
  disabled,
  type = "button",
  ...props
}: ComponentProps<"button"> & { variant?: keyof typeof BUTTON; busy?: boolean }) {
  return (
    <button
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:cursor-not-allowed",
        BUTTON[variant],
        className,
      )}
      {...props}
    >
      {busy ? "Aguarde…" : children}
    </button>
  );
}

const CONTROL =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 " +
  "focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/20 " +
  "aria-[invalid=true]:border-red-500 disabled:bg-zinc-100";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cx(CONTROL, className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cx(CONTROL, className)} {...props} />;
}

export type FieldProps = { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string };

/** A label, a control and its message, wired for screen readers. */
export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: (props: FieldProps) => ReactNode;
}) {
  const id = useId();
  const messageId = `${id}-message`;
  const message = error ?? hint;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-zinc-700">
        {label}
      </label>
      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": message ? messageId : undefined,
      })}
      {message && (
        <p id={messageId} className={cx("text-xs", error ? "text-red-600" : "text-zinc-500")}>
          {message}
        </p>
      )}
    </div>
  );
}

export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div className={cx("rounded-xl border border-zinc-200 bg-white p-5 shadow-xs", className)} {...props} />
  );
}

export function Alert({ children, tone = "error" }: { children: ReactNode; tone?: "error" | "info" }) {
  if (!children) return null;
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={cx(
        "rounded-lg px-3 py-2 text-sm",
        tone === "error" ? "bg-red-50 text-red-800" : "bg-emerald-50 text-emerald-900",
      )}
    >
      {children}
    </p>
  );
}

export function Badge({
  children,
  tone = "zinc",
}: {
  children: ReactNode;
  tone?: "zinc" | "amber" | "emerald" | "red";
}) {
  const tones = {
    zinc: "bg-zinc-100 text-zinc-700",
    amber: "bg-amber-100 text-amber-800",
    emerald: "bg-emerald-100 text-emerald-800",
    red: "bg-red-100 text-red-800",
  };
  return <span className={cx("rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-zinc-600">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/** A modal on the native <dialog>: focus trap, Esc and the backdrop come from the browser. */
export function Dialog({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      // showModal focuses the first focusable element, the close button; start at the form instead.
      dialog.querySelector<HTMLElement>("[data-autofocus], input, select, textarea")?.focus();
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={`${title}-title`}
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-xl p-0 shadow-xl backdrop:bg-zinc-900/40"
    >
      {open && (
        <div className="p-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <h2 id={`${title}-title`} className="text-lg font-semibold text-zinc-900">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-zinc-500 hover:text-zinc-800"
              aria-label="Fechar"
            >
              ✕
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

export function Loading({ label = "Carregando…" }: { label?: string }) {
  return (
    <p role="status" className="py-8 text-center text-sm text-zinc-500">
      {label}
    </p>
  );
}

export function formValues(form: HTMLFormElement): Record<string, string> {
  return Object.fromEntries(
    [...new FormData(form).entries()].map(([key, value]) => [key, typeof value === "string" ? value : ""]),
  );
}
