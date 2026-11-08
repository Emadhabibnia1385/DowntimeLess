import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LineChart } from "./LineChart";

const times = [1_790_000_000, 1_790_000_060, 1_790_000_120, 1_790_000_180];

const props = {
	title: "مصرف",
	times,
	series: [
		{ key: "cpu", label: "CPU", tone: "accent" as const, values: [10, 20, null, 40] },
		{ key: "ram", label: "RAM", tone: "info" as const, values: [50, 55, 60, 65] },
	],
	format: (value: number) => `${value}%`,
	domain: [0, 100] as const,
	spanSeconds: 3600,
	fileName: "test",
};

const chip = (name: string) => screen.getByRole("button", { name });

describe("LineChart", () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.restoreAllMocks();
	});

	it("draws one line per run: a null value breaks the line", () => {
		const { container } = render(<LineChart {...props} />);
		const cpu = container.querySelectorAll("svg g.text-accent");
		const ram = container.querySelectorAll("svg g.text-info");
		expect(ram).toHaveLength(1);
		expect(cpu).toHaveLength(2);
	});

	it("writes the date alone for daily points, in the zone given", () => {
		render(<LineChart {...props} time={{ dateOnly: true, timeZone: "Asia/Tehran" }} />);
		const slider = screen.getByRole("slider");
		fireEvent.focus(slider);
		expect(screen.getByRole("status").textContent).not.toContain(":");
		expect(slider.getAttribute("aria-valuetext")).not.toContain(":");
	});

	it("writes date and clock by default", () => {
		render(<LineChart {...props} />);
		fireEvent.focus(screen.getByRole("slider"));
		expect(screen.getByRole("status").textContent).toContain(":");
	});

	it("has a toggle chip per series that hides it, and keeps the last one on", async () => {
		const { container } = render(<LineChart {...props} />);
		const cpu = chip("CPU");
		const ram = chip("RAM");
		expect(cpu.getAttribute("aria-pressed")).toBe("true");
		await userEvent.click(cpu);
		expect(cpu.getAttribute("aria-pressed")).toBe("false");
		expect(container.querySelectorAll("svg g.text-accent")).toHaveLength(0);
		await userEvent.click(ram);
		expect(ram.getAttribute("aria-pressed")).toBe("true");
		await userEvent.click(cpu);
		expect(cpu.getAttribute("aria-pressed")).toBe("true");
	});

	it("shows every shown series at the chosen time with the arrow keys", () => {
		render(<LineChart {...props} />);
		const slider = screen.getByRole("slider");
		fireEvent.focus(slider);
		expect(screen.getByRole("status").textContent).toContain("40%");
		fireEvent.keyDown(slider, { key: "Home" });
		const tooltip = screen.getByRole("status");
		expect(within(tooltip).getByText("CPU")).toBeTruthy();
		expect(within(tooltip).getByText("10%")).toBeTruthy();
		expect(within(tooltip).getByText("50%")).toBeTruthy();
		fireEvent.keyDown(slider, { key: "Escape" });
		expect(screen.queryByRole("status")).toBeNull();
	});

	it("switches to a table with the exact values, newest first, and back", async () => {
		render(<LineChart {...props} />);
		await userEvent.click(screen.getByRole("button", { name: "نمایش جدول داده‌ها" }));
		const table = screen.getByRole("table");
		const rows = within(table).getAllByRole("row");
		expect(rows).toHaveLength(5);
		expect(within(rows[1] as HTMLElement).getByText("40%")).toBeTruthy();
		expect(within(rows[2] as HTMLElement).getByText("—")).toBeTruthy();
		await userEvent.click(screen.getByRole("button", { name: "بازگشت به نمودار" }));
		expect(screen.queryByRole("table")).toBeNull();
	});

	it("downloads the data as a CSV file", async () => {
		const blobs: Blob[] = [];
		vi.stubGlobal("URL", {
			createObjectURL: (blob: Blob) => {
				blobs.push(blob);
				return "blob:x";
			},
			revokeObjectURL: () => {},
		});
		const names: string[] = [];
		vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
			this: HTMLAnchorElement,
		) {
			names.push(this.download);
		});
		render(<LineChart {...props} />);
		await userEvent.click(screen.getByRole("button", { name: "دانلود CSV" }));
		expect(names).toEqual(["test.csv"]);
		expect(blobs).toHaveLength(1);
		const bytes = new Uint8Array(await (blobs[0] as Blob).arrayBuffer());
		expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
		const text = new TextDecoder().decode(bytes.slice(3));
		expect(text.split("\r\n")).toHaveLength(5);
		expect(text).toMatch(/^زمان,CPU,RAM\r\n\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},10,50\r\n/);
	});

	it("says so when there is nothing to draw", () => {
		render(<LineChart {...props} times={[]} series={[]} />);
		expect(screen.getByText("در این بازه داده‌ای ثبت نشده است.")).toBeTruthy();
		expect(screen.queryByRole("slider")).toBeNull();
	});
});
