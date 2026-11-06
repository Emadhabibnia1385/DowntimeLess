import { createFileRoute } from "@tanstack/react-router";
import { ServersPage } from "@/features/servers";

export const Route = createFileRoute("/_app/servers/")({ component: ServersPage });
