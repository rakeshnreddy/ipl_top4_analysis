# Foundation visual review

18 October 2026. Independent image review of all **24** foundation viewport screenshots: landing, hub, football, cricket, F1 and share kit, each at 375px and 1280px in light and dark. Also compared eight representative baseline frames from `docs/screenshots/before`. Images were opened with `view_image`; this is a visual judgment, not a substitute for the lead worker's measured contrast, DOM overflow, keyboard or performance checks.

**Verdict: PASS for the foundation PR.** No visual blocker was found in the captured frames. The opaque data planes, brighter neutral text, clear table headers, contained team colours and controlled sport-accent rules are a sound base. The citron mark/CTA reads as a stronger brand cue than the former plain jade pulse icon. Both themes look intentional. The foundation still inherits the old page compositions; page-family work is necessary to deliver the requested visual transformation.

## Findings

| Page / element | Severity | Rendered evidence | Recommendation / ownership |
| --- | --- | --- | --- |
| Shared surfaces | Positive | In football/F1 desktop light, the white table separates sharply from a cool neutral ground. Dark slate panels retain borders and numerical hierarchy without the baseline's green/amber background tint. | Preserve solid table planes. Keep glass limited to small feature/header surfaces. |
| Shared brand | Positive | Citron mark and action are immediately recognisable in the dark landing; the light version is deep olive with white button text. | Keep success mint and championship amber distinct from brand. Do not use citron as a generic data colour for all charts. |
| Sport accents | Positive | F1 has a coral top rule, cricket azure; football retains brand citron. The short rail gives identity without colouring the table surface. | Keep this restrained and add text alongside any sport identity mark. |
| League headers, 375px | **P2, family work** | Football table panel begins around y=517px versus y=476px before; F1 around y=564px. Title, four facts, navigation and new rails consume substantial first-screen space. Rows are visible in the first screen, but fewer than before. | Compact the phone fact strip, update text or headings in the family PRs. Avoid adding another large summary above the main table. |
| Football table, 375px | **P2, family work** | The rightmost relegation column is clipped at the inner table edge and only “DR…” is visible in the captured first state. This appears to be contained horizontal table scrolling, not page overflow. | Add a visible scroll affordance and consider a race/column focus control. Pin team identity if the table scrolls. Verify the rightmost data through real interaction. |
| Generic position chart, desktop | **P2, already audited** | The selected City distribution has a tall first bar followed by a long citron hairline tail; no probability axis/value is visible. Bright minimum-height tails give tiny probabilities more weight. | Repair chart scale/floors and expose the modal probability during sport-page work. The foundation should not lock this treatment in as a reusable chart primitive. |
| Landing, both themes | **P2, family work** | Composition is unchanged from baseline: long 3-line desktop headline, long lede, six text-only football races, then a coverage grid. On phone, meaningful race data begins near y=567px. The new palette alone does not create a hero focal point. | Replace with a shorter editorial headline and one real-data race feature, then a compact cross-sport selection. Keep the real numbers and timestamp prominent. |
| Hub, 375px | **P2, family work** | The introductory coverage paragraph occupies roughly six lines before the facts. The first league card starts near y=554px. On desktop the page is a uniform four-column card wall. | Shorten the lede to one concise sentence and use sport filtering. Create one focal area rather than increasing decorative effects. |
| Shared header control, 375px | **P3** | Current-league/Leagues button appears medium grey in multiple phone captures, much brighter than the surrounding dark header and close to a disabled-control appearance in light mode. Desktop resting control is outlined. This may be capture hover state. | Inspect hover/active/pointer placement; use a calmer raised surface while preserving its interactive affordance. Not a blocker. |
| Share kit | **P2, family work** | Archived May 24 graphics are very prominent under a current October header. The warning is legible in both themes but the section still says “Today's Race” and “newest slide pack”. | Make the archived state explicit in the heading and thumbnails; maintain the warning adjacent to download actions. |
| Cricket completed state | Positive, then P3 | Final table and playoff results are immediately legible on desktop. Mobile displays the champion/runner-up facts and several table rows without overlapping text. | Preserve this density. Add a controlled champion feature within the existing hierarchy rather than a tall ceremonial banner above the table. |

## Representative evidence

The full matrix lives beside these files. All six page types and both themes were inspected at both required widths.

| Page | Foundation light / dark at 375px | Foundation light / dark at 1280px |
| --- | --- | --- |
| Landing | [light](../screenshots/foundation/landing-light-375.png) / [dark](../screenshots/foundation/landing-dark-375.png) | [light](../screenshots/foundation/landing-light-1280.png) / [dark](../screenshots/foundation/landing-dark-1280.png) |
| Hub | [light](../screenshots/foundation/hub-light-375.png) / [dark](../screenshots/foundation/hub-dark-375.png) | [light](../screenshots/foundation/hub-light-1280.png) / [dark](../screenshots/foundation/hub-dark-1280.png) |
| Football | [light](../screenshots/foundation/football-light-375.png) / [dark](../screenshots/foundation/football-dark-375.png) | [light](../screenshots/foundation/football-light-1280.png) / [dark](../screenshots/foundation/football-dark-1280.png) |
| Cricket | [light](../screenshots/foundation/cricket-light-375.png) / [dark](../screenshots/foundation/cricket-dark-375.png) | [light](../screenshots/foundation/cricket-light-1280.png) / [dark](../screenshots/foundation/cricket-dark-1280.png) |
| F1 | [light](../screenshots/foundation/f1-light-375.png) / [dark](../screenshots/foundation/f1-dark-375.png) | [light](../screenshots/foundation/f1-light-1280.png) / [dark](../screenshots/foundation/f1-dark-1280.png) |
| Share kit | [light](../screenshots/foundation/share-light-375.png) / [dark](../screenshots/foundation/share-dark-375.png) | [light](../screenshots/foundation/share-light-1280.png) / [dark](../screenshots/foundation/share-dark-1280.png) |

These are viewport screenshots. They do not prove below-the-fold layout, loading/error states, chart hover/focus behaviour, or the absence of DOM overflow. No measured contrast ratios are inferred from appearance.

