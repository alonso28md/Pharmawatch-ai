import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { AskPage } from "@/pages/AskPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { EvaluationPage } from "@/pages/EvaluationPage";
import { OperationsPage } from "@/pages/OperationsPage";
import { makePlaceholder } from "@/pages/placeholders";
import { ReviewDetailPage, ReviewPage } from "@/pages/ReviewPage";
import { TriagePage } from "@/pages/TriagePage";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, Component: DashboardPage },
      { path: "triage", Component: TriagePage },
      { path: "ask", Component: AskPage },
      { path: "review", Component: ReviewPage },
      { path: "review/:incidentId", Component: ReviewDetailPage },
      { path: "evaluation", Component: EvaluationPage },
      { path: "operations", Component: OperationsPage },
      { path: "settings", Component: makePlaceholder("settings") },
    ],
  },
];
