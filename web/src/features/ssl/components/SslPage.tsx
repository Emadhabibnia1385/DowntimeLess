import { Button, PageHeader } from "@nyxon/nasim";
import { useState } from "react";
import { useCanManage } from "@/features/auth";
import { AddIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { AddDomainDialog } from "./AddDomainDialog";
import { CertTable } from "./CertTable";
import { SummaryCards } from "./SummaryCards";

export function SslPage() {
	useDocumentTitle(t.ssl.title);
	const canManage = useCanManage();
	const [adding, setAdding] = useState(false);
	return (
		<div className="flex flex-col gap-6">
			<PageHeader
				title={t.ssl.title}
				description={t.ssl.subtitle}
				actions={
					canManage ? (
						<Button onPress={() => setAdding(true)}>
							<AddIcon aria-hidden />
							{t.ssl.add}
						</Button>
					) : undefined
				}
			/>
			<SummaryCards />
			<CertTable canManage={canManage} />
			<AddDomainDialog isOpen={adding} onOpenChange={setAdding} />
		</div>
	);
}
