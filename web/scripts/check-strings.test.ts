import { describe, expect, it } from "vitest";
import {
	collectKeys,
	collectReads,
	findBidiControls,
	findViolations,
	unusedKeys,
} from "./check-strings.ts";

const messages = (source: string) => findViolations(source).map((v) => v.message);

describe("findViolations", () => {
	it("flags Latin letters in JSX text and in string children", () => {
		expect(messages("const a = <p>Hello</p>;")).toEqual(['Latin text in JSX: "Hello"']);
		expect(messages('const a = <p>{"Hello"}</p>;')).toEqual(['Latin text in JSX: "Hello"']);
	});

	it("flags literal copy attributes, even when the literal is Persian", () => {
		const source = `const a = <button aria-label="بستن" title={'x'} alt="" placeholder="مثلاً ۱۲" />;`;
		expect(messages(source)).toEqual([
			'literal aria-label="بستن"',
			'literal title="x"',
			'literal placeholder="مثلاً ۱۲"',
		]);
	});

	it("allows copy read from the tree, Persian text and empty alt", () => {
		const source = `const a = <p aria-label={t.common.close} alt="">سلام {name} ۱۲۳</p>;`;
		expect(messages(source)).toEqual([]);
	});

	it("ignores Latin letters outside JSX text", () => {
		expect(messages(`const a = <Button className="px-2" onPress={go}>{label}</Button>;`)).toEqual(
			[],
		);
	});
});

describe("string keys", () => {
	const fa = `
		export const fa = {
			common: { close: "x", copy: (n: number) => String(n) },
			"react-aria": { "@a/b": { c: "y" } } satisfies Dict,
		};
	`;

	it("collects leaf keys, including functions and quoted names", () => {
		expect(collectKeys(fa)).toEqual(["common.close", "common.copy", "react-aria.@a/b.c"]);
	});

	it("collects maximal property chains from strings imports only", () => {
		const source = `
			import { t as copy } from "@/strings";
			const t = { other: 1 };
			use(copy.common.close, copy.reactAria["@a/b"], t.other, copy.status[state]);
		`;
		const reads = collectReads(source, "src/x.tsx");
		expect(reads.chains).toEqual([["common", "close"], ["reactAria", "@a/b"], ["status"]]);
		expect(reads.all).toBe(false);
	});

	it("reads a type query on a branch as reading that branch, not the whole tree", () => {
		const source = `import { t } from "@/strings"; type Hue = keyof typeof t.admin.accent.colors;`;
		const reads = collectReads(source, "src/x.ts");
		expect(reads.chains).toEqual([["admin", "accent", "colors"]]);
		expect(reads.all).toBe(false);
	});

	it("treats an aliased tree as reading everything", () => {
		expect(collectReads(`import { t } from "../strings"; const s = t;`, "src/x.ts").all).toBe(true);
	});

	it("does not count a helper imported next to the tree as reading everything", () => {
		const source = `import { formatToman, t } from "@/strings"; use(formatToman(5), t.a.b);`;
		const reads = collectReads(source, "src/x.tsx");
		expect(reads.chains).toEqual([["a", "b"]]);
		expect(reads.all).toBe(false);
	});

	it("follows the tree imported by file name, with or without the extension", () => {
		for (const path of ["../../strings/fa.ts", "../../strings/fa", "./fa.ts"]) {
			const reads = collectReads(`import { fa } from "${path}"; use(fa.x.y);`, "src/x.ts");
			expect(reads.chains, path).toEqual([["x", "y"]]);
		}
	});

	it("reports keys no chain reaches; a read of a parent covers its children", () => {
		const keys = ["common.close", "common.copy", "state.errorTitle", "theme.light"];
		const chains = [["common", "close"], ["theme"]];
		expect(unusedKeys(keys, chains)).toEqual(["common.copy", "state.errorTitle"]);
	});
});

describe("findBidiControls", () => {
	const char = (code: number) => String.fromCodePoint(code);

	it("finds every embedding, override and isolate control, where it is", () => {
		const controls = [0x202a, 0x202b, 0x202c, 0x202d, 0x202e, 0x2066, 0x2067, 0x2068, 0x2069];
		for (const code of controls) {
			const source = `const a = 1;\nconst b = "x${char(code)}y";`;
			const hex = code.toString(16).toUpperCase();
			expect(findBidiControls(source), hex).toEqual([
				{ line: 2, column: 13, codePoint: `U+${hex}` },
			]);
		}
	});

	it("leaves text and escapes alone: the zero-width non-joiner, the marks and a written escape", () => {
		const text = `می${char(0x200c)}خواهم ${char(0x200e)}${char(0x200f)} ok`;
		expect(findBidiControls(text)).toEqual([]);
		// The escape as it is written in source: a backslash, then u202E.
		expect(findBidiControls(`const a = "${"\\"}u202E";`)).toEqual([]);
	});

	it("reports each one on a line, in order", () => {
		const source = `a${char(0x202e)}b${char(0x2066)}c`;
		expect(findBidiControls(source).map((hit) => hit.column)).toEqual([2, 4]);
	});
});
