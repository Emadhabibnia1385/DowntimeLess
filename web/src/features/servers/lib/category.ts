import type { ServerFormValues } from "../components/ServerForm";

/** The select's value for a server with no category. */
export const NO_CATEGORY = "none";

export const categoryValue = (id: number | null | undefined): string =>
	id == null ? NO_CATEGORY : String(id);

/** The form's fields as the API wants them: the category as a number, or null for none. */
export function toServerPayload(values: ServerFormValues) {
	const { category, ...rest } = values;
	return { ...rest, category_id: category === NO_CATEGORY ? null : Number(category) };
}
