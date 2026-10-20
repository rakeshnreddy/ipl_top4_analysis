# Final accessibility evidence review

20 October 2026. Production contrast capture: `4089f17`, Chromium, 375px and 1280px, light and dark, six page families plus four NBA neutral-chart samples. No product changes were made by this reviewer.

**Scoped result:** all 272 measured text pairs met the applicable AA contrast threshold; the minimum was **5.089:1 light** and **5.753:1 dark**. All four informative neutral-bar samples exceeded 3:1. These are representative measurements, not whole-site WCAG certification.

## Rendered contrast

Foreground RGBA came from computed styles. Screenshots hid glyph ink without removing layout, surface fills, ambient gradients or backdrop blur. The minimum ratio was sampled on a 2px grid within visible text ranges. Neutral fills were compared with screenshots of the same coordinates with only that bar hidden. Selectors, fonts, coordinates, colors and screenshot paths are in [the measurement artifact](../release/rendered-contrast.json).

| Representative pair/state | Light minimum | Dark minimum |
| --- | ---: | ---: |
| Wordmark over translucent sticky header | 15.979:1 | 15.392:1 |
| Header league control | 16.293:1 | 15.375:1 |
| Selected menu row over alpha accent fill | 5.902:1 | 11.074:1 |
| Hovered menu row | 13.574:1 | 11.801:1 |
| Landing feature note on its opaque plane | 6.349:1 | 7.495:1 |
| Hovered landing feature link | 6.743:1 | 13.823:1 |
| Status text, 12px | 5.089:1 | 5.753:1 |
| Measured table column label | 5.809:1 | 6.830:1 |
| Selected team name | 14.263:1 | 12.317:1 |
| Archived Share warning text | 13.963:1 | 11.597:1 |
| Neutral histogram fill, including grid-line background | 4.863:1 | 5.259:1 |

The neutral fill is `#506175` in light and `#9eafc1` in dark. The lowest measured backgrounds were the actual grid lines `#dce2e8` and `#2b3947`. At desktop samples over the solid plot plane, the ratios were 6.349:1 and 7.495:1. Twelve team-color chip samples remain decorative: all are `aria-hidden="true"` beside written names. Their sometimes lower contrast is not counted as an informative-graphic or text pass.

## Manual ARIA review

The targeted `aria-prohibited-attr` run had zero violations on all six families and one incomplete node: `.cricket-champion`, `<div class="cricket-champion" aria-label="IPL 2026 champions">`. Axe identifies an unsupported naming attribute on a generic div. Its visible “2026 champions” context and champion name already supply the information. The lead removed the redundant `aria-label` locally after this capture. Fresh 303 Python tests (one skip), 120 Vitest tests, lint and both builds pass. All 24 affected cricket cases pass across both bases, Chromium/WebKit, 320/375/1280px and both themes; the incomplete rule is absent in all 24. See [repair evidence](../release/champion-aria-followup.json). The production revision captured here still contained the original attribute; the lead owns the post-deployment smoke.

## Limits and prior evidence

Eight compound table-header selectors had no direct text node and were skipped. Other league-warning states, tiny/subpixel bars, raster social-image text, every ambient position, screen-reader behavior and forced colors are not certified by this probe. The landing feature is opaque; the header supplies the measured translucent plane. Two initially over-wide ellipsized EPL text ranges were corrected by clipping to their visible container before sampling.

The old [foundation review](foundation-review.md#findings-resolved-during-review) contains deterministic solid-pair ratios of 6.35:1/7.50:1 for neutral bars. Its [visual review](foundation-visual.md#representative-evidence) explicitly infers no contrast ratios from screenshots. Existing zero-violation axe matrices, including incomplete contrast nodes, remain automated evidence rather than a full contrast certificate.
