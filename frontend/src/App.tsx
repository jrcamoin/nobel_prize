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
  X,
} from "lucide-react";
import { fetchCompound, fetchCompounds, fetchDatasets, fetchModelRuns } from "./api";
import type { Compound, CompoundDetail, Dataset, ModelRun } from "./types";

function Percent({ value }: { value: number }) {
  return <span className="numeric">{Math.round(value * 100)}%</span>;
}

export default function App() {
  const [compounds, setCompounds] = useState<Compound[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [modelRuns, setModelRuns] = useState<ModelRun[]>([]);
  const [selected, setSelected] = useState<CompoundDetail | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      fetchCompounds(controller.signal),
      fetchDatasets(controller.signal),
      fetchModelRuns(controller.signal),
    ])
      .then(([nextCompounds, nextDatasets, nextRuns]) => {
        setCompounds(nextCompounds);
        setDatasets(nextDatasets);
        setModelRuns(nextRuns);
      })
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

  const openCompound = (id: number) => {
    fetchCompound(id).then(setSelected).catch((reason: Error) => setError(reason.message));
  };

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
                      <td>{compound.activity_score === null ? "Unscored" : <Percent value={compound.activity_score} />}</td>
                      <td>
                        <div className="confidence">
                          <span style={{ width: `${(compound.confidence ?? 0) * 100}%` }} />
                        </div>
                        {compound.confidence === null ? "—" : <Percent value={compound.confidence} />}
                      </td>
                      <td><span className="badge">{compound.status}</span></td>
                      <td>{compound.evidence_source}</td>
                      <td><button className="row-action" title={`Open ${compound.name}`} onClick={() => openCompound(compound.id)}><ChevronRight size={18} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visible.length === 0 && <div className="state">No candidates match this search.</div>}
            </div>
          )}
        </section>

        <section className="evidence-grid" aria-label="Scientific provenance">
          <div className="evidence-panel" id="datasets">
            <div className="panel-heading"><Database size={17} /><div><h2>Datasets</h2><p>Immutable source manifests</p></div></div>
            {datasets.length === 0 ? <div className="compact-empty">No dataset imported</div> : datasets.map((dataset) => (
              <div className="evidence-row" key={dataset.id}>
                <div><strong>{dataset.name}</strong><span>{dataset.record_count} records · {dataset.license}</span></div>
                <code title={dataset.sha256}>{dataset.sha256.slice(0, 12)}</code>
              </div>
            ))}
          </div>
          <div className="evidence-panel" id="models">
            <div className="panel-heading"><ShieldCheck size={17} /><div><h2>Model runs</h2><p>Versioned benchmark evidence</p></div></div>
            {modelRuns.length === 0 ? <div className="compact-empty">No benchmark completed</div> : modelRuns.map((run) => (
              <div className="model-summary" key={run.id}>
                <strong>{run.name}</strong><span>{run.split_strategy}</span>
                <div className="score-grid">
                  <div><small>PR AUC</small><b>{run.metrics.average_precision?.toFixed(3) ?? "—"}</b></div>
                  <div><small>ROC AUC</small><b>{run.metrics.roc_auc?.toFixed(3) ?? "—"}</b></div>
                  <div><small>Brier</small><b>{run.metrics.brier_score?.toFixed(3) ?? "—"}</b></div>
                </div>
                {run.metrics.comparisons && (
                  <div className="comparison-table">
                    {Object.entries(run.metrics.comparisons).map(([name, scores]) => (
                      <div key={name}>
                        <span>{name.replaceAll("_", " ")}</span>
                        <b>{scores.average_precision.toFixed(3)} PR AUC</b>
                      </div>
                    ))}
                  </div>
                )}
                {run.metrics.prospective_holdout && (
                  <div className="holdout">
                    <span>Frozen holdout · {run.metrics.prospective_holdout.compound_count} compounds</span>
                    <code title={run.metrics.prospective_holdout.sha256}>
                      {run.metrics.prospective_holdout.sha256.slice(0, 16)}
                    </code>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
        {selected && (
          <div className="drawer-backdrop" role="presentation" onClick={() => setSelected(null)}>
            <aside className="detail-drawer" role="dialog" aria-modal="true" aria-label={`${selected.name} evidence`} onClick={(event) => event.stopPropagation()}>
              <div className="drawer-heading">
                <div><p className="eyebrow">Compound evidence</p><h2>{selected.name}</h2></div>
                <button className="icon-button" aria-label="Close evidence" onClick={() => setSelected(null)}><X size={18} /></button>
              </div>
              <dl>
                <div><dt>InChIKey</dt><dd>{selected.inchikey}</dd></div>
                <div><dt>Molecular weight</dt><dd>{selected.molecular_weight.toFixed(2)} g/mol</dd></div>
                <div><dt>Canonical SMILES</dt><dd><code>{selected.canonical_smiles}</code></dd></div>
                <div><dt>Source</dt><dd>{selected.evidence_source}</dd></div>
              </dl>
              <h3>Measurements</h3>
              <div className="measurement-list">
                {selected.measurements.map((measurement, index) => (
                  <div key={`${measurement.value}-${index}`}>
                    <span>{measurement.standard_type}</span>
                    <strong>{measurement.relation ?? "="} {measurement.value.toFixed(2)} {measurement.units}</strong>
                    <span className={measurement.active ? "activity active" : "activity inactive"}>{measurement.active ? "Active" : "Inactive"}</span>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
