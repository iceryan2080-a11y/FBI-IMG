import useReveal from "../useReveal.js";

const SERVICES = [
  { name: "frontend", tech: "React + nginx", desc: "Esta interfaz. Proxy /api → backend." },
  { name: "backend", tech: "FastAPI + YOLO11 + EasyOCR + OpenCV", desc: "Orquestador: detecta, lee y difumina." },
  { name: "qr-service", tech: "FastAPI + pyzbar", desc: "Decodifica QR aislado, sin puerto expuesto." },
  { name: "trainer", tech: "Ultralytics", desc: "Fine-tuning del modelo propio (perfil aparte)." },
];

export default function Architecture() {
  const ref = useReveal();
  return (
    <section className="section" id="arquitectura">
      <div className="section-inner reveal" ref={ref}>
        <h2 className="section-title">Arquitectura</h2>
        <p className="section-sub">
          Cuatro microservicios en una red Docker interna (<code>fbi-net</code>). Sin llamadas a internet en runtime.
        </p>
        <div className="arch">
          {SERVICES.map((s, i) => (
            <div className="arch-item" key={s.name}>
              <article className="card arch-card" style={{ transitionDelay: `${i * 120}ms` }}>
                <h3 className="mono">{s.name}</h3>
                <p className="arch-tech">{s.tech}</p>
                <p>{s.desc}</p>
              </article>
              {i < SERVICES.length - 1 && <span className="arch-arrow">→</span>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
