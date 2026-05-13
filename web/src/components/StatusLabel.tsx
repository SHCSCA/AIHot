import { statusLabel } from "../labels";

export function StatusLabel({ value }: { value: string }) {
  return <span className={`status status-${value}`}>{statusLabel(value)}</span>;
}
