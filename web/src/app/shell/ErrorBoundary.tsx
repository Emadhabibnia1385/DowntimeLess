import { ErrorState } from "@nyxon/nasim";
import { type ErrorComponentProps, useRouter } from "@tanstack/react-router";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { t } from "@/strings";

// A route failed while rendering or loading: retry in place.
export function RouteError({ reset }: ErrorComponentProps) {
	const router = useRouter();
	return (
		<ErrorState
			as="h1"
			title={t.crash.title}
			message={t.crash.message}
			onRetry={() => {
				reset();
				void router.invalidate();
			}}
		/>
	);
}

type State = { failed: boolean };

// The last resort for a crash outside any route (the shell itself): reload the app.
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
	state: State = { failed: false };

	static getDerivedStateFromError(): State {
		return { failed: true };
	}

	componentDidCatch(error: Error, info: ErrorInfo) {
		console.error(error, info.componentStack);
	}

	render() {
		if (!this.state.failed) return this.props.children;
		return (
			<div className="grid min-h-dvh place-items-center bg-background p-page text-foreground">
				<ErrorState
					as="h1"
					title={t.crash.title}
					message={t.crash.message}
					onRetry={() => window.location.reload()}
				/>
			</div>
		);
	}
}
