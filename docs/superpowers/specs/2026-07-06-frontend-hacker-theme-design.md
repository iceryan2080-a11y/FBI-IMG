# Rediseño frontend FBI-IMG — estética hacker/cybersecurity

**Fecha:** 2026-07-06 · **Estado:** aprobado por el usuario

Diseño original inspirado en la estética de sitios de academias de ciberseguridad
(dark + verde neón + partículas). No se copia código, textos ni assets de terceros.

## Paleta y tipografía
- Fondo: `#0d0f12` (base) / `#1a1b1e` (paneles)
- Acento: verde `#22c55e` con glow; riesgo: ámbar `#fbbf24` / rojo `#ef4444`
- Texto: `#e4e4e7` primario, `#9ca3af` secundario
- Fuentes: Inter (UI) + JetBrains Mono (terminal), vía `@fontsource` empaquetadas
  localmente (sin CDN — coherente con "privacy by design" del proyecto)

## Estructura (landing de una página)
1. **Navbar** sticky translúcida (backdrop blur), logo `●_ FBI-IMG`, anchors.
2. **Hero**: canvas de partículas conectadas, h1 con efecto typing + cursor,
   subtítulo, CTA con glow-pulse → scroll a la herramienta.
3. **Herramienta** (`#herramienta`): panel ventana-terminal (3 puntos, título),
   dropzone drag&drop, tabs de modo (ligero/medio/completo), botón ANALIZAR,
   loading con barra + scanline. Resultado: toggle antes/después, contadores
   animados, tabla de hallazgos con badges de riesgo, JSON colapsable.
4. **Cómo funciona** (`#como-funciona`): 3 cards de modos, hover lift+glow,
   reveal al scroll.
5. **Arquitectura** (`#arquitectura`): 4 cards de microservicios con flujo.
6. **Footer**: AGPL-3.0 + stack.

## Animaciones
Partículas canvas vanilla (desactivadas con `prefers-reduced-motion`), typing en
hero, glow-pulse en CTA, fade-up reveal con IntersectionObserver, hover lift en
cards, contadores incrementales, scanline durante análisis.

## Arquitectura de código
- `src/styles.css`: variables CSS + keyframes + estilos por sección
- `src/components/`: `Particles`, `Navbar`, `Hero`, `AnalyzerPanel`,
  `ModeCards`, `Architecture`, `Footer` — un componente por sección
- `src/useReveal.js`: hook IntersectionObserver reutilizable
- `src/App.jsx`: solo composición
- `src/api.js`: sin cambios (contrato backend intacto)

## Sin cambios
Backend, qr-service, trainer, nginx, docker-compose. Solo `frontend/`.

## Verificación
`docker compose build frontend && up -d frontend` → :8080 sirve, análisis
end-to-end funciona igual que antes, animaciones visibles, sin errores consola.
