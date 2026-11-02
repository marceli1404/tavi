# Creative brief, delivery contract and example prompts

Use brief discovery to make a confident creative direction rather than ask users a dozen cosmetic questions.

## Minimum creative brief
- **Site/product:** real name and category.
- **Audience and job:** who visits and what should they do?
- **Primary CTA:** one most important conversion/action.
- **Brand posture:** three desired adjectives and what *not* to look like.
- **Content and proof:** real features, images, screenshots, claims, legal requirements.
- **Existing stack:** framework, route layout, components, auth, analytics, integrations.
- **Constraints:** schedule, devices, performance, accessibility, motion preferences.
- **Reference direction:** 2–4 examples, which properties to learn rather than copy.
- **Expected delivery:** working source, preview, tests, branch/PR when authorized.

If details are missing, make safe explicit assumptions and implement useful foundations; don't invent company results, customers or testimonials.

## Design proposal format
1. Concept line: **"The site should feel ... and enable ..."**
2. One primary aesthetic mode + a distinctive motif.
3. Tokens: typography, colors, spacing, layout, surfaces, imagery and interactions.
4. Page narrative: what each section contributes.
5. Motion plan: essential / enhancement / experimental with fallback and budget.
6. Implementation details: actual stack/components, functional UX.
7. Proof plan: visual, keyboard, responsive and performance checks.

## Before final handoff
Include: files changed, how to run, features preserved, feature/interaction demonstration, browser widths tested, keyboard and reduced-motion results, performance tools run (or explicitly not run), gaps and follow-up options.

## Example A — premium software website
> Apply `$tavi-web-design` to our existing cloud monitoring app. Design an expressive yet technically credible landing page: striking editorial typography, a real product dashboard screenshot, subtle scroll reveal and precise micro-interactions. Preserve existing auth/billing and make the free-scan CTA obvious. Build responsive HTML/React in the current stack, not an unconnected mockup. Include a mobile and reduced-motion test pass.

## Example B — experimental creative portfolio
> Apply `$tavi-web-design` for an original creative developer portfolio with playful experimental direction. Create a remarkable identity with one optional 2D Canvas interaction, carefully art-directed projects and a functional contact path. Support keyboard, touch and static reduced-motion mode. Avoid copying the Tavi example's torus, palette or fictional brands.

## Example C — restrained luxury
> Apply `$tavi-web-design` to create a high-end editorial boutique site. Focus on sophisticated typography, tactile imagery, whitespace and subtle hover/scroll transitions. No forced 3D, no autoplay audio and no animation that delays browsing. Preserve checkout behavior and make mobile shopping natural.

## Example D — motion retrofit
> Apply `$tavi-web-design` only to polish an existing dashboard. First audit current workflows; add navigational state feedback, tasteful panel transitions, loading/success/error states and reduced-motion fallbacks, without changing data behavior or installing a heavy animation package.

## Worked mini-brief: Tavi showcase
- Audience: developers and designers evaluating an expressive website design system.
- Desired feeling: ambitious / crafted / playful.
- Main proof: real Canvas hero, project compositions, micro-interactions, and a brief builder.
- Aesthetic: playful experimental with editorial composition and expressive typography.
- Enhancement: pointer-reactive 2D art, marquee, staggered reveal, magnetic button, kinetic type.
- Constraints: dependency-light HTML/CSS/JS, semantic navigation, visible content without JS, mobile + reduced-motion support.
- Result: `examples/showcase.html`, a runnable concept. Its featured clients and projects are fictional and must not be represented as case studies.