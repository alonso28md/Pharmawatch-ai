import { render } from "@testing-library/react";
import { App } from "@/app/App";

/** Render the full app (router + providers) at a path, with MSW answering /api/*. */
export function renderApp(path = "/") {
  return render(<App initialPath={path} />);
}
