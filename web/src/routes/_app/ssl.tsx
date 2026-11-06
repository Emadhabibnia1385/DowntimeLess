import { createFileRoute } from "@tanstack/react-router";
import { SslPage } from "@/features/ssl";

export const Route = createFileRoute("/_app/ssl")({ component: SslPage });
