/**
 * Mirrors `format_cost()` in `backend/app/services/llm_usage_service.py` — a raw
 * per-call cost is routinely $0.001-$0.00001, and rounding to 2dp would print $0.00 for
 * every row. Shared by every LLM-usage component so a precision change only has one
 * place to land instead of drifting across copies.
 */
export function formatCost(cost: number | null | undefined): string {
  if (cost === null || cost === undefined) return "—";
  if (cost === 0) return "$0.00";
  if (Math.abs(cost) < 0.01) return `$${cost.toFixed(6)}`;
  if (Math.abs(cost) < 1) return `$${cost.toFixed(4)}`;
  return `$${cost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
