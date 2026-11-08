import { CheckIcon, CloseIcon } from "@/shared/icons";
import { t } from "@/strings";

// The tick of an up-to-date agent, or the cross of an old one, with its meaning for screen readers.
export function AgentVersionMark({ outdated }: { outdated: boolean }) {
	const label = outdated ? t.servers.updateNeeded : t.servers.upToDate;
	const Icon = outdated ? CloseIcon : CheckIcon;
	return (
		<span title={label} className={`inline-flex ${outdated ? "text-danger" : "text-success"}`}>
			<Icon aria-hidden className="size-4" />
			<span className="sr-only">{label}</span>
		</span>
	);
}
