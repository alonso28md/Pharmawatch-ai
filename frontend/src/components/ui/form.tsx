import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes, useId } from "react";
import { cn } from "@/lib/utils";

const control =
  "w-full rounded-md border border-line-strong bg-surface text-body text-ink placeholder:text-ink-subtle " +
  "transition-[border-color] duration-[140ms] hover:border-ink-subtle " +
  "aria-[invalid=true]:border-critical disabled:opacity-60";

/** Label above the control, help and error text linked through aria-describedby. */
export function Field({
  label,
  help,
  error,
  counter,
  children,
}: {
  label: ReactNode;
  help?: ReactNode;
  error?: ReactNode;
  counter?: ReactNode;
  children: (ids: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
}) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-body font-medium text-ink">
          {label}
        </label>
        {counter && <span className="tabular text-caption text-ink-subtle">{counter}</span>}
      </div>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {help && (
        <p id={helpId} className="text-small text-ink-muted">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-small font-medium text-critical">
          {error}
        </p>
      )}
    </div>
  );
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn(control, "min-h-36 resize-y px-3 py-2.5 leading-[22px]", className)} {...props} />
  ),
);
Textarea.displayName = "Textarea";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(control, "h-10 px-3", className)} {...props} />,
);
Input.displayName = "Input";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select ref={ref} className={cn(control, "h-10 bg-surface px-3 text-ink", className)} {...props} />
  ),
);
Select.displayName = "Select";
