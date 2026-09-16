import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Explorer from "./Explorer";

const key = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N";
const report = {
  compound: { name: "Example", inchikey: key, smiles: "CCO" }, evidence: [],
  unique_record_count: 0, repeated_snapshot_records: 0, mixed_outcomes: false,
  interpretation: "No measurements available", comparison_note: "Review assay conditions",
  gaps: ["Strain unavailable"], revision: "report-revision", evidence_revision: "new-evidence", predictions: [],
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); window.history.replaceState(null, "", "/"); });

test("shared report opens without search and can be followed", async () => {
  window.history.replaceState(null, "", `/?compound=${key}`);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => report }));
  render(<Explorer />);
  expect(await screen.findByText("Example — evidence report")).toBeInTheDocument();
  expect(screen.getByText("Strain unavailable")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download cited CSV" })).toHaveAttribute("href", expect.stringContaining(key));
  fireEvent.click(screen.getByText("Follow / mark evidence as read"));
  await waitFor(() => expect(JSON.parse(localStorage.getItem("openad-watches") || "[]")[0].key).toBe(key));
});

test("CSV matching exposes unmatched inputs", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ results: [{ input: "unknown", status: "unmatched", inchikey: "", name: "", records: 0 }] }) }));
  render(<Explorer />);
  fireEvent.click(screen.getByText("Match your compound list"));
  fireEvent.change(screen.getByLabelText("Compound CSV"), { target: { value: "identifier\nunknown" } });
  fireEvent.click(screen.getByText("Match list"));
  expect(await screen.findByText("unmatched")).toBeInTheDocument();
});

test("saved compound watches surface changed evidence on return", async () => {
  localStorage.setItem("openad-watches", JSON.stringify([{ key, name: "Example", revision: "old-evidence" }]));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => report }));
  render(<Explorer />);
  expect(await screen.findByText("New or changed evidence: Example")).toBeInTheDocument();
});
