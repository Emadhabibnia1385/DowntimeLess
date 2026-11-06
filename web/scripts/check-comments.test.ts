import { describe, expect, it } from "vitest";
import { findCommentBlocks, findWideComments, MAX_COMMENT_WIDTH } from "./check-comments.ts";

const blocks = (source: string, file = "file.ts") => findCommentBlocks(source, file);

describe("a comment is one short line", () => {
	it("lets single lines through, above code or after it", () => {
		const source = [
			"// why",
			"const a = 1; // also why",
			"",
			"// and another",
			"const b = 2;",
		].join("\n");
		expect(blocks(source)).toEqual([]);
	});

	it("flags a run of two or more lines and says where it starts and how long it is", () => {
		const source = [
			"const a = 1;",
			"// first",
			"// second",
			"const b = 2;",
			"// one",
			"// two",
			"// three",
		].join("\n");
		expect(blocks(source)).toEqual([
			{ line: 2, lines: 2 },
			{ line: 5, lines: 3 },
		]);
	});

	it("does not join a trailing comment with the comment below it", () => {
		expect(blocks(["const a = 1; // after code", "// below"].join("\n"))).toEqual([]);
	});

	it("flags a block comment across lines, JSDoc included, and not one on a single line", () => {
		const source = [
			"/** one line */",
			"/**",
			" * a",
			" * b",
			" */",
			"export const a = 1;",
			"/* x */",
		].join("\n");
		expect(blocks(source)).toEqual([{ line: 2, lines: 4 }]);
	});

	it("leaves a tool directive alone, with its reason on the next line", () => {
		const source = [
			"// biome-ignore lint/style/noNonNullAssertion: it is checked above",
			"// the reason",
			"a();",
		].join("\n");
		expect(blocks(source)).toEqual([]);
	});

	it("reads comments from the code, not from text that looks like one", () => {
		const source = [
			'const text = "// not a comment";',
			"const next = `",
			"// not a comment either",
			"// not a comment either",
			"`;",
			"const pattern = /https?:[/][/]/;",
		].join("\n");
		expect(blocks(source)).toEqual([]);
	});

	it("sees through JSX text that has slashes in it", () => {
		const source = [
			"export const a = (",
			"\t<p>",
			"\t\thttps://example.test/",
			"\t\t// plain text",
			"\t</p>",
			");",
		].join("\n");
		expect(blocks(source, "file.tsx")).toEqual([]);
	});

	it("checks stylesheets too", () => {
		const css = [
			".a { color: red; } /* one */",
			"/* two",
			"   lines */",
			".b { color: blue; }",
		].join("\n");
		expect(blocks(css, "file.css")).toEqual([{ line: 2, lines: 2 }]);
	});
});

describe("a comment line stays short", () => {
	const wide = (source: string, file = "file.ts") => findWideComments(source, file);
	const line = (width: number) => `//${"x".repeat(width - 2)}`;

	it("lets a line of exactly the limit through and flags one character more, saying how long", () => {
		expect(MAX_COMMENT_WIDTH).toBe(100);
		expect(wide(line(100))).toEqual([]);
		expect(wide(["const a = 1;", line(101)].join("\n"))).toEqual([{ line: 2, width: 101 }]);
	});

	it("counts the comment alone, not the indent or the code in front of it", () => {
		expect(wide(`\t\t\t\tconst value = compute(); ${line(90)}`)).toEqual([]);
		expect(wide(`const value = compute(); ${line(120)}`)).toEqual([{ line: 1, width: 120 }]);
	});

	it("counts each line of a run on its own", () => {
		expect(wide([line(60), line(130), line(80)].join("\n"))).toEqual([{ line: 2, width: 130 }]);
	});

	it("counts a block comment on one line and a stylesheet's too", () => {
		expect(wide(`/*${"y".repeat(120)}*/`)).toEqual([{ line: 1, width: 124 }]);
		expect(wide(`.a { color: red; } /*${"y".repeat(120)}*/`, "file.css")).toEqual([
			{ line: 1, width: 124 },
		]);
	});

	it("leaves a tool directive alone: its reason is part of the directive", () => {
		const directive = `// biome-ignore lint/style/noNonNullAssertion: ${"because ".repeat(20)}`;
		expect(wide(directive)).toEqual([]);
	});

	it("reads comments from the code, not from text that looks like one", () => {
		const source = [`const text = "${line(150)}";`, `const next = \`${line(150)}\`;`].join("\n");
		expect(wide(source)).toEqual([]);
	});
});
