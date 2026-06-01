import type { ReactNode } from "react";

export function Section({
  title,
  description,
  action,
  error,
  className,
  children
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  error?: string | null;
  className?: string;
  children: ReactNode;
}) {
  const classes = ["section", className].filter(Boolean).join(" ");

  return (
    <section className={classes}>
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {action && <div className="section-action">{action}</div>}
      </div>
      {error && <p className="error">{error}</p>}
      {children}
    </section>
  );
}

export function TableWrap({ children }: { children: ReactNode }) {
  return <div className="table-wrap">{children}</div>;
}
