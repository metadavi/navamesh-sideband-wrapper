SUPERGOAL_PHASE_START
Phase: 8 of 8 — Polish & Harden
Task: Verify every aspect — states, edges, accessibility, security, perf, copy, docs — and produce the farmer guide and deployment guide.
Type: ui, polish, hardening
Mandatory commands: .venv/bin/python -m pytest tests/ -q (x3), .venv/bin/python -m compileall sbapp/farmui tests, bash scripts/check_upstream_integrity.sh, git diff --stat upstream-pin..HEAD
Acceptance criteria: 9
Evidence required: one paragraph per sub-pass, final diff --stat, final screenshots normal+large-text
Depends on phases: 1, 2, 3, 4, 5, 6, 7

## Why

Catch what shipping-focused phases missed; this is how "beautiful, simple, farmer-friendly" gets enforced rather than asserted.

## Work (sub-passes — each produces a paragraph of evidence)

- **UX & copy** — audit every visible string: plain language, no jargon without a helper line ("📡 Signal — how strong the radio link is"), no debug placeholders, consistent voice. Fix all findings.
- **States** — verify and screenshot: no-announces-yet, no-gateway-pinned, no-replies-yet, sending, gateway-unreachable, radio-down, first-run onboarding card (one screen: "1. Turn on the white box · 2. Wait for green Radio chip · 3. Pick your farm gateway").
- **Edges** — gateway never announces (stream stays useful, no spinner-forever); `nodes` reply with 50 nodes (picker scrolls, list virtualized); reply arrives while app backgrounded (appears on resume; Android notification path is core's, untouched); bad/garbled image bytes → friendly card; timestamp clock-skew → "just now/—" fallback rather than negative ages.
- **A11y** — large-text toggle scales all screens (screenshots both modes); contrast re-run; every touch target ≥48dp measured (test or instrumented dump); soil status always icon+word+color, never color alone.
- **Security** — repo secret scan (no keys/DSNs); settings IP/port validation rejects garbage; confirm no new network surface beyond the RNS config interface block; debug APK signing documented as not-for-store.
- **Perf** — all core calls (send, list, announce) off the UI thread (audit + fix); announce/message lists virtualized (RecycleView) beyond 100 entries; app cold-start on desktop < 5s after core ready.
- **Docs** — `docs/FARMER_GUIDE.md`: ≤2 pages, screenshots, plain language, the three screens + the 9 buttons + "what to do when the radio chip is red". `docs/DEPLOYMENT.md`: Pi-side expectations (existing reticulum_bridge env unchanged), HT-HD01 config on both ends, APK install steps, gateway pinning. README final pass.
- **Diff review** — full `git diff upstream-pin..HEAD` review: confirm modified upstream files are exactly {`sbapp/main.py` (shim), `sbapp/buildozer.spec` (metadata), `setup.py` (additive entry)}; no stray debug prints/TODOs from this run; integrity guard final pass.
- **Regression sweep** — full suite x3; re-screenshot all three screens (normal + large-text); rig demo of soil + map one last time.

## Acceptance criteria (all must pass — verify each in transcript)

- Every sub-pass above has an evidence paragraph with findings + fixes (9 paragraphs)
- All state/edge screenshots captured and listed
- Touch-target and contrast checks pass as automated assertions
- No core call on UI thread (grep/audit evidence)
- Secret scan clean
- Modified-upstream-files set is exactly the three allowed files (diff proof)
- Full suite green x3; compileall clean; integrity guard green
- FARMER_GUIDE.md and DEPLOYMENT.md complete with screenshots
- Final diff --stat shown

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `.venv/bin/python -m pytest tests/ -q` (x3)
- `.venv/bin/python -m compileall sbapp/farmui tests`
- `bash scripts/check_upstream_integrity.sh`
- `git diff --stat upstream-pin..HEAD`

## Evidence required in transcript

- 9 sub-pass paragraphs
- Final diff --stat
- Final screenshots (normal + large-text)

## Notes

Cleanliness override: none. The bar is a tool a farmer can hand to a neighbor with zero explanation.
