import type { ServerOut } from "@/api/generated/model";
import { t } from "@/strings";

export type Tone = "success" | "danger" | "neutral";

const TONES: Record<string, Tone> = { online: "success", offline: "danger" };

export const statusTone = (status: string): Tone => TONES[status] ?? "neutral";

const LABELS: Record<string, string> = {
	online: t.status.online,
	offline: t.status.offline,
	pending: t.status.pending,
};

export const statusLabel = (status: string): string => LABELS[status] ?? t.common.unknown;

const ROLES: Record<string, string> = t.roles;

export const roleLabel = (role: string): string => ROLES[role] ?? role;

/** The name people use for a server: its alias when it has one. */
export const displayName = (server: Pick<ServerOut, "alias" | "name">): string =>
	server.alias || server.name;
