import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Beaker,
  ChevronRight,
  Database,
  FlaskConical,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { fetchCompounds } from "./api";
import type { Compound } from "./types";

function Percent({ value }: { value: number }) {
  return <span className="numeric">{Math.round(value * 100)}%</span>;
}

export default function App() {
  const [compounds, setCompounds] = useState<Compound[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchCompounds(controller.signal)
      .then(setCompounds)
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setError(reason.message);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  };

  useEffect(load, []);

  const visible = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return compounds;
    return compounds.filter((compound) =>
      [compound.name, compound.target_pathogen, compound.status].some((value) =>
        value.toLowerCase().includes(normalized),
      ),
    );
  }, [compounds, query]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><FlaskConical size={19} /></span>
          <span>OpenAD</span>
        </div>
        <nav aria-label="Primary navigation">
          <a className="nav-link active" href="#candidates"><Beaker size={17} /><span>Candidates</span></a>
          <a className="nav-link" href="#experiments"><Activity size={17} /><span>Experiments</span></a>
          <a className="nav-link" href="#datasets"><Database size={17} /><span>Datasets</span></a>
          <a className="nav-link" href="#models"><ShieldCheck size={17} /><span>Models</span></a>
        </nav>
        <div className="sidebar-foot">
          <span className="status-dot" />
          Research environment
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">Acinetobacter program</p>
            <h1>Candidate ranking</h1>
          </div>
          <button className="icon-button" title="Refresh candidates" aria-label="Refresh candidates" onClick={load}>
            <RefreshCw size={18} />
          </button>
        </header>

        <section className="metrics" aria-label="Program summary">
          <div><span>Ranked candidates</span><strong>{compounds.length}</strong></div>
          <div><span>Awaiting validation</span><strong>{compounds.filter((item) => item.status !== "validated").length}</strong></div>
          <div><span>Target organism</span><strong className="organism">A. baumannii</strong></div>
        </section>

        <section className="workspace" id="candidates">
          <div className="toolbar">
            <div>
              <h2>Compound queue</h2>
              <p>Ranked by predicted antimicrobial activity</p>
            </div>
            <label className="search">
              <Search size={16} />
              <span className="sr-only">Search candidates</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search candidates" />
            </label>
          </div>

          {error ? (
            <div className="state error">
              <strong>API unavailable</strong>
              <span>Start the backend at localhost:8000, then refresh.</span>
            </div>
          ) : loading ? (
            <div className="state">Loading candidates...</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Activity</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Evidence</th>
                    <th><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((compound, index) => (
                    <tr key={compound.id}>
                      <td>
                        <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                        <span><strong>{compound.name}</strong><code>{compound.smiles}</code></span>
                      </td>
                      <td><Percent value={compound.activity_score} /></td>
                      <td>
                        <div className="confidence">
                          <span style={{ width: `${compound.confidence * 100}%` }} />
                        </div>
                        <Percent value={compound.confidence} />
                      </td>
                      <td><span className="badge">{compound.status}</span></td>
                      <td>{compound.evidence_source}</td>
                      <td><button className="row-action" title={`Open ${compound.name}`}><ChevronRight size={18} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visible.length === 0 && <div className="state">No candidates match this search.</div>}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
