import { Button } from "@nyxon/nasim";
import { useState } from "react";
import { GuideIcon } from "@/shared/icons";
import { t } from "@/strings";
import { GuideDialog, type GuideTarget } from "./GuideDialog";

// Everyone who sees an issue may read its guide: it only shows text and commands to copy.
export function GuideButton({ target }: { target: GuideTarget }) {
	const [open, setOpen] = useState(false);
	return (
		<>
			<Button
				size="sm"
				variant="secondary"
				aria-label={t.issueGuides.actionFor(target.title)}
				onPress={() => setOpen(true)}
			>
				<GuideIcon aria-hidden />
				{t.issueGuides.action}
			</Button>
			<GuideDialog target={open ? target : null} onClose={() => setOpen(false)} />
		</>
	);
}
