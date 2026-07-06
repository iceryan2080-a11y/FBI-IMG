import useReveal from "../useReveal.js";

const MODES = [
  {
    icon: "⚡",
    name: "ligero",
    title: "Ligero",
    desc: "Detección YOLO11 de zonas sensibles + decodificación y clasificación de riesgo de códigos QR (WiFi, URLs, credenciales).",
  },
  {
    icon: "🔍",
    name: "medio",
    title: "Medio",
    desc: "Todo lo anterior + OCR (EasyOCR es/en) sobre documentos, pantallas y notas, con regex de contraseñas, correos, tarjetas y cédulas.",
  },
  {
    icon: "🛡️",
    name: "completo",
    title: "Completo",
    desc: "Todo lo anterior + censura automática: blur gaussiano de OpenCV sobre cada zona de riesgo antes de devolver la imagen.",
  },
];

export default function ModeCards() {
  const ref = useReveal();
  return (
    <section className="section" id="como-funciona">
      <div className="section-inner reveal" ref={ref}>
        <h2 className="section-title">¿Cómo funciona?</h2>
        <p className="section-sub">Tres modos de análisis, de más rápido a más exhaustivo.</p>
        <div className="cards">
          {MODES.map((m, i) => (
            <article className="card" key={m.name} style={{ transitionDelay: `${i * 120}ms` }}>
              <span className="card-icon">{m.icon}</span>
              <h3 className="mono">{m.title}</h3>
              <p>{m.desc}</p>
              <code className="card-mode">mode={m.name}</code>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
