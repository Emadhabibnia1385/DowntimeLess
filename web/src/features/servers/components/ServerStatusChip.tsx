import { StatusChip } from "@nyxon/nasim";
import { statusLabel, statusTone } from "../lib/status";

export function ServerStatusChip({ status, size = "sm" }: { status: string; size?: "sm" | "md" }) {
	return <StatusChip tone={statusTone(status)} label={statusLabel(status)} size={size} />;
}
