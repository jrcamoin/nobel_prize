import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App";

afterEach(() => vi.restoreAllMocks());

test("renders ranked compounds from the API", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve({
    ok: true,
    json: async () => url.endsWith("/api/compounds") ? [{
      id: 1,
      name: "Candidate A",
      smiles: "CCO",
      target_pathogen: "Acinetobacter baumannii",
      activity_score: 0.82,
      confidence: 0.68,
      status: "needs validation",
      evidence_source: "Test evidence",
      created_at: "2026-01-01T00:00:00",
    }] : [],
  })));

  render(<App />);

  expect(await screen.findByText("Candidate A")).toBeInTheDocument();
  expect(screen.getByText("82%")).toBeInTheDocument();
});
