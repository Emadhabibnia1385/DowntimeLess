import { PageSkeleton as NasimPageSkeleton } from "@nyxon/nasim";
import { t } from "@/strings";

// Stands in for a page while its code or the session arrives.
export function PageSkeleton() {
	return <NasimPageSkeleton stats={4} rows={4} label={t.shell.pageLoading} />;
}
