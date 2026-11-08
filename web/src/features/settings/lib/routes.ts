import type { ChannelOut } from "@/api/generated/model";
import { t } from "@/strings";
import type { RuleId } from "./rules";

export const PANEL_ROUTE = "panel";
export const ADMINS_ROUTE = "admins";

/** Form field that holds the destination of one alert. */
export const ROUTE_PREFIX = "route_";
export const routeKey = (id: RuleId) => `${ROUTE_PREFIX}${id}`;

export const channelRoute = (channel: Pick<ChannelOut, "id">) => `channel:${channel.id}`;

/** Where an alert can go: the panel only, the admins' private chats, or one of the channels. */
export function routeOptions(channels: readonly ChannelOut[]) {
	return [
		{ value: PANEL_ROUTE, label: t.notifications.routePanel },
		{ value: ADMINS_ROUTE, label: t.notifications.routeAdmins },
		...channels.map((channel) => ({ value: channelRoute(channel), label: channel.name })),
	];
}

/** The form's route fields as the API's rule-to-route map. */
export function toRoutes(values: Record<string, unknown>): Record<string, string> {
	return Object.fromEntries(
		Object.entries(values)
			.filter(([key]) => key.startsWith(ROUTE_PREFIX))
			.map(([key, value]) => [key.slice(ROUTE_PREFIX.length), String(value)]),
	);
}
