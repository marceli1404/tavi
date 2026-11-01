---
name: tavi-web-design
description: Design, build, audit, and refine exceptional, distinctively art-directed websites and web applications. Use for premium landing pages, product websites, portfolios, editorial experiences, responsive UI, visual design systems, and purposeful animation or interactive 3D. Preserve existing product behavior and user constraints; do not use merely for ordinary routing decisions.
---

# Tavi Web Design & Motion — unified skill

Produce a **working, distinctive, coherent website**, not just attractive screenshots. This skill merges premium/award-level visual direction with the practical animated Tavi showcase: kinetic type, scroll reveals, Canvas artwork, creative project grids, interactive micro-feedback, and three motion modes.

## Activate for
New website/page creation; redesigns; hero and landing page design; brand/typography/layout systems; interactive product experiences; front-end polish; motion, scroll storytelling, and 2D/3D creative coding; website UX and visual audits. Do not activate for unrelated tasks.

This is a **design and implementation skill**, distinct from the existing `tavi-decision` model/skill-routing skill. Tavi does not automatically execute it, retrain a model, or change an installed skill inventory merely because this folder exists in the repo. Install this folder into a configured skill root and refresh discovery as needed.

## Order of precedence
1. User requirements, existing business logic, brand guidelines, and accessibility needs.
2. Functional correctness, content clarity, privacy/security, accessibility, and performance.
3. Cohesive art direction and purposeful interaction.
4. Optional experimental effects; never compromise 1–3 for visual spectacle.

## Required context capture
Read the existing app and UI before changing it. Identify the audience, conversion/action, brand/personality, content, platform and constraints. Preserve actual routes, forms, auth, analytics, SEO, data, and responsive behavior. If no brief exists, choose sensible, explicitly identified creative defaults instead of repeatedly blocking on questions. Never invent client names, case studies, metrics, or testimonials.

## Workflow (follow in order)

### 1. Audit and direction
- Inventory the current stack and components, pages, responsive behavior, assets, dependencies, accessibility and any visual references.
- Define one experience thesis: **"For [audience], this website should feel [3 adjectives] and make [primary action] obvious."**
- Select one primary style from `references/design-system.md`: *precision minimal*, *expressive SaaS*, *editorial luxury*, *cinematic immersive*, or *playful experimental*. Mix only with a rationale.
- Explain the distinguishing visual motif: signature type treatment, composition, shape language, photography, illustration, or interface metaphor. Do **not** copy another brand's trademarks/assets or impersonate its live site.

### 2. Design the system before sections
- Specify type pairings and scale, spacing/grid, semantic color tokens, surface/border treatment, imagery, icons, radii and breakpoints. Use at most a few meaningful fonts, not a different font for every region.
- Write the headline, supporting copy and CTA **for the actual user goal**, not placeholder hype.
- Create a page skeleton with purposeful variation: signature hero, evidence/benefit, demonstration, detail, trust, clear next step. Content order may differ by use case.
- Start mobile composition deliberately, not as a clipped desktop version.

### 3. Build a working, progressively enhanced experience
- Use semantic HTML and accessible components. Choose the existing project's framework and styling conventions. Do not introduce React, GSAP, Three.js, or WebGL just to reproduce a CSS interaction.
- Implement real navigation, functional controls and correct empty/loading/error/success states.
- Add purposeful motion using `references/motion-interactions.md` and the self-contained `examples/showcase.html`. The demo is a **mechanism library, not a visual template**: avoid copying its lime palette, torus, slogans or fictional work unless specifically requested.
- Prefer native CSS transitions/keyframes + IntersectionObserver + requestAnimationFrame where adequate. For complex sequencing use installed Motion/GSAP; for genuinely meaningful immersive scenes consider Canvas/WebGL with static fallbacks.
- Make core content visible without JS. No animations may trap focus, delay a primary CTA, or conceal meaningful information when JS fails.

### 4. Critique and iterate
- Capture desktop/mobile screenshots where a browser or test runner is available, and review **actual rendering**. Inspect type wrapping, hierarchy, contrast, image crops, margins, navigation, interaction states and visual consistency.
- Critique against the 100-site reference principles: intentional art direction, coherent typography, crisp layout, readable copy, thoughtful motion, usability, performance.
- Fix obvious template signals: uniform card grids everywhere, random glow/orbs, gratuitous glassmorphism, meaningless animated blobs, pseudo-premium copy, cramped hero, tiny gray body text, placeholder links, and generic icon soup.
- Test keyboard paths, touch, zoom, reduced motion, 320/375/768/1024/1440px layouts, and low-power fallbacks. Follow `references/quality-gates.md`.

### 5. Deliver
Provide working source code, changes to existing project, instructions to run, a brief explanation of design rationale, interaction list, limitations, and a transparent checklist of *tested* versus *not tested*. Provide a screenshot/preview when actually generated. Do not claim performance scores, awards, WCAG conformance or production deployment without evidence.

## Non-negotiable quality gates
- Useful first screen: identify subject, value and primary action; navigation remains discoverable.
- Distinctive **design system**, consistent across all sections rather than a polished hero followed by default cards.
- Responsive layout with **no horizontal overflow** at common narrow widths.
- Keyboard-operable navigation, visible focus, semantic headings, text alternatives, accessible form labels, suitable contrast, reduced-motion support.
- Content visible without JavaScript; decorative Canvas/3D must have static or skipped fallback.
- Performance-minded images, fonts, motion and event listeners; avoid scroll-layout thrash and gratuitous large packages.
- No fake claims, fake metrics, dead CTAs, or concealed user-critical state.

## Motion tiers
**Essential**: focus/pressed/loading feedback and clear state transitions (must remain usable when motion is off).
**Enhancement**: restrained entrances, stagger, hover cues, subtle marquee, parallax (only when justified; off/reduced fallback).
**Experimental**: particle fields, interactive generative art, WebGL/3D, page morphs and cinematic sequences (opt-in, budgeted, pausable, irrelevant to task completion).

The demo offers `alive`, `calm`, `off` with operating-system reduced motion taking precedence. Implement the same policy for expressive concepts, but do not require a motion-toggle UI on every conventional site.

## Reference map
- [Design system & five art directions](references/design-system.md)
- [Animation and interaction patterns](references/motion-interactions.md)
- [Quality gates and testing](references/quality-gates.md)
- [Creative brief & handoff](references/creative-brief.md)
- [Curated inspiration, with caution about awards](references/inspiration.md)
- [Working animated showcase](examples/showcase.html) and [example notes](examples/README.md)

## Example invocation
> Use `$tavi-web-design` to redesign a cybersecurity SaaS homepage with expressive SaaS art direction, authoritative typography, visible real product screenshots, subtle progressive scroll reveals and an optional lightweight Canvas hero. Preserve signup/auth routes, make everything keyboard-accessible, support reduced motion, and deliver working code plus mobile tests.

## Installation / compatibility
This folder is a **portable, instruction-based agent skill**: install by copying `skills/tavi-web-design` into one of the skill roots in `tavi.config.json` (e.g. `~/.codex/skills/tavi-web-design` or `~/.agents/skills/tavi-web-design`). Its instructions are for the selected coding agent to follow. The Tavi local router does not automatically learn this new label; existing trained weights and routing acceptance remain unchanged. Specify `--skill tavi-web-design` when appropriate if your configured routing flow supports explicit skill selection.