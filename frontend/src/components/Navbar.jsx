export default function Navbar() {
  return (
    <header className="navbar">
      <a className="brand" href="#top">
        <span className="brand-dot">●</span>
        <span className="brand-name">FBI-IMG</span>
        <span className="brand-cursor">_</span>
      </a>
      <nav>
        <a href="#herramienta">Herramienta</a>
        <a href="#como-funciona">Cómo funciona</a>
        <a href="#arquitectura">Arquitectura</a>
        <a className="nav-cta" href="#herramienta">Analizar</a>
      </nav>
    </header>
  );
}
