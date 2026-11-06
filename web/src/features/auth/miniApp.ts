// Telegram opens a Mini App with the signed launch data in the address hash; the master checks it.
export function miniAppInitData(hash = location.hash): string | null {
	try {
		return new URLSearchParams(hash.slice(1)).get("tgWebAppData") || null;
	} catch {
		return null;
	}
}
