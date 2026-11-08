import { Button, Modal } from "@nyxon/nasim";
import { useState } from "react";
import { InstallIcon } from "@/shared/icons";
import { t } from "@/strings";
import { promptInstall, useInstallState } from "../pwa/installPrompt";

// The browser's install prompt, or the Share-sheet steps on iOS; gone once installed.
export function InstallButton() {
	const state = useInstallState();
	const [help, setHelp] = useState(false);
	const steps = t.pwa.iosSteps;
	if (state === "installed" || state === "none") return null;
	return (
		<>
			<Button
				variant="secondary"
				fullWidth
				onPress={() => (state === "prompt" ? void promptInstall() : setHelp(true))}
			>
				<InstallIcon aria-hidden />
				{t.pwa.install}
			</Button>
			<Modal
				isOpen={help}
				onOpenChange={setHelp}
				title={t.pwa.iosTitle}
				size="xs"
				footer={<Button onPress={() => setHelp(false)}>{t.pwa.iosClose}</Button>}
			>
				<p className="mb-3 text-sm text-muted">{t.pwa.iosLead}</p>
				<ol className="flex list-decimal flex-col gap-2 ps-5 text-sm">
					{steps.map((step) => (
						<li key={step}>{step}</li>
					))}
				</ol>
			</Modal>
		</>
	);
}
