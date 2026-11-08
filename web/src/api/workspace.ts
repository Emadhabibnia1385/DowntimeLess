// Each tab names its own workspace on every request, so a switch elsewhere never redirects a save.
export const WORKSPACE_HEADER = "X-Workspace-Id";
const KEY = "dl.workspace";

function read(): number | null {
	try {
		const raw = sessionStorage.getItem(KEY);
		const id = raw ? Number(raw) : Number.NaN;
		return Number.isInteger(id) && id > 0 ? id : null;
	} catch {
		return null;
	}
}

let current: number | null = read();

/** The tab's workspace; null until /auth/me answers (the master then uses the session's). */
export function tabWorkspace(): number | null {
	return current;
}

export function setTabWorkspace(id: number | null): void {
	current = id;
	try {
		if (id === null) sessionStorage.removeItem(KEY);
		else sessionStorage.setItem(KEY, String(id));
	} catch {
		// private mode: the id still lives in memory for this tab
	}
}
