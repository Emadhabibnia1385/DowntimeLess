import { KeyValueList, SectionCard } from "@nyxon/nasim";
import type { ServerOut } from "@/api/generated/model";
import { IpText } from "@/shared/IpText";
import { formatDateTime, formatDuration, t } from "@/strings";

// The record of one server: where it is, what runs on it, when it last spoke.
export function ServerInfo({ server }: { server: ServerOut }) {
	const place = [server.country, server.city].filter(Boolean).join(", ");
	return (
		<SectionCard title={t.server.details}>
			<KeyValueList
				layout="grid"
				items={[
					{
						label: t.server.ip,
						value: server.public_ip ? <IpText ip={server.public_ip} /> : t.common.none,
					},
					{ label: t.server.location, value: place || t.common.none, ltr: true },
					{ label: t.server.org, value: server.org ?? t.common.none, ltr: true },
					{ label: t.server.hostname, value: server.hostname ?? t.common.none, ltr: true },
					{ label: t.server.agentVersion, value: server.agent_version ?? t.common.none, ltr: true },
					{
						label: t.server.lastSeen,
						value: server.last_seen ? formatDateTime(server.last_seen) : t.servers.neverSeen,
					},
					server.latest.uptime_s != null && {
						label: t.server.uptime,
						value: formatDuration(server.latest.uptime_s),
					},
				]}
			/>
		</SectionCard>
	);
}
