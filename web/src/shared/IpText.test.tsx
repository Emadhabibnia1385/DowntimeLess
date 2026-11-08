import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IpText } from "./IpText";

describe("IpText", () => {
	afterEach(() => vi.unstubAllGlobals());

	it("shows the address and copies exactly it when the button is pressed", async () => {
		const writeText = vi.fn(async () => {});
		vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
		render(<IpText ip="203.0.113.7" />);
		expect(screen.getByText("203.0.113.7")).toBeTruthy();
		await userEvent.click(screen.getByRole("button", { name: "کپی آدرس IP" }));
		expect(writeText).toHaveBeenCalledWith("203.0.113.7");
	});
});
