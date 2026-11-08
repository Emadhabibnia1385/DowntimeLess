/** A server's page belongs to the old workspace; every other page exists in each workspace. */
export function safePathAfterSwitch(pathname: string): string | null {
	return /^\/servers\/[^/]+/.test(pathname) ? "/" : null;
}
