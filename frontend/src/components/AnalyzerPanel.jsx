import { useEffect, useRef, useState } from "react";
import { analyzeImage } from "../api.js";
import useReveal from "../useReveal.js";

const RISK_COLORS = {
  wifi: "amber", credential: "red", email: "amber", vcard: "amber",
  url: "green", login: "red", card: "red", id_pa: "red", generic: "green",
};

function Counter({ value }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    let raf;
    const t0 = performance.now();
    const dur = 800;
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      setShown(Math.round(value * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <span className="counter">{shown}</span>;
}

function Badge({ kind }) {
  return <span className={`badge badge-${RISK_COLORS[kind] || "green"}`}>{kind}</span>;
}

export default function AnalyzerPanel() {
  const ref = useReveal();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [mode, setMode] = useState("completo");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  // vista de la imagen resultado: procesada (censura), anotada (señalar), original
  const [view, setView] = useState("procesada");

  useEffect(() => () => previewUrl && URL.revokeObjectURL(previewUrl), [previewUrl]);

  const pick = (f) => {
    if (!f || !f.type.startsWith("image/")) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
    setResult(null);
    setError(null);
  };

  const submit = async () => {
    if (!file || loading) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await analyzeImage(file, mode));
      setView("procesada");
    } catch (e) {
      setResult(null);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const shownImage = !result
    ? previewUrl
    : view === "anotada" ? result.image_annotated
    : view === "original" ? previewUrl
    : result.image_base64;

  return (
    <section className="section" id="herramienta">
      <div className="section-inner reveal" ref={ref}>
        <h2 className="section-title">Analiza una imagen</h2>
        <p className="section-sub">Todo se procesa en tu máquina. Nada sale de la red interna.</p>

        <div className="terminal">
          <div className="terminal-bar">
            <span className="tdot tdot-red" />
            <span className="tdot tdot-amber" />
            <span className="tdot tdot-green" />
            <span className="terminal-title">~/fbi-img/analyze</span>
          </div>

          <div className="terminal-body">
            <div
              className={`dropzone ${dragging ? "dragging" : ""} ${previewUrl ? "has-file" : ""}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files[0]); }}
            >
              <input
                ref={inputRef} type="file" accept="image/*" hidden
                onChange={(e) => pick(e.target.files[0])}
              />
              {shownImage ? (
                <div className="preview-wrap">
                  <img src={shownImage} alt="imagen a analizar" />
                  {loading && <div className="scanline" />}
                </div>
              ) : (
                <p className="drop-hint">
                  <span className="prompt">$</span> arrastra una imagen aquí o haz clic para elegir<span className="cursor">_</span>
                </p>
              )}
            </div>

            {result && previewUrl && (
              <div className="toggle-row">
                <button
                  className={view === "anotada" ? "btn-mark active" : "btn-mark"}
                  onClick={() => setView(view === "anotada" ? "procesada" : "anotada")}
                >
                  ⊙ Señalar datos comprometedores
                </button>
                <button className={view === "procesada" ? "tab active" : "tab"} onClick={() => setView("procesada")}>
                  {result.mode === "completo" ? "censurada" : "procesada"}
                </button>
                <button className={view === "original" ? "tab active" : "tab"} onClick={() => setView("original")}>original</button>
              </div>
            )}

            <div className="controls">
              <div className="mode-tabs" role="tablist">
                {["ligero", "medio", "completo"].map((m) => (
                  <button
                    key={m} role="tab" aria-selected={mode === m}
                    className={mode === m ? "tab active" : "tab"}
                    onClick={() => setMode(m)}
                  >{m}</button>
                ))}
              </div>
              <button className="btn-primary btn-analyze" onClick={submit} disabled={loading || !file}>
                {loading ? "escaneando…" : "ANALIZAR"}
              </button>
            </div>

            {loading && <div className="progress"><div className="progress-bar" /></div>}
            {error && <p className="error">✖ {error}</p>}

            {result && (
              <div className="result">
                <div className="stats">
                  <div className="stat">
                    <Counter value={result.total_detections} />
                    <label>detecciones</label>
                  </div>
                  <div className="stat stat-risk">
                    <Counter value={result.risky_count} />
                    <label>en riesgo</label>
                  </div>
                  <div className="stat">
                    <span className="counter">{result.mode}</span>
                    <label>modo</label>
                  </div>
                </div>

                {result.warnings?.map((w, i) => <p key={i} className="warning">⚠ {w}</p>)}

                {result.report.length > 0 && (
                  <table className="report">
                    <thead>
                      <tr><th>clase</th><th>conf</th><th>hallazgos</th><th>estado</th></tr>
                    </thead>
                    <tbody>
                      {result.report.map((r, i) => (
                        <tr key={i} className={r.risky ? "row-risky" : ""}>
                          <td className="mono">{r.class}</td>
                          <td className="mono">{r.conf ?? "—"}</td>
                          <td>
                            {r.details.length === 0 && "—"}
                            {r.details.map((d, j) => (
                              <div key={j} className="finding">
                                <Badge kind={d.risk_type || d.kind || "generic"} />
                                <code>{(d.content || d.text || "").slice(0, 60)}</code>
                              </div>
                            ))}
                          </td>
                          <td>
                            {r.redacted ? <span className="badge badge-green">censurado</span>
                              : r.risky ? <span className="badge badge-red">riesgo</span>
                              : <span className="badge badge-dim">ok</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                <details className="json-details">
                  <summary>reporte JSON completo</summary>
                  <pre>{JSON.stringify(result.report, null, 2)}</pre>
                </details>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
