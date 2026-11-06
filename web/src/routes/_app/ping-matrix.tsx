import { createFileRoute } from "@tanstack/react-router";
import { PingMatrixPage } from "@/features/ping-matrix";

export const Route = createFileRoute("/_app/ping-matrix")({ component: PingMatrixPage });
