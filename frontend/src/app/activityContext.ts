import { createContext, useContext } from "react";

/**
 * Application activity, driven only by real request lifecycles and results (never timers).
 * The dynamic background (PulseField) renders it; pages report into it.
 */
export type ActivityState = "idle" | "processing" | "ok" | "serious" | "escalated" | "error";

export interface Activity {
  state: ActivityState;
  /** Increments on every report, so the same state twice still triggers a transition. */
  revision: number;
  report: (state: ActivityState) => void;
}

export const ActivityContext = createContext<Activity | null>(null);

export function useActivity(): Activity {
  const ctx = useContext(ActivityContext);
  if (!ctx) throw new Error("useActivity must be used inside ActivityProvider");
  return ctx;
}
