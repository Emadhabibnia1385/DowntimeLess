import { renderSVG } from "uqr";

// A client-side QR (uqr): dark on white so it scans in either theme; built from `value` only.
export function QRCode({
	value,
	size = 176,
	label,
}: {
	value: string;
	size?: number;
	/** What the code is for, so a screen reader can say it. */
	label: string;
}) {
	const svg = renderSVG(value, { border: 2, blackColor: "black", whiteColor: "white" });
	return (
		<img
			src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`}
			alt={label}
			width={size}
			height={size}
			className="mx-auto h-auto rounded-lg bg-white p-2"
			style={{ width: size, maxWidth: "100%" }}
		/>
	);
}
