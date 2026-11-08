import { Button, Tooltip } from "@nyxon/nasim";
import { ChartIcon, DownloadIcon, TableIcon } from "@/shared/icons";
import { t } from "@/strings";

// Icon buttons at the end of the legend row: chart or table, and the CSV download.
export function ChartToolbar({
	showTable,
	onToggleView,
	onDownload,
}: {
	showTable: boolean;
	onToggleView: () => void;
	onDownload: () => void;
}) {
	const viewLabel = showTable ? t.chart.showChart : t.chart.showTable;
	return (
		<div className="flex items-center gap-1">
			<Tooltip>
				<Button isIconOnly size="sm" variant="ghost" aria-label={viewLabel} onPress={onToggleView}>
					{showTable ? <ChartIcon aria-hidden /> : <TableIcon aria-hidden />}
				</Button>
				<Tooltip.Content>{viewLabel}</Tooltip.Content>
			</Tooltip>
			<Tooltip>
				<Button
					isIconOnly
					size="sm"
					variant="ghost"
					aria-label={t.chart.download}
					onPress={onDownload}
				>
					<DownloadIcon aria-hidden />
				</Button>
				<Tooltip.Content>{t.chart.download}</Tooltip.Content>
			</Tooltip>
		</div>
	);
}
