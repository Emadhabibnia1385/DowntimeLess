import { Button, Dropdown, toast } from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import {
	getAuthMeQueryKey,
	useAuthSwitchWorkspace,
	useAuthWorkspaces,
} from "@/api/generated/auth/auth";
import type { WorkspaceOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { useWorkspace } from "@/features/auth";
import { PersonalChip, RoleChip } from "@/features/members";
import { ChevronDownIcon, WorkspaceIcon } from "@/shared/icons";
import { t } from "@/strings";
import { safePathAfterSwitch } from "./workspacePath";

const ME_KEY = getAuthMeQueryKey()[0];

function Item({ space }: { space: WorkspaceOut }) {
	return (
		<Dropdown.Item id={String(space.id)} textValue={space.name} className="min-h-11 gap-3">
			<div className="flex min-w-0 flex-1 flex-col gap-1">
				<span className="truncate font-medium">{space.name}</span>
				<span className="flex flex-wrap items-center gap-1.5">
					<RoleChip role={space.role} />
					{space.is_personal ? <PersonalChip /> : null}
				</span>
			</div>
			<Dropdown.ItemIndicator />
		</Dropdown.Item>
	);
}

// A pill like GitHub's organization switcher: the current workspace, and the others one press away.
export function WorkspaceSwitcher() {
	const current = useWorkspace();
	const spaces = useAuthWorkspaces({ query: { staleTime: 60_000 } });
	const queryClient = useQueryClient();
	const navigate = useNavigate();
	const pathname = useRouterState({ select: (state) => state.location.pathname });
	const change = useAuthSwitchWorkspace({
		mutation: {
			onSuccess: (user) => {
				queryClient.setQueryData(getAuthMeQueryKey(), user);
				const safe = safePathAfterSwitch(pathname);
				if (safe) void navigate({ to: safe, replace: true });
				// nothing of the old workspace may stay on screen: drop every answer and ask again
				void queryClient.resetQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY });
				toast.success(t.workspace.switched(user.workspace.name));
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	if (!current) return null;
	const list = Array.isArray(spaces.data) ? spaces.data : [current];
	return (
		<Dropdown>
			<Button
				variant="secondary"
				aria-label={t.workspace.switcher(current.name)}
				isPending={change.isPending}
				className="min-h-11 max-w-[min(16rem,40vw)] gap-1 rounded-full px-2.5 max-sm:me-11 sm:gap-1.5 sm:px-3"
			>
				<WorkspaceIcon aria-hidden className="size-5 shrink-0" />
				<span className="hidden min-w-0 truncate sm:inline">{current.name}</span>
				<ChevronDownIcon aria-hidden className="size-4 shrink-0 text-muted" />
			</Button>
			<Dropdown.Popover placement="bottom end" className="w-72 max-w-[calc(100vw-2rem)]">
				<Dropdown.Menu
					aria-label={t.workspace.menuLabel}
					items={list}
					selectionMode="single"
					disallowEmptySelection
					selectedKeys={[String(current.id)]}
					onSelectionChange={(keys) => {
						const picked = keys === "all" ? null : Number([...keys][0]);
						if (picked && picked !== current.id) change.mutate({ data: { workspace_id: picked } });
					}}
				>
					{(space) => <Item space={space} />}
				</Dropdown.Menu>
			</Dropdown.Popover>
		</Dropdown>
	);
}
