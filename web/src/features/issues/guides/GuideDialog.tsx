import { Modal, SkeletonRows } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { useGuide } from "./api";
import { GuideBody } from "./GuideBody";

export type GuideTarget = { code: string; title: string };

// The issue's own title heads the dialog at once; the guide's title replaces it when it arrives.
export function GuideDialog({
	target,
	onClose,
}: {
	target: GuideTarget | null;
	onClose: () => void;
}) {
	const guide = useGuide(target?.code ?? null);
	const title = guide.data?.guide_fa?.title ?? target?.title ?? "";
	return (
		<Modal
			isOpen={target !== null}
			onOpenChange={(open) => !open && onClose()}
			title={title}
			size="lg"
		>
			<Loadable query={guide} skeleton={<SkeletonRows />}>
				{(data) =>
					data.guide_fa ? (
						<GuideBody guide={data.guide_fa} generic={data.guide_fa.code === "generic"} />
					) : null
				}
			</Loadable>
		</Modal>
	);
}
