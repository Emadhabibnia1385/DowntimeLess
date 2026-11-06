import { PageHeader, SectionCard } from "@nyxon/nasim";
import { useSettingsGet } from "@/api/generated/settings/settings";
import { useCanManage } from "@/features/auth";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { DEFAULT_THRESHOLDS } from "../api";
import { ThresholdsForm } from "./ThresholdsForm";

export function SettingsPage() {
	useDocumentTitle(t.settings.title);
	const settings = useSettingsGet();
	const canManage = useCanManage();
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.settings.title} description={t.settings.subtitle} />
			<SectionCard title={t.settings.thresholds}>
				<Loadable query={settings}>
					{(values) => (
						<ThresholdsForm values={{ ...DEFAULT_THRESHOLDS, ...values }} canManage={canManage} />
					)}
				</Loadable>
			</SectionCard>
		</div>
	);
}
