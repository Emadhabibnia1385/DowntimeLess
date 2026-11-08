import { createFileRoute } from "@tanstack/react-router";
import { PanelPage } from "@/features/panel";

export const Route = createFileRoute("/_app/panel")({ component: PanelPage });
