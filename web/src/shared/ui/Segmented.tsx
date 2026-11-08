import { Tabs } from "@nyxon/nasim";

type Option<T extends string> = { value: T; label: string };

// Track of segments sharing the room, one chosen; `\_` because Tailwind reads `_` as a space.
const TRACK = [
	String.raw`[&_.tabs\_\_list-container]:rounded-2xl [&_.tabs\_\_list-container]:bg-surface-secondary`,
	String.raw`[&_.tabs\_\_list]:gap-1 [&_.tabs\_\_list]:p-1`,
	String.raw`[&_.tabs\_\_tab]:h-10 [&_.tabs\_\_tab]:flex-auto [&_.tabs\_\_tab]:whitespace-nowrap`,
	String.raw`[&_.tabs\_\_tab]:rounded-xl [&_.tabs\_\_tab]:px-2 [&_.tabs\_\_tab]:text-sm`,
	String.raw`[&_.tabs\_\_tab[data-selected=true]]:font-semibold`,
	String.raw`[&_.tabs\_\_tab[data-selected=true]]:text-accent-soft-foreground`,
	String.raw`[&_.tabs\_\_indicator]:rounded-xl [&_.tabs\_\_indicator]:bg-accent-soft`,
	String.raw`[&_.tabs\_\_indicator]:shadow-none [&_.tabs\_\_indicator]:ring-1`,
	String.raw`[&_.tabs\_\_indicator]:ring-inset [&_.tabs\_\_indicator]:ring-accent/35`,
].join(" ");

// Compact replacement for wrapping filter chips: tablist semantics, arrows follow the reading side.
export function Segmented<T extends string>({
	label,
	value,
	onChange,
	options,
	className,
}: {
	/** Names the group for assistive technology. */
	label: string;
	value: T;
	onChange: (value: T) => void;
	options: readonly Option<T>[];
	className?: string;
}) {
	return (
		<Tabs
			label={label}
			selectedKey={value}
			onSelectionChange={(id) => {
				const next = options.find((option) => option.value === id);
				if (next) onChange(next.value);
			}}
			items={options.map((option) => ({ id: option.value, label: option.label }))}
			className={className ? `${TRACK} ${className}` : TRACK}
		/>
	);
}
