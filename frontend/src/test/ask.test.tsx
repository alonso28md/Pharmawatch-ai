import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderApp } from "./render";

async function ask(question: string) {
  const user = userEvent.setup();
  renderApp("/ask");
  await user.type(await screen.findByLabelText(/pregunta normativa|regulatory question/i), question);
  await user.click(screen.getByRole("button", { name: /^(preguntar|ask)$/i }));
  return user;
}

describe("regulatory Q&A", () => {
  it("renders citations as buttons that open the exact cited fragment", async () => {
    const user = await ask("What is the reporting deadline for a death under the MDR?");
    const cite = (await screen.findAllByRole("button", { name: /C1: MDR 2017\/745/ }))[0]!;
    await user.click(cite);
    const panel = await screen.findByRole("dialog");
    expect(within(panel).getByText(/not later\s+than 10 days after the date/)).toBeInTheDocument();
    expect(within(panel).getAllByText(/Article 87 — Reporting/).length).toBeGreaterThan(0);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows abstention distinctly when the answer cites nothing", async () => {
    await ask("What is the maximum daily dose of paracetamol?");
    expect(await screen.findByText(/No hay información suficiente|Not enough information/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /C1:/ })).not.toBeInTheDocument();
  });

  it("requires at least 10 characters", async () => {
    const user = userEvent.setup();
    renderApp("/ask");
    await user.click(await screen.findByRole("button", { name: /^(preguntar|ask)$/i }));
    expect(screen.getByText(/al menos 10 caracteres|at least 10 characters/)).toBeInTheDocument();
  });
});
