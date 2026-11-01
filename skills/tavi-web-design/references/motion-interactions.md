# Motion and interactive art playbook

Purposeful motion answers one of four questions: **What changed? Where should I look? What can I do? What is this brand's character?** Remove effects that answer none.

## Timing and easing (starting ranges, not universal laws)
| Pattern | Typical range | Notes |
| --- | --- | --- |
| Button hover/focus | 120–220ms | quick, never hide focus ring |
| Menu/panel | 160–320ms | preserve accessibility and escape behavior |
| Card lift/preview | 200–450ms | hover/focus parity; no critical data only on hover |
| Scroll reveal | 400–900ms | one-time and skip if reduced motion |
| Section transition | 450–1000ms | non-blocking; don't add artificial wait |
| Decorative loops | 6–24s | slow, pausable, can turn off outside viewport |

Use expressive easing sparingly, e.g. `cubic-bezier(.22,1,.36,1)`; use predictable ease for functional controls. Avoid bounce or vestibular triggers around primary content.

## Animation patterns
1. **Hero kinetic type**: animate line/word wrappers, not text content itself; preserve readable semantic text, copy/paste, selection and accessibility order. No empty/hiding hero while JS loads.
2. **Scroll reveal**: CSS opt-in only after JS initializes; observe once with `IntersectionObserver`. All content is visible by default and becomes visible if observer unsupported.
3. **Staggered sections**: reveal groups in narrative reading order; <=~80ms stagger per element when appropriate, no prolonged "waiting to read."
4. **Magnetic button**: decorative `transform: translate()` on fine pointer devices only; the true clickable hit area, keyboard focus and touch state remain fixed. Respect off/reduced.
5. **Marquee**: purely decorative, never the sole source of information; slow, optionally pausable and disabled in reduced motion.
6. **Parallax**: small movements on decorative layers only, not essential text/controls; avoid synchronous DOM measurement on every scroll event.
7. **Product demos**: provide accessible real controls or clear noninteractive playback; do not present pretend dashboards as functioning product.
8. **Page transitions**: preserve history, focus, URLs, busy/error states and scroll restoration. Don't animate a route for its entire load duration.
9. **3D/Canvas**: artwork as progressive enhancement; deterministic static poster/first frame; cap resolution and frame rate; stop on offscreen/hidden/reduced; make scene visually decorative (`aria-hidden`), with readable nearby copy.

## Reference implementation — one-time reveal

```css
[data-reveal] { opacity: 1; transform: none; }
html.motion-ready:not([data-motion="off"]) [data-reveal]:not(.is-visible) {
  opacity: 0; transform: translateY(1.25rem);
}
html.motion-ready [data-reveal] {
  transition: opacity .65s cubic-bezier(.22,1,.36,1),
              transform .65s cubic-bezier(.22,1,.36,1);
}
@media (prefers-reduced-motion: reduce) {
  html [data-reveal] { opacity: 1 !important; transform: none !important; transition: none !important; }
}
```
```js
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const targets = [...document.querySelectorAll('[data-reveal]')];
if (!reduced.matches && 'IntersectionObserver' in window) {
  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('is-visible'); io.unobserve(e.target); }
  }), { threshold: .08 });
  document.documentElement.classList.add('motion-ready');
  targets.forEach(el => io.observe(el));
} else targets.forEach(el => el.classList.add('is-visible'));
```

## Reference implementation — preference-safe motion policy
- Read `matchMedia('(prefers-reduced-motion: reduce)')` on load and on change.
- UI modes can be `alive`, `calm`, `off`, but the OS reduction request **always wins**. Do not persist a mode without permission, and don't let a toggle override OS preference.
- All nonessential animation must stop under `off`/OS reduction. Essential state changes must remain perceivable without relying on movement.
- Use `aria-pressed` for mode toggles and a visible explanation of what's changed.

## Canvas / generative hero, derived from demo
The reference `examples/showcase.html` implements an original 2D Canvas drawing of projected torus curves, with pointer-reactive rotation. Its implementation is instructive because it:
- uses no external 3D runtime;
- caps devicePixelRatio at 2, avoids repeated layout reads per frame and budgets decorative drawing (~20fps calm, ~38fps alive);
- uses IntersectionObserver + `document.hidden` to avoid painting hidden artwork;
- draws one static frame in the motion-off state;
- keeps actual headline, CTA and navigation in semantic DOM.

Do not copy the torus by default. Replace it with a concept appropriate to the audience, or omit it entirely.

## React libraries
For projects already using React, a `motion.div` entrance is reasonable with an existing Motion dependency; use a reduced-motion hook and keep semantic HTML. GSAP is suitable when sequencing truly complex narratives, but must clean up on unmount and avoid intercepting native scroll unless essential. Never add both libraries for a simple fade-in.

## GPU, accessibility and failure budgets
- Prefer `transform` and `opacity` over animating layout properties; avoid `filter: blur()` on giant layers.
- Use rAF for pointer/scroll updates; batch DOM reads and writes. No `getBoundingClientRect()` each frame unless necessary and measured.
- Respect `prefers-reduced-motion`, page visibility, low-power devices and inputs without hover; provide pause/stop for ongoing motion as required by context.
- Don't attach unbounded observers/listeners; disconnect observers and cancel RAF on teardown.
- Do not block reading, navigation, purchases or form submission with choreography. Avoid scroll-jacking.
- Verify interactiveness with a real browser; CSS hover animation alone is not proof of functionality.