import { Button, ConfirmDialog, Modal, toast } from "@nyxon/nasim";
import { useState } from "react";
import type { CategoryOut } from "@/api/generated/model";
import {
	useCategoriesCreate,
	useCategoriesDelete,
	useCategoriesUpdate,
} from "@/api/generated/categories/categories";
import { errorMessage } from "@/api/transport";
import { EditIcon, TrashIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { formatNumber, t } from "@/strings";
import { useCategories } from "../api";
import { CategoryNameForm } from "./CategoryNameForm";

// Add, rename and delete categories; a server without one is fine.
export function CategoryManager({
	isOpen,
	onOpenChange,
}: {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const categories = useCategories();
	const refresh = useRefreshAll();
	const [renaming, setRenaming] = useState<number | null>(null);
	const [deleting, setDeleting] = useState<CategoryOut | null>(null);
	const create = useCategoriesCreate({ mutation: { onSuccess: () => void refresh() } });
	const update = useCategoriesUpdate({
		mutation: {
			onSuccess: () => {
				toast.success(t.common.saved);
				setRenaming(null);
				void refresh();
			},
		},
	});
	const remove = useCategoriesDelete({
		mutation: {
			onSuccess: () => {
				setDeleting(null);
				void refresh();
			},
			onError: (error) => {
				setDeleting(null);
				toast.danger(errorMessage(error));
			},
		},
	});
	return (
		<>
			<Modal isOpen={isOpen} onOpenChange={onOpenChange} title={t.categories.title}>
				<div className="flex flex-col gap-4">
					<p className="text-sm text-muted">{t.categories.hint}</p>
					<CategoryNameForm
						name=""
						submitLabel={t.categories.add}
						error={create.error}
						onSubmit={(name) => create.mutate({ data: { name } })}
					/>
					{categories.data?.length ? (
						<ul className="flex flex-col gap-2">
							{categories.data.map((category) => (
								<li
									key={category.id}
									className="flex flex-col gap-2 rounded-lg border border-border p-3"
								>
									{renaming === category.id ? (
										<CategoryNameForm
											name={category.name}
											submitLabel={t.common.save}
											error={update.error}
											onSubmit={(name) =>
												update.mutate({ categoryId: category.id, data: { name } })
											}
										/>
									) : (
										<div className="flex items-center justify-between gap-2">
											<div>
												<p className="font-semibold">{category.name}</p>
												<p className="text-xs text-muted">
													{t.categories.count(formatNumber(category.server_count))}
												</p>
											</div>
											<div className="flex gap-1">
												<Button
													isIconOnly
													size="sm"
													variant="secondary"
													aria-label={t.common.edit}
													onPress={() => setRenaming(category.id)}
												>
													<EditIcon aria-hidden />
												</Button>
												<Button
													isIconOnly
													size="sm"
													variant="danger-soft"
													aria-label={t.common.delete}
													onPress={() => setDeleting(category)}
												>
													<TrashIcon aria-hidden />
												</Button>
											</div>
										</div>
									)}
								</li>
							))}
						</ul>
					) : (
						<p className="text-sm text-muted">{t.categories.empty}</p>
					)}
				</div>
			</Modal>
			<ConfirmDialog
				isOpen={deleting !== null}
				onOpenChange={(open) => !open && setDeleting(null)}
				tone="danger"
				title={t.categories.deleteTitle}
				description={t.categories.deleteBody}
				confirmLabel={t.common.delete}
				isPending={remove.isPending}
				onConfirm={() => {
					if (deleting) remove.mutate({ categoryId: deleting.id });
				}}
			/>
		</>
	);
}
