import { StatusChip } from "@nyxon/nasim";
import { t } from "@/strings";
import type { Health } from "../lib/matrix";

const TONES = { ok: "success", degraded: "warning", down: "danger", unknown: "neutral" } as const;
const LABELS: Record<Health, string> = {
	ok: t.pingMatrix.ok,
	degraded: t.pingMatrix.degraded,
	down: t.pingMatrix.down,
	unknown: t.pingMatrix.unknown,
};

/** A link's health as a word on a tinted chip. */
export function HealthChip({ health }: { health: Health }) {
	return <StatusChip tone={TONES[health]} label={LABELS[health]} size="sm" />;
}
