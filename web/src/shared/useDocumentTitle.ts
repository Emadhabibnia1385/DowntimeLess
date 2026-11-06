import { useEffect } from "react";
import { t } from "@/strings";

/** Sets the tab's title to the screen's name followed by the product's. */
export function useDocumentTitle(screen: string) {
	useEffect(() => {
		document.title = `${screen} | ${t.brand.name}`;
	}, [screen]);
}
