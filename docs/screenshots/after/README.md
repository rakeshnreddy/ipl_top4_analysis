# Final production screenshots

Product revision: `4089f17249c90f248dd5b18e442fb835976f7489`. Capture: **2026-10-20 03:37:52–03:39:18 UTC** on [primary production](https://ipl-playoff-pulse.pages.dev/).

These 24 full-page PNGs are unchanged copies of the Chromium production captures in [verification-final-primary-legacy](../verification-final-primary-legacy/results.json): six page families, 375px and 1280px, light and dark. The legacy query routes were used for the directory and sport pages; Share Kit uses `share.html`. [Final visual review](../../audits/final-visual-review.md): **PASS**, no confirmed visual blocker in these captured states.

| Page | 375px light | 375px dark | 1280px light | 1280px dark |
| --- | --- | --- | --- | --- |
| Landing | [375px light](landing-light-375.png) | [375px dark](landing-dark-375.png) | [1280px light](landing-light-1280.png) | [1280px dark](landing-dark-1280.png) |
| League directory | [375px light](hub-light-375.png) | [375px dark](hub-dark-375.png) | [1280px light](hub-light-1280.png) | [1280px dark](hub-dark-1280.png) |
| Football | [375px light](football-light-375.png) | [375px dark](football-dark-375.png) | [1280px light](football-light-1280.png) | [1280px dark](football-dark-1280.png) |
| Cricket | [375px light](cricket-light-375.png) | [375px dark](cricket-dark-375.png) | [1280px light](cricket-light-1280.png) | [1280px dark](cricket-dark-1280.png) |
| Formula 1 | [375px light](f1-light-375.png) | [375px dark](f1-dark-375.png) | [1280px light](f1-light-1280.png) | [1280px dark](f1-dark-1280.png) |
| Share Kit | [375px light](share-light-375.png) | [375px dark](share-dark-375.png) | [1280px light](share-light-1280.png) | [1280px dark](share-dark-1280.png) |

## Landing before/after boards

- [Desktop: 1280×900, dark theme](comparisons/landing-dark-1280-comparison.png).
- [Phone: 375×812, dark theme](comparisons/landing-dark-375-comparison.png).

The two comparison boards are separate from the 24 original captures. Chromium rendered the real before and after PNGs at equal scale, cropping the final full-page image to the exact baseline viewport. Captions identify the capture/revision; source timestamps and sport values are retained. No chart or data was invented or redrawn. The [comparison manifest](comparisons/manifest.json) records the source images and retained HTML.

## Provenance

The [manifest](manifest.json) records each served URL, source capture, dimensions, SHA-256 and browser-case result. Every copied PNG was checked against its source hash. All 24 images and both comparison boards were visually inspected. These images are evidence for the primary host at the stated revision; broader host, route, browser and performance results are recorded separately in the [site analysis](../../site-analysis.md).
