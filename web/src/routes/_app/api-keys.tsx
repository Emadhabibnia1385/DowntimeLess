import { createFileRoute } from "@tanstack/react-router";
import { ApiKeysPage } from "@/features/api-keys";

export const Route = createFileRoute("/_app/api-keys")({ component: ApiKeysPage });
