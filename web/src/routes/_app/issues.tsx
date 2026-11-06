import { createFileRoute } from "@tanstack/react-router";
import { IssuesPage } from "@/features/issues";

export const Route = createFileRoute("/_app/issues")({ component: IssuesPage });
