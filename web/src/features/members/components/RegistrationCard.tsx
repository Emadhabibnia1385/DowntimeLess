import { SectionCard, SwitchField, toast } from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import {
	getAuthRegistrationQueryKey,
	useAuthRegistration,
	useAuthSetRegistration,
} from "@/api/generated/auth/auth";
import { errorMessage } from "@/api/transport";
import { t } from "@/strings";

// The panel owner's door: may anyone sign up, and may workspace owners bring new people.
export function RegistrationCard() {
	const queryClient = useQueryClient();
	const status = useAuthRegistration();
	const set = useAuthSetRegistration({
		mutation: {
			onSuccess: (next) => {
				queryClient.setQueryData(getAuthRegistrationQueryKey(), next);
				toast.success(next.open ? t.members.registrationOpened : t.members.registrationClosed);
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	return (
		<SectionCard title={t.members.registrationTitle} description={t.members.registrationHint}>
			<SwitchField
				label={t.members.registrationSwitch}
				value={status.data?.open ?? false}
				onChange={(open) => set.mutate({ data: { open } })}
				isDisabled={status.isPending || set.isPending}
			/>
		</SectionCard>
	);
}
