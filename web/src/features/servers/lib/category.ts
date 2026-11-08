import type { ServerFormValues } from "../components/ServerForm";

/** The select's value for a server with no category. */
export const NO_CATEGORY = "none";

export const categoryValue = (id: number | null | undefined): string =>
	id == null ? NO_CATEGORY : String(id);

/** The form's fields as the API wants them: the category as a number, or null for none. */
export function toServerPayload(values: ServerFormValues) {
	const { category, quota_gb: _gb, quota_reset_day: _day, ...rest } = values;
	return { ...rest, category_id: category === NO_CATEGORY ? null : Number(category) };
}

/** The same for an edit: the quota is cleared with null when its box is emptied. */
export function toServerPatch(values: ServerFormValues) {
	return {
		...toServerPayload(values),
		quota_gb: values.quota_gb ?? null,
		quota_reset_day: values.quota_reset_day ?? null,
	};
}
