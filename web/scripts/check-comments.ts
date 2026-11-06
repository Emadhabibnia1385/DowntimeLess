// `bun run check:comments`: a comment is one short line that says why; longer ones fail below.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import ts from "typescript";

const ROOT = join(import.meta.dirname, "..");
const FOLDERS = ["scripts", "src"];
const FILES = ["orval.config.ts", "vite.config.ts", "vitest.config.ts"];
const SKIP = ["src/api/generated/", "src/api/zod/", "src/routeTree.gen.ts"];
const DIRECTIVE = /^(\/\/\s*(biome-ignore|oxlint-|eslint-|@ts-|prettier-ignore)|\/\/\/)/;

export const MAX_COMMENT_WIDTH = 100;

export type CommentBlock = { line: number; lines: number };
export type WideComment = { line: number; width: number };

// One comment as written: where it starts, how many lines and characters, and what kind it is.
type Piece = {
	line: number;
	lines: number;
	width: number;
	joinable: boolean;
	directive: boolean;
};

const piecesOf = (source: string, fileName: string) =>
	fileName.endsWith(".css") ? cssComments(source) : tsComments(source, fileName);

// The comment lines too long to read at a glance; a tool directive keeps its reason on its line.
export function findWideComments(source: string, fileName: string): WideComment[] {
	return piecesOf(source, fileName)
		.filter((piece) => piece.lines === 1 && !piece.directive && piece.width > MAX_COMMENT_WIDTH)
		.map((piece) => ({ line: piece.line, width: piece.width }));
}

// The comments of two lines or more: a run of own-line `//` comments, or a block across lines.
export function findCommentBlocks(source: string, fileName: string): CommentBlock[] {
	const pieces = piecesOf(source, fileName);
	const found: CommentBlock[] = [];
	let run: CommentBlock | undefined;
	const close = () => {
		if (run && run.lines > 1) found.push(run);
		run = undefined;
	};
	for (const piece of pieces) {
		if (piece.lines > 1) {
			close();
			found.push({ line: piece.line, lines: piece.lines });
		} else if (!piece.joinable) {
			close();
		} else if (run && piece.line === run.line + run.lines) {
			run.lines += 1;
		} else {
			close();
			run = { line: piece.line, lines: 1 };
		}
	}
	close();
	return found;
}

function lineStarts(source: string): number[] {
	const starts = [0];
	for (let i = 0; i < source.length; i++) if (source[i] === "\n") starts.push(i + 1);
	return starts;
}

function lineAt(starts: number[], position: number): number {
	let low = 0;
	let high = starts.length - 1;
	while (low < high) {
		const mid = (low + high + 1) >> 1;
		if ((starts[mid] ?? 0) <= position) low = mid;
		else high = mid - 1;
	}
	return low + 1;
}

// Comments come from the trivia of real tokens, so `; //` in a string, regex or JSX is not one.
function tsComments(source: string, fileName: string): Piece[] {
	const kind = fileName.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
	const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, kind);
	const ranges = new Map<number, ts.CommentRange>();
	const visit = (node: ts.Node) => {
		for (const range of ts.getLeadingCommentRanges(source, node.pos) ?? [])
			ranges.set(range.pos, range);
		for (const range of ts.getTrailingCommentRanges(source, node.end) ?? [])
			ranges.set(range.pos, range);
		for (const child of node.getChildren(file)) visit(child);
	};
	visit(file);
	const starts = lineStarts(source);
	return [...ranges.values()]
		.sort((a, b) => a.pos - b.pos)
		.map((range) => {
			const first = lineAt(starts, range.pos);
			const last = lineAt(starts, Math.max(range.pos, range.end - 1));
			const alone = source.slice(starts[first - 1] ?? 0, range.pos).trim() === "";
			const directive = DIRECTIVE.test(source.slice(range.pos, range.end));
			const plain = range.kind === ts.SyntaxKind.SingleLineCommentTrivia && !directive;
			return {
				line: first,
				lines: last - first + 1,
				width: range.end - range.pos,
				joinable: alone && plain,
				directive,
			};
		});
}

function cssComments(source: string): Piece[] {
	const starts = lineStarts(source);
	return [...source.matchAll(/\/\*[\s\S]*?\*\//g)].map((match) => {
		const first = lineAt(starts, match.index ?? 0);
		const last = lineAt(starts, (match.index ?? 0) + match[0].length - 1);
		const width = match[0].length;
		return { line: first, lines: last - first + 1, width, joinable: false, directive: false };
	});
}

function listFiles(dir: string): string[] {
	if (!existsSync(join(ROOT, dir))) return [];
	return readdirSync(join(ROOT, dir), { recursive: true, withFileTypes: true })
		.filter((entry) => entry.isFile() && /\.(tsx?|css)$/.test(entry.name))
		.map((entry) => relative(ROOT, join(entry.parentPath, entry.name)).split(sep).join("/"));
}

function main() {
	const files = [...FOLDERS.flatMap(listFiles), ...FILES].filter(
		(file) => !SKIP.some((skip) => file.startsWith(skip)),
	);
	let problems = 0;
	for (const file of files.sort()) {
		const source = readFileSync(join(ROOT, file), "utf8");
		for (const block of findCommentBlocks(source, file)) {
			console.error(
				`${file}:${block.line}: a comment of ${block.lines} lines; one short line says why`,
			);
			problems += 1;
		}
		for (const wide of findWideComments(source, file)) {
			console.error(
				`${file}:${wide.line}: a comment line of ${wide.width} characters; at most ${MAX_COMMENT_WIDTH}`,
			);
			problems += 1;
		}
	}
	console.log(`${files.length} files, ${problems} long comments`);
	if (problems > 0) process.exit(1);
}

if (process.argv[1]?.endsWith("check-comments.ts")) main();
