# Quality gates: inspect before calling the result finished

A site can be visually unusual and still be unusable. Prioritise **functional experience** and measurable constraints.

## Required verification matrix
| Dimension | Check | Evidence to provide |
| --- | --- | --- |
| Content | Clear subject, proposition, differentiated audience value, primary CTA | screenshot and copy review |
| Layout | 320, 375, 768, 1024, 1440px, long text, zoom and orientation | screenshots/viewport report |
| Navigation | Mouse/touch/keyboard, tab order, mobile menu, anchors, Escape for dialogs | tested flows |
| Semantics | One useful H1, logical headings, landmarks, labels, meaningful text alternatives | manual DOM review |
| Focus | Visible indicator, no keyboard traps, focus retained/restored for interactive overlays | keyboard walkthrough |
| Contrast | WCAG 2.2 AA: normal text 4.5:1; large text 3:1 where applicable; UI component contrast 3:1 | evaluated foreground/background pairs |
| Motion | OS reduced motion, user off, scene offscreen, hidden tab | tested preferences and events |
| Forms | Real submission/copy behavior, error/loading/success, useful validation, no pretend endpoints | manual validation |
| Media | Correct image aspect, alt or decorative silence, responsive sizes and lazy loading | inspect network/DOM |
| Performance | Field data where available; lab data clearly labeled | report, not assumptions |
| SEO | Descriptive title/meta, indexable copy, clear headings, meaningful links; canonical/social tags when applicable | inspect rendered head |
| Safety | No secrets in client, exposed API keys, unlicensed assets or misleading testimonials | source review |
| Existing app | Authentication, routing, analytics, data logic and feature tests preserved | regression results |

## Performance targets (field data at p75)
- Largest Contentful Paint **<=2.5s**.
- Interaction to Next Paint **<=200ms**.
- Cumulative Layout Shift **<=0.1**.

These are Google Core Web Vitals "good" thresholds, *targets*, not guarantees. Performance can vary with network/device; report the tool, environment, URL, date and data source used. Test assets/font timing and loading behavior. An attractive screenshot does not establish a Lighthouse score.

## Accessibility
Follow **WCAG 2.2 AA** as a target. Test keyboard, focus state, screen reader where possible, 200% zoom, 400% reflow where applicable, interactive target size/spacing, status announcements, and motion safety. Automated axe/Lighthouse scans supplement but do **not** replace manual testing. Do not claim verified AA compliance without meaningful review.

## Structured design review rubric (100 points)
- Art direction and original identity — 20
- Hierarchy, typography and composition — 20
- User journeys and functional clarity — 20
- Accessibility and mobile responsiveness — 15
- Performance and engineering — 15
- Purposeful motion and interaction quality — 10

Score observed evidence only. A perfect-looking hero cannot rescue broken navigation; critical failures mean **not ready**, irrespective of average score.

## Release block / no-go conditions
- Navigation, primary CTA or form cannot complete its actual intended action.
- Horizontal overflow, clipped text or inaccessible controls on a supported screen width.
- Content hidden without JS, reduced-motion option unusable, keyboard-inaccessible key interactions.
- Serious contrast failures, missing form labels, focus traps or seizure/vestibular-risk effects.
- Fake content presented as fact or significant regression of existing product behavior.
- Baseless claims of performance, awards, accessibility compliance or live deployment.

## Recommended checks
- Static: lint, typecheck, unit tests relevant to repo, markup and CSS inspection.
- Browser: smoke navigation, screenshot at multiple widths, Lighthouse and axe where available, keyboard-only walkthrough, reduced-motion.
- Inspect long-page rhythm and all key component states, not only the hero.
- State what was executed, what remains untested and why.