import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Segmented } from "./Segmented";

const OPTIONS = [
	{ value: "6h", label: "۶ ساعت" },
	{ value: "24h", label: "۲۴ ساعت" },
	{ value: "7d", label: "۷ روز" },
	{ value: "30d", label: "۳۰ روز" },
] as const;

type Value = (typeof OPTIONS)[number]["value"];

function Harness({ onChange }: { onChange?: (value: Value) => void }) {
	const [value, setValue] = useState<Value>("24h");
	return (
		<Segmented
			label="بازهٔ زمانی"
			value={value}
			onChange={(next) => {
				setValue(next);
				onChange?.(next);
			}}
			options={OPTIONS}
		/>
	);
}

describe("Segmented", () => {
	it("names the group, labels every segment in Persian and marks the chosen one", () => {
		render(<Harness />);
		const group = screen.getByRole("tablist", { name: "بازهٔ زمانی" });
		const tabs = screen.getAllByRole("tab");
		expect(group).toBeTruthy();
		expect(tabs.map((tab) => tab.textContent)).toEqual(OPTIONS.map((option) => option.label));
		expect(tabs.map((tab) => tab.getAttribute("aria-selected"))).toEqual([
			"false",
			"true",
			"false",
			"false",
		]);
	});

	it("selects a segment on press and reports its value", async () => {
		const onChange = vi.fn();
		render(<Harness onChange={onChange} />);
		await userEvent.click(screen.getByRole("tab", { name: "۷ روز" }));
		expect(onChange).toHaveBeenCalledWith("7d");
		expect(screen.getByRole("tab", { name: "۷ روز" }).getAttribute("aria-selected")).toBe("true");
		expect(screen.getByRole("tab", { name: "۲۴ ساعت" }).getAttribute("aria-selected")).toBe(
			"false",
		);
	});

	it("moves the choice with the arrow keys and keeps one tab stop", async () => {
		const onChange = vi.fn();
		render(<Harness onChange={onChange} />);
		const tabs = screen.getAllByRole("tab");
		expect(tabs.filter((tab) => tab.getAttribute("tabindex") === "0")).toHaveLength(1);
		await userEvent.tab();
		expect(document.activeElement).toBe(screen.getByRole("tab", { name: "۲۴ ساعت" }));
		await userEvent.keyboard("{ArrowRight}");
		const first = onChange.mock.calls.at(-1)?.[0];
		expect(["6h", "7d"]).toContain(first);
		await userEvent.keyboard("{ArrowLeft}{ArrowLeft}");
		expect(onChange.mock.calls.length).toBeGreaterThan(1);
		expect(document.activeElement?.getAttribute("role")).toBe("tab");
	});
});
