// Panel de REPORTE: gráficas ligeras (SVG/CSS, sin librerías).
//  - Cumplimiento de la imagen actual: qué "cumple" (sin riesgo) vs "no cumple".
//  - Desglose por tipo de hallazgo.
//  - Historial de detección de la sesión.

const KIND_LABEL = {
  qr_code: "QR", id_card: "ID / tarjeta", document: "documento", screen: "pantalla",
  handwritten_text: "manuscrito", sticky_note: "post-it",
  name: "nombre", date: "fecha", email: "email", card: "tarjeta nº",
  credential: "credencial", login: "usuario", id_pa: "cédula",
  leaked_pwd: "contraseña filtrada", weak_pwd: "contraseña débil",
};

function Donut({ safe, risky }) {
  const total = safe + risky;
  const R = 52, C = 2 * Math.PI * R;
  const riskyLen = total ? (risky / total) * C : 0;
  const pct = total ? Math.round((safe / total) * 100) : 100;
  return (
    <svg viewBox="0 0 130 130" className="donut" role="img"
         aria-label={`cumplimiento ${pct}%`}>
      <circle cx="65" cy="65" r={R} className="donut-track" />
      {/* arco verde (cumple) ocupa el resto; rojo (riesgo) al frente */}
      <circle cx="65" cy="65" r={R} className="donut-safe"
              strokeDasharray={`${C} ${C}`} />
      <circle cx="65" cy="65" r={R} className="donut-risk"
              strokeDasharray={`${riskyLen} ${C}`} transform="rotate(-90 65 65)" />
      <text x="65" y="60" className="donut-num">{total ? risky : 0}</text>
      <text x="65" y="80" className="donut-lbl">
        {total ? "en riesgo" : "limpia"}
      </text>
    </svg>
  );
}

function Bars({ items }) {
  const max = Math.max(1, ...items.map((i) => i.v));
  return (
    <div className="rp-bars">
      {items.map((it, i) => (
        <div key={i} className="rp-bar-row">
          <span className="rp-bar-lbl">{it.k}</span>
          <div className="rp-bar-track">
            <div className="rp-bar-fill" style={{ width: `${(it.v / max) * 100}%` }} />
          </div>
          <span className="rp-bar-val">{it.v}</span>
        </div>
      ))}
    </div>
  );
}

export default function Report({ result, history }) {
  const total = result?.total_detections ?? 0;
  const risky = result?.risky_count ?? 0;
  const safe = Math.max(0, total - risky);
  const alerts = result?.alerts?.length ?? 0;

  // desglose por tipo (clase de cada item del reporte)
  const counts = {};
  (result?.report || []).forEach((r) => {
    counts[r.class] = (counts[r.class] || 0) + 1;
  });
  const kinds = Object.entries(counts)
    .map(([k, v]) => ({ k: KIND_LABEL[k] || k, v }))
    .sort((a, b) => b.v - a.v)
    .slice(0, 7);

  const hMax = Math.max(1, ...history.map((h) => h.risky));

  return (
    <div className="report">
      <h3 className="rp-title">📊 Reporte</h3>

      {result && (
        <div className="rp-grid">
          <div className="rp-card">
            <p className="rp-card-h">Cumplimiento de la imagen</p>
            <Donut safe={safe} risky={risky} />
            <div className="rp-legend">
              <span><i className="dot dot-green" /> cumple: {safe}</span>
              <span><i className="dot dot-red" /> no cumple: {risky}</span>
              {alerts > 0 && <span className="rp-alert">⚠ {alerts} alerta(s)</span>}
            </div>
          </div>

          <div className="rp-card">
            <p className="rp-card-h">Hallazgos por tipo</p>
            {kinds.length ? <Bars items={kinds} />
              : <p className="rp-empty">Sin hallazgos: imagen limpia ✔</p>}
          </div>
        </div>
      )}

      <p className="rp-card-h">Historial de detección (sesión)</p>
      {history.length ? (
        <div className="rp-history">
          {history.slice(-12).map((h, i) => (
            <div key={i} className="rp-hbar" title={`#${h.n} ${h.mode}: ${h.risky} en riesgo`}>
              <div className="rp-hbar-fill"
                   style={{ height: `${(h.risky / hMax) * 100 || 4}%` }} />
              <span className="rp-hbar-x">{h.n}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="rp-empty">Aún no hay análisis. Ejecuta ANALIZAR para empezar el historial.</p>
      )}
    </div>
  );
}
