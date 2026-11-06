// `bun run check:strings`: copy is in src/strings/fa.ts, and every key in it is read.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import ts from "typescript";

const ROOT = join(import.meta.dirname, "..");
const SRC = join(ROOT, "src");
const FA_FILE = "src/strings/fa.ts";
const COPY_ATTRIBUTES = new Set(["aria-label", "placeholder", "title", "alt"]);
const LATIN = /[A-Za-z]/;
const STRINGS_MODULE = /(^|\/)strings(\/(index|fa))?(\.ts)?$|^\.\/fa(\.ts)?$/;

// Not user-facing copy: generated code, the strings module, tests and the design-system gallery.
const SKIP_JSX = [
	"src/api/generated/",
	"src/api/zod/",
	"src/strings/",
	"src/test/",
	"src/routeTree.gen.ts",
];
const isTest = (file: string) => /\.test\.tsx?$/.test(file) || file.includes("/__tests__/");

export type Violation = { line: number; message: string };

// Bidi controls (U+202A-202E, U+2066-2069) change display invisibly: write escapes, not characters.
const BIDI_CONTROLS = /[\u202A-\u202E\u2066-\u2069]/gu;

export type BidiHit = { line: number; column: number; codePoint: string };

export function findBidiControls(source: string): BidiHit[] {
	const hits: BidiHit[] = [];
	source.split("\n").forEach((text, index) => {
		for (const match of text.matchAll(BIDI_CONTROLS)) {
			const code = (match[0].codePointAt(0) ?? 0).toString(16).toUpperCase().padStart(4, "0");
			hits.push({ line: index + 1, column: (match.index ?? 0) + 1, codePoint: `U+${code}` });
		}
	});
	return hits;
}

function parse(source: string, fileName: string) {
	return ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
}

function lineOf(sf: ts.SourceFile, node: ts.Node) {
	return sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
}

function literalText(node: ts.Node | undefined): string | null {
	if (!node) return null;
	if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
	if (ts.isJsxExpression(node)) return literalText(node.expression);
	return null;
}

export function findViolations(source: string, fileName = "file.tsx"): Violation[] {
	const sf = parse(source, fileName);
	const found: Violation[] = [];
	const visit = (node: ts.Node) => {
		if (ts.isJsxText(node) && LATIN.test(node.text)) {
			found.push({ line: lineOf(sf, node), message: `Latin text in JSX: "${node.text.trim()}"` });
		}
		if (ts.isJsxAttribute(node) && COPY_ATTRIBUTES.has(node.name.getText(sf))) {
			const text = literalText(node.initializer);
			if (text) {
				const name = node.name.getText(sf);
				found.push({ line: lineOf(sf, node), message: `literal ${name}="${text}"` });
			}
		}
		if (
			ts.isJsxExpression(node) &&
			(ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))
		) {
			const text = literalText(node);
			if (text && LATIN.test(text)) {
				found.push({ line: lineOf(sf, node), message: `Latin text in JSX: "${text}"` });
			}
		}
		ts.forEachChild(node, visit);
	};
	visit(sf);
	return found;
}

// Leaf key paths of the object literal exported from fa.ts ("common.close", ...).
export function collectKeys(faSource: string): string[] {
	const sf = parse(faSource, FA_FILE);
	const keys: string[] = [];
	const walk = (node: ts.Expression, path: string[]) => {
		while (ts.isSatisfiesExpression(node) || ts.isAsExpression(node)) node = node.expression;
		if (!ts.isObjectLiteralExpression(node)) {
			keys.push(path.join("."));
			return;
		}
		for (const prop of node.properties) {
			if (
				ts.isPropertyAssignment(prop) &&
				(ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name))
			) {
				walk(prop.initializer, [...path, prop.name.text]);
			}
		}
	};
	for (const statement of sf.statements) {
		if (!ts.isVariableStatement(statement)) continue;
		for (const decl of statement.declarationList.declarations) {
			if (decl.name.getText(sf) === "fa" && decl.initializer) walk(decl.initializer, []);
		}
	}
	return keys;
}

// Maximal `t.a.b` chains rooted at an import from the strings module; a bare reference reads all.
export function collectReads(
	source: string,
	fileName: string,
): { chains: string[][]; all: boolean } {
	const sf = parse(source, fileName);
	const roots = new Set<string>();
	for (const statement of sf.statements) {
		if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier))
			continue;
		if (!STRINGS_MODULE.test(statement.moduleSpecifier.text)) continue;
		const named = statement.importClause?.namedBindings;
		if (named && ts.isNamedImports(named)) {
			// Only the copy tree is a root: `formatToman(x)` is a function call, not a read of every key.
			for (const element of named.elements) {
				const imported = (element.propertyName ?? element.name).text;
				if (imported === "t" || imported === "fa") roots.add(element.name.text);
			}
		}
	}
	const chains: string[][] = [];
	let all = false;
	const inStrings = fileName.includes("src/strings/");
	const visit = (node: ts.Node) => {
		if (ts.isIdentifier(node) && roots.has(node.text) && !ts.isImportSpecifier(node.parent)) {
			const path: string[] = [];
			let current: ts.Node = node;
			for (;;) {
				const parent: ts.Node = current.parent;
				if (ts.isPropertyAccessExpression(parent) && parent.expression === current) {
					path.push(parent.name.text);
					current = parent;
				} else if (ts.isElementAccessExpression(parent) && parent.expression === current) {
					if (!ts.isStringLiteralLike(parent.argumentExpression)) break;
					path.push(parent.argumentExpression.text);
					current = parent;
				} else if (ts.isQualifiedName(parent) && parent.left === current) {
					path.push(parent.right.text);
					current = parent;
				} else if (ts.isNonNullExpression(parent) || ts.isParenthesizedExpression(parent)) {
					current = parent;
				} else break;
			}
			if (path.length > 0) chains.push(path);
			else if (!inStrings) all = true;
		}
		ts.forEachChild(node, visit);
	};
	visit(sf);
	return { chains, all };
}

export function unusedKeys(keys: string[], chains: string[][]): string[] {
	const used = chains.map((chain) => chain.join("."));
	return keys.filter((key) => !used.some((path) => key === path || key.startsWith(`${path}.`)));
}

function listFiles(dir: string, pattern = /\.tsx?$/): string[] {
	return readdirSync(dir, { recursive: true, withFileTypes: true })
		.filter((entry) => entry.isFile() && pattern.test(entry.name))
		.map((entry) => relative(ROOT, join(entry.parentPath, entry.name)).split(sep).join("/"));
}

// Everything we write, not only the code the other rules read.
const TEXT_FILES = /\.(tsx?|css|md|json|html|svg)$/;
const BIDI_DIRS = ["src", "scripts"];

function main() {
	const files = listFiles(SRC);
	const problems: string[] = [];

	for (const file of files.filter((f) => f.endsWith(".tsx"))) {
		if (isTest(file) || SKIP_JSX.some((skip) => file.startsWith(skip))) continue;
		for (const v of findViolations(readFileSync(join(ROOT, file), "utf8"), file)) {
			problems.push(`${file}:${v.line}: ${v.message}`);
		}
	}

	const chains: string[][] = [];
	let readsAll = false;
	for (const file of files.filter((f) => f !== FA_FILE && !isTest(f))) {
		const reads = collectReads(readFileSync(join(ROOT, file), "utf8"), file);
		chains.push(...reads.chains);
		readsAll ||= reads.all;
	}
	const keys = collectKeys(readFileSync(join(ROOT, FA_FILE), "utf8"));
	if (!readsAll) {
		for (const key of unusedKeys(keys, chains)) problems.push(`${FA_FILE}: unused key "${key}"`);
	}

	for (const dir of BIDI_DIRS) {
		for (const file of listFiles(join(ROOT, dir), TEXT_FILES)) {
			for (const hit of findBidiControls(readFileSync(join(ROOT, file), "utf8"))) {
				problems.push(
					`${file}:${hit.line}:${hit.column}: literal bidi control character ${hit.codePoint}; write it as an escape`,
				);
			}
		}
	}

	for (const problem of problems) console.error(problem);
	console.log(`${keys.length} strings`);
	if (problems.length > 0) process.exit(1);
}

if (process.argv[1]?.endsWith("check-strings.ts")) main();
