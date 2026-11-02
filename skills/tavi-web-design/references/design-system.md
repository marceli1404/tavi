# Design system and art direction

Build **one recognizable visual language**: aesthetic ambition comes from art direction, composition and execution, not accumulating effects.

## Five modes

| Mode | Identity | Layout and type | Motion | Use when |
| --- | --- | --- | --- | --- |
| Precision minimal | quietly confident, exact | restrained palette, tight grid, strongly edited type | low, brief state feedback | dashboards, tools, serious B2B |
| Expressive SaaS | energetic, technical, trustworthy | graphic hero, controlled contrast, legible product screenshots | reveal, state demos, subtle reactive detail | software, dev tools, AI |
| Editorial luxury | tactile, sophisticated, spacious | distinctive serif/sans pairing, whitespace, strong photography | slow, deliberate transitions | fashion, lifestyle, premium services |
| Cinematic immersive | narrative, atmospheric, dramatic | full-bleed visual scenes, sequenced chapters, deliberate contrast | spatial/parallax/Canvas, skip option | stories, campaigns, experiential brands |
| Playful experimental | surprising, distinctive, delightful | asymmetric layout, illustrations, unexpected but meaningful interactions | playful gestures, interactive exploration | creative studios, portfolios, festivals |

Pick one dominant mode. Never mistake a strong brand for one universal color palette.

## Tokens and layout
- Use semantic tokens (`--bg`, `--fg`, `--accent`, `--muted`, `--border`, `--surface`) with dark/light variants only when design requires.
- Define 4–8 purposeful spacing steps, a max content width, and fluid gutters. Example: `width: min(100% - clamp(2.75rem, 9vw, 10.5rem), 90rem)`; adapt values rather than blindly reuse.
- Use an editorial typography scale based on `clamp()` for display and headlines; body text usually about 16–18px (context-dependent), line-height typically 1.4–1.7, adequate measure, robust line breaking.
- Avoid accidental typography: specify widths, wrapping, letter spacing only where legible; don't set strong negative tracking on small body copy.
- Use layout rhythm: alternate quiet and expressive chapters for attention, but preserve alignment rules. Asymmetry should look intentional, not broken.
- Set icon stroke/weight and corner geometry as design tokens; mix illustration and photos only with clear art direction.
- Every interactive element has default, hover (where appropriate), focus, active, disabled, pending/error and success states.
- Respect touch targets and avoid hover-only information; always accommodate zoom and increased text spacing.

## Composition recipe
1. First viewport has a visual thesis, a clear headline and one dominant call to action.
2. Establish a motif: interesting type composition, border vocabulary, spatial depth, photographic crop, ornamental grid, or interactive metaphor.
3. Use contrast in **scale**, **density** and **tempo** across sections, not merely alternating backgrounds.
4. Show evidence: real screenshots, credible examples, specific capabilities, or real work. No fake logos or numbers.
5. End with a next step tailored to audience; don't bury the actual action under animation experiments.

## Anti-generic critique
Ask: Could a hundred unrelated businesses use this exact hero after swapping the logo? If yes, revise. If an animation is removed, does the composition still look authored? If no, improve the static layout. If the design's visual language disappears beyond the hero, unify the whole page. If every section is a three-card grid, rebuild section composition around content.

## Tavi demonstration, abstracted
The showcase applies one lime/coral-on-dark expression, oversized type with italic editorial contrast, an offset generative woven torus, varied asymmetrical project presentations, motion studies, and a functional brief builder. **Learn its principles, not its brand.** Map the decisions into appropriate new tokens and motifs for each client.

## Responsive composition
- Design 320px as a valid minimum, with tested intermediate widths and orientation changes.
- Reframe oversized hero artwork on mobile; do not position the subject entirely offscreen.
- Reorder content based on narrative meaning, not just column stacking.
- Make hero type fluid with limits, and protect words/lines from accidental cropping.
- Test real menus, dialogs and forms on touch, keyboard and small viewports.

## Choosing technology
- Static HTML/CSS/JS for self-contained marketing pages and demos.
- Existing React/Next/Vue/Svelte when already in repo; retain its routing and component patterns.
- Motion/Framer Motion for component and layout transitions if dependency already available or justified.
- GSAP/ScrollTrigger only for advanced timed scenes after establishing scroll semantics and fallbacks.
- SVG, CSS and 2D Canvas before WebGL; Three.js/react-three-fiber only when spatial interaction serves the goal and device budgets permit.