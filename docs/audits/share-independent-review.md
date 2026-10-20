# Independent Share preview review

Reviewed final Share commit `86cc9ff` on 2026-10-19, with the GitHub-base build served at `http://127.0.0.1:5222/ipl_top4_analysis/share.html`. Application sources were read-only. No remaining blocker was confirmed in the reviewed preview pipeline or frontend.

## Archive integrity

The independent comparison against `6ecef1d` found all 13 original PNGs byte-identical. Removing only the three new optional preview fields from each manifest slide makes the entire original manifest identical to the baseline: archive dates, source, source timestamp, generated timestamp, warnings, PNG paths and download names remain intact. The archive remains `2026-05-24`; no replacement pack or new historical date was created.

Running the final archive backfill on a temporary copy preserved all file bytes and modification times, including manifest, original PNGs and WebPs. Final display previews are 720×1280 WebP at quality 85; original downloads remain 1080×1920 PNG. The first preview is 58,000 bytes, compared with the original’s 182,311 bytes.

[Final integrity evidence](../screenshots/verification-share-independent/integrity-final.json).

## Browser findings and verified repairs

Five independent Chromium probes passed:

- Published previews at 375px dark and 1280px light render at their real 720px source width. Original PNG open/download destinations remain unchanged. The last slide loads successfully when scrolled into view.
- A legacy manifest without preview fields displays the original 1080×1920 PNG.
- A missing optional WebP originally left a broken image despite an available PNG. The final implementation recovers once to the original PNG and restores its 1080×1920 dimensions. The real 404 probe now passes.
- Mixed-date archive cards originally used the pack’s latest date for every slide. The final implementation uses each slide’s own date, with the pack date as a fallback. The synthetic date/fallback probe now passes.

The first image’s preload is reused: its Resource Timing initiator is `link`, with exactly one network request to the displayed URL. No unused-preload warning was recorded in the normal published cases. Initial phone load requests one of 11 gallery images; desktop requests four of 11. This matches visible content rather than eagerly fetching the complete gallery. Deferred images load when needed.

The 720px previews retain the archived graphic’s primary odds and team identifiers without a visible compression regression at the inspected widths. The historical graphic includes small print; this review does not claim every raster label is 12 CSS pixels. Full PNGs remain available for reading/export, and the surrounding archive date and controls remain normal accessible page text.

[Browser probes](../screenshots/verification-share-independent/browser-final.json), [phone close-up](../screenshots/verification-share-independent/final-published-375-dark.png), [desktop close-up](../screenshots/verification-share-independent/final-published-1280-light.png).

## Performance evidence

The final writer-run Lighthouse 13.5 mobile report was independently inspected: performance 98, accessibility 100, FCP 1.515s, LCP 2.273s, CLS 0 and TBT 0ms. The LCP element is the actual first slide image. Earlier preview-only and bounded-loading trials were 3.028s and 2.586s; the final optimization combines bounded loading with the smaller quality-85 preview and preserves the two measured font hints.

[Final Lighthouse report](../performance/share-final-optimized.json).

This is a local simulated mobile sample, not field INP or production p75. The implementation writer separately reported 303 Python tests (one skip), 104 frontend tests, lint/build and eight Chromium/WebKit cases passing. The final merged release still needs both-host production checks, including canonical Share return links after the separate static-page integration.
