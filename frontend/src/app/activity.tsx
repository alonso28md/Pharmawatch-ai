import { type ReactNode, useCallback, useMemo, useState } from "react";
import { ActivityContext, type ActivityState } from "./activityContext";

export function ActivityProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ActivityState>("idle");
  const [revision, setRevision] = useState(0);
  const report = useCallback((next: ActivityState) => {
    setState(next);
    setRevision((r) => r + 1);
  }, []);
  const value = useMemo(() => ({ state, revision, report }), [state, revision, report]);
  return <ActivityContext.Provider value={value}>{children}</ActivityContext.Provider>;
}
