import { useEffect, useState } from "react";
import Particles from "./Particles.jsx";

const PHRASE = "Detecta y censura datos confidenciales en imágenes.";

export default function Hero() {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setTyped(PHRASE);
      return;
    }
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setTyped(PHRASE.slice(0, i));
      if (i >= PHRASE.length) clearInterval(id);
    }, 45);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="hero" id="top">
      <Particles />
      <div className="hero-content">
        <p className="hero-kicker">// visión artificial + OCR + análisis de QR</p>
        <h1 className="hero-title">
          {typed}
          <span className="cursor">█</span>
        </h1>
        <p className="hero-sub">
          QR con credenciales, contraseñas en post-its, documentos y pantallas:
          FBI-IMG los encuentra con YOLO11 y los difumina antes de que salgan de tu red.
        </p>
        <div className="hero-actions">
          <a className="btn-primary" href="#herramienta">▶ Probar ahora</a>
          <a className="btn-ghost" href="#como-funciona">Ver cómo funciona</a>
        </div>
        <p className="hero-badges">
          <span>100% local</span>
          <span>CPU-friendly</span>
          <span>AGPL-3.0</span>
        </p>
      </div>
    </section>
  );
}
