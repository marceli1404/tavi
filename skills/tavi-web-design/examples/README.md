# Tavi showcase — functioning reference implementation

Open `showcase.html` in a browser. It is a self-contained **concept site**, not a production Tavi website, with inline CSS/JS and an optional Google Fonts request. It uses no npm packages or CDN animation libraries.

Observe how design decisions relate to implementation:
- oversize kinetic editorial type + responsive scaling;
- pointer-reactive projected Canvas torus (2D, not WebGL);
- asymmetrical fictional project gallery and section pacing;
- scroll reveals, decorative marquee and magnetic button;
- Calm / Alive / Off motion modes with operating-system reduced motion taking precedence;
- keyboard-operable mobile navigation and functional copy-to-clipboard creative brief generator;
- non-JS content visibility and static-art fallback.

**Do not use this page as a universal website template.** Its lime/coral palette, exact artwork, slogans and fictional projects are for demonstration only. Reinterpret the underlying choices for each product.

Local run:
```sh
python -m http.server 8080
# open http://localhost:8080/skills/tavi-web-design/examples/showcase.html
```

Launch notes: the showcase was browser-smoke-tested during its creation, but this repo addition does not imply a new comprehensive production audit, live deployment or Lighthouse certification. Replace fictional content and validate accessibility, responsiveness and performance for real use.