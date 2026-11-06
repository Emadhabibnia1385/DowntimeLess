import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/app/shell/AppLayout";

// The pathless layout every signed-in screen lives in: the auth gate and the app frame.
export const Route = createFileRoute("/_app")({ component: AppLayout });
