import { useEffect, useState } from "react";
import { searchCompounds } from "./api";
import type { Compound } from "./types";
import "./explorer.css";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
type Evidence = { assay_id: string; organism: string; description: string | null; value: number; relation: string | null; units: string; source: string; assay_url: string; license: string; imported_at: string; snapshot_count: number };
type Report = { compound: { name: string; inchikey: string; smiles: string }; evidence: Evidence[]; unique_record_count: number; repeated_snapshot_records: number; possible_cross_source_overlaps: number; mixed_outcomes: boolean; interpretation: string; comparison_note: string; gaps: string[]; revision: string; evidence_revision: string; predictions: { model_run_id: number; probability: number; uncertainty: number }[] };
type Match = { input: string; status: string; inchikey: string; name: string; records: number; mixed_outcomes: boolean; sources: string; gaps: string };
type Watch = { key: string; name: string; revision: string };
type SearchWatch = { query: string; keys: string[] };

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`${API}/api/explorer${path}`, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined);
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(typeof problem.detail === "string" ? problem.detail : `Request failed (${response.status})`);
  }
  return response.json();
}

function saved<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || "null") ?? fallback; } catch { return fallback; }
}

export default function Explorer() {
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<Compound[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [csv, setCsv] = useState("identifier\n");
  const [matches, setMatches] = useState<Match[]>([]);
  const [keys, setKeys] = useState<string[]>([]);
  const [comparison, setComparison] = useState<{ reports: Report[]; note: string } | null>(null);
  const [watches, setWatches] = useState<Watch[]>(() => saved("openad-watches", []));
  const [searches, setSearches] = useState<SearchWatch[]>(() => saved("openad-searches", []));
  const [alerts, setAlerts] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [notice, setNotice] = useState("");

  const open = async (key: string) => {
    setError("");
    try {
      setReport(await request<Report>(`/reports/${encodeURIComponent(key)}`));
      const url = new URL(window.location.href); url.searchParams.set("compound", key);
      window.history.replaceState(null, "", url);
    } catch (e) { setError(String(e)); }
  };
  useEffect(() => {
    const key = new URL(window.location.href).searchParams.get("compound");
    if (key) void open(key);
  }, []);
  useEffect(() => {
    try { localStorage.setItem("openad-watches", JSON.stringify(watches)); localStorage.setItem("openad-searches", JSON.stringify(searches)); }
    catch { setError("This browser cannot save watches. Enable local storage to keep them."); }
  }, [watches, searches]);
  useEffect(() => {
    let stopped = false;
    const check = async () => {
      const updates: string[] = [];
      try {
        for (const watch of watches) {
          const next = await request<Report>(`/reports/${encodeURIComponent(watch.key)}`);
          if (next.evidence_revision !== watch.revision) updates.push(`New or changed evidence: ${watch.name}`);
        }
        for (const search of searches) {
          const results = await searchCompounds(search.query);
          const added = results.filter(c => !search.keys.includes(c.inchikey)).length;
          if (added) updates.push(`${added} new matches for “${search.query}”`);
        }
        if (!stopped) setAlerts(updates);
      } catch { if (!stopped) setError("Could not check watches. Your saved watches are retained."); }
    };
    void check();
    const timer = window.setInterval(check, 60000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [watches, searches]);

  const search = async () => {
    setError(""); setBusy(true);
    try { setFound(await searchCompounds(query.trim())); setSearched(true); } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };
  const match = async () => {
    setBusy(true); setError("");
    try { setMatches((await request<{ results: Match[] }>("/match", { csv })).results); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  const exportList = async () => {
    try {
      const response = await fetch(`${API}/api/explorer/match/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ csv }) });
      if (!response.ok) throw new Error("Export failed; check your CSV");
      const url = URL.createObjectURL(await response.blob()); const a = document.createElement("a");
      a.href = url; a.download = "compound-evidence.csv"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(String(e)); }
  };
  const select = (key: string) => setKeys(current => current.includes(key) ? current.filter(k => k !== key) : [...current, key].slice(-8));
  return <section className="public-explorer" id="explorer">
    <p className="eyebrow">Open antibiotic evidence</p>
    <h2>What do we know about this compound?</h2>
    <p>Explore published measurements, compare the evidence, and find what is still unknown. Start with a name, ChEMBL ID, InChIKey, or SMILES.</p>
    <form onSubmit={e => { e.preventDefault(); void search(); }} className="explorer-actions">
      <input aria-label="Find compound evidence" value={query} onChange={e => setQuery(e.target.value)} placeholder="Compound name or identifier" minLength={2} maxLength={120} required />
      <button disabled={busy}>Find evidence</button>
      <button type="button" disabled={query.trim().length < 2 || searches.length >= 10} onClick={async () => {
        try { const results = await searchCompounds(query.trim()); setSearches(s => [...s.filter(v => v.query !== query.trim()), { query: query.trim(), keys: results.map(c => c.inchikey) }]); }
        catch (e) { setError(String(e)); }
      }}>Follow this search</button>
    </form>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {searched && found.length === 0 && <p>No matching compounds in the imported evidence. Try a source ID or InChIKey; a missing match does not mean the compound has never been studied.</p>}
    {found.length >= 50 && <p>Showing the first 50 matches. Narrow your search for more specific results.</p>}
    <div className="explorer-results">{found.map(c => <div key={c.id}>
      <button onClick={() => void open(c.inchikey)}>{c.name}</button> <code>{c.inchikey}</code>
      <label><input type="checkbox" checked={keys.includes(c.inchikey)} onChange={() => select(c.inchikey)} /> Compare</label>
    </div>)}</div>

    <details><summary>Match your compound list</summary>
      <p>Upload or paste a CSV with an identifier, inchikey, smiles, name, or source_id column. Up to 200 rows. Lists are processed without being saved as datasets.</p>
      <input type="file" accept=".csv,text/csv" aria-label="Upload compound CSV" onChange={async e => {
        const file = e.target.files?.[0]; if (!file) return;
        if (file.size > 200000) { setError("CSV must be smaller than 200 KB"); return; }
        setCsv(await file.text()); setMatches([]);
      }} />
      <textarea aria-label="Compound CSV" rows={5} value={csv} onChange={e => { setCsv(e.target.value); setMatches([]); }} />
      <div className="explorer-actions"><button disabled={busy} onClick={match}>Match list</button><button onClick={exportList}>Export cited matches</button></div>
      {matches.length > 0 && <div className="table-scroll"><table><thead><tr><th>Input</th><th>Match</th><th>Evidence records</th><th>Comparison</th></tr></thead><tbody>{matches.map((m, i) => <tr key={i}>
        <td>{m.input}</td><td>{m.inchikey ? <button onClick={() => void open(m.inchikey)}>{m.name}</button> : m.status}</td><td>{m.records}{m.mixed_outcomes ? " · mixed outcomes" : ""}</td>
        <td>{m.inchikey && <input aria-label={`Compare ${m.name}`} type="checkbox" checked={keys.includes(m.inchikey)} onChange={() => select(m.inchikey)} />}</td>
      </tr>)}</tbody></table></div>}
    </details>

    {keys.length > 0 && <div className="explorer-actions"><button disabled={keys.length < 2} onClick={async () => {
      try { setComparison(await request(`/compare?keys=${encodeURIComponent(keys.join(","))}`)); } catch (e) { setError(String(e)); }
    }}>Compare {keys.length} selected compounds</button><button onClick={() => { setKeys([]); setComparison(null); }}>Clear selection</button></div>}
    {comparison && <div className="table-scroll"><p>{comparison.note}</p><table><thead><tr><th>Compound</th><th>Distinct records</th><th>Mixed outcomes</th><th>Strain / method</th></tr></thead><tbody>{comparison.reports.map(r => <tr key={r.compound.inchikey}><td><button onClick={() => void open(r.compound.inchikey)}>{r.compound.name}</button></td><td>{r.unique_record_count}</td><td>{r.mixed_outcomes ? "Yes — inspect assays" : "Not observed"}</td><td>Not structured; review sources</td></tr>)}</tbody></table></div>}

    {report && <article className="compound-report">
      <h3>{report.compound.name} — evidence report</h3><code>{report.compound.inchikey}</code>
      <div className="explorer-actions">
        <a href={`${API}/api/explorer/reports/${report.compound.inchikey}/export`}>Download cited CSV</a>
        <button onClick={() => window.print()}>Print / save PDF</button>
        <button onClick={async () => { try { await navigator.clipboard.writeText(window.location.href); setNotice("Report link copied"); } catch { setNotice("Copy the report URL from your address bar to share it."); } }}>Copy report link</button>
        <button disabled={watches.length >= 30 && !watches.some(w => w.key === report.compound.inchikey)} onClick={() => setWatches(w => [...w.filter(v => v.key !== report.compound.inchikey), { key: report.compound.inchikey, name: report.compound.name, revision: report.evidence_revision }])}>Follow / mark evidence as read</button>
      </div>
      <p>{report.unique_record_count} distinct measurement records · {report.repeated_snapshot_records} repeated snapshot records collapsed</p>
      {report.possible_cross_source_overlaps > 0 && <p>{report.possible_cross_source_overlaps} matching measurement signatures appear across sources. These may be reused evidence or coincidentally equal results; inspect citations before treating them as independent studies.</p>}
      <p>{report.interpretation}</p><p>{report.comparison_note}</p>
      <h4>Evidence gaps</h4><ul>{report.gaps.map(g => <li key={g}>{g}</li>)}</ul>
      <h4>Published measurements</h4>
      {report.evidence.map((e, i) => <div className="measurement-card" key={i}>
        <strong>{e.relation || ""} {e.value} {e.units}</strong> · {e.organism}
        <p>{e.description || "Assay description unavailable"}</p>
        <a href={e.assay_url} target="_blank" rel="noreferrer">{e.source} · {e.assay_id}</a>
        <small>Imported {new Date(e.imported_at + "Z").toLocaleDateString()} · {e.license}</small>
      </div>)}
      <h4>Computational predictions</h4>
      <p>Model scores are separate from published measurements and do not establish laboratory activity.</p>
      {report.predictions.length ? report.predictions.map(p => <p key={p.model_run_id}>Model run {p.model_run_id}: {(p.probability * 100).toFixed(1)}% predicted activity · uncertainty {p.uncertainty.toFixed(3)}</p>) : <p>No model predictions available.</p>}
      <small>Report revision: {report.revision}. Shared links show current evidence; downloaded reports retain this revision.</small>
    </article>}
    <details><summary>Following and updates ({watches.length + searches.length})</summary>
      <p>Saved in this browser. Checks run while this page is open and when you return. Alerts refer to newly imported evidence, not necessarily newly published studies. Search watches track the first 50 matches; use a specific name or identifier.</p>
      {alerts.map(a => <p role="status" key={a}>{a}</p>)}
      {!alerts.length && <p>No changes detected in your saved watches.</p>}
      {watches.map(w => <p key={w.key}><button onClick={() => void open(w.key)}>{w.name}</button> <button onClick={() => setWatches(ws => ws.filter(v => v.key !== w.key))}>Unfollow</button></p>)}
      {searches.map(s => <p key={s.query}>Search: {s.query} <button onClick={async () => {
        try { const results = await searchCompounds(s.query); setFound(results); setQuery(s.query); setSearches(ss => ss.map(v => v.query === s.query ? { ...v, keys: results.map(c => c.inchikey) } : v)); }
        catch (e) { setError(String(e)); }
      }}>Review and mark read</button> <button onClick={() => setSearches(ss => ss.filter(v => v.query !== s.query))}>Unfollow</button></p>)}
    </details>
  </section>;
}
