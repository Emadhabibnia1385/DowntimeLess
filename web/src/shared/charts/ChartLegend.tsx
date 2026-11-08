import { Button } from "@nyxon/nasim";
import { type ChartSeries, TONE_TEXT } from "./types";

// One chip per series: pressed shows it, and the last one shown cannot be hidden.
export function ChartLegend({
	label,
	series,
	hidden,
	onToggle,
}: {
	label: string;
	series: readonly ChartSeries[];
	hidden: ReadonlySet<string>;
	onToggle: (key: string) => void;
}) {
	return (
		<fieldset
			aria-label={label}
			className="m-0 flex min-w-0 flex-wrap items-center gap-2 border-0 p-0"
		>
			{series.map((item) => {
				const on = !hidden.has(item.key);
				return (
					<Button
						key={item.key}
						size="sm"
						variant={on ? "secondary" : "outline"}
						aria-pressed={on}
						onPress={() => onToggle(item.key)}
						className={on ? undefined : "text-muted"}
					>
						<span
							aria-hidden
							className={`size-2.5 shrink-0 rounded-full border-2 border-current ${TONE_TEXT[item.tone]} ${
								on ? "bg-current" : "bg-transparent"
							}`}
						/>
						{item.label}
					</Button>
				);
			})}
		</fieldset>
	);
}
