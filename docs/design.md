# Dashboard design

**Who it's for:** a recruiter or hiring manager who gives the page 30 seconds,
and an engineer who stays for five minutes.

**What it is:** a product page that opens on a precomputed case study (3,581
archived CFPB complaint narratives, January 1–4, 2024) and lets visitors run
the live model on their own text. The signature idea is that every label shows
the words that drove it, with their real weights from the model.

## Example vs. live

- The example is a static file (`frontend/public/example-insights.json`, built
  by `scripts/build_case_study.py`), so it never waits for the API.
- Example sections say so in their copy ("This is example data: archived CFPB
  complaints…"), and the footer states the evaluation limits.
- Live results appear only in "Try it on your own words", each with a Live tag,
  the time, and the theme model. They never replace the example.
- The header status shows checking, waking up, ready, or unavailable. Analyze is
  disabled until the API answers `/health`.

## References

- **Dovetail:** a list of themes beside the evidence for the selected one.
- **Enterpret:** a near-black ground with one accent colour.
- **Thematic:** an insight stated in words next to the chart that backs it.

## System

- **Type:** Mona Sans only (self-hosted, variable weight and width). Headlines
  run wide (112–118% width) at weight 800+; numbers use tabular figures.
- **Colour:** ink `#0A0A0B`, text `#F5F5F4`, greys `#CFCFD5`/`#B9B9C0`/`#8E8E96`,
  and one accent, lime `#D4FF3A`, used for highlights, primary actions, and
  progress. No second accent colour; weak scores and disagreements are shown
  in words, grey, and strike-through.
- **Avoided on purpose:** orange/terracotta accents, decorative monospace and
  uppercase labels, serif accent words, window-chrome dots, "·"-separated
  metadata, decorative glows.

## Motion

All scroll effects use CSS scroll-driven animation; nothing hijacks scrolling.

- Hero lines rise in while widening; lime sweeps across "why".
- A replay of archived complaints streams by (pauses on hover).
- Key figures count up as they enter; a lime rule draws above each.
- A summary paragraph brightens line by line as it scrolls through.
- The theme panel tilts upright on entry; bars grow; evidence words highlight
  as they scroll in and replay when a theme is picked.
- "Where it disagrees" pins and slides sideways with the scroll; Previous and
  Next buttons step one card at a time. On phones it is a swipeable strip.
- "How it works" pins while a progress line lights each step.

Browsers without scroll-driven animation, and `prefers-reduced-motion`, get the
final state of everything with no pinning.
