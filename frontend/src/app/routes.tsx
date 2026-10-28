import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { AskPage } from "@/pages/AskPage";
import { makePlaceholder } from "@/pages/placeholders";
import { TriagePage } from "@/pages/TriagePage";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, Component: makePlaceholder("dashboard") },
      { path: "triage", Component: TriagePage },
      { path: "ask", Component: AskPage },
      { path: "review", Component: makePlaceholder("review") },
      { path: "evaluation", Component: makePlaceholder("evaluation") },
      { path: "operations", Component: makePlaceholder("operations") },
      { path: "settings", Component: makePlaceholder("settings") },
    ],
  },
];
