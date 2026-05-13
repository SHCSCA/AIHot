import type { ReactNode } from "react";

export function Section({
  title,
  description,
  action,
  error,
  children
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {action}
      </div>
      {error && <p className="error">{error}</p>}
      {children}
    </section>
  );
}

export function TableWrap({ children }: { children: ReactNode }) {
  return <div className="table-wrap">{children}</div>;
}
