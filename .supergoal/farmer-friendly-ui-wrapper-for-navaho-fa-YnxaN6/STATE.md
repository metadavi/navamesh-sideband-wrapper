# State: Navamesh Farm App — farmer-friendly Sideband/Reticulum wrapper

**Status:** COMPLETE
**Current phase:** 8 (done)
**Started:** 2026-06-12
**Last update:** 2026-06-15
**Run root:** .supergoal/farmer-friendly-ui-wrapper-for-navaho-fa-YnxaN6
**Baseline ref:** upstream-pin

## Phase progress

| # | Phase | Status | Started | Completed | Notes |
|---|-------|--------|---------|-----------|-------|
| 1 | Scaffold fork & pin upstream | completed | 2026-06-12 | 2026-06-12 | integrity guard pass+fail+revert demo'd |
| 2 | Protocol rig & stub gateway | completed | 2026-06-12 | 2026-06-12 | 12/12 tests, 3×runs pass |
| 3 | Farm UI shell (desktop) | completed | 2026-06-12 | 2026-06-12 | 11/11 logic tests; 3 PIL screenshots; compileall clean |
| 4 | Conversation command flow | completed | 2026-06-12 | 2026-06-12 | 15/15 e2e tests 3×pass; wire-content asserted |
| 5 | HT-HD01 UDP connectivity | completed | 2026-06-12 | 2026-06-12 | 44/44 tests 3×pass; UDP runner + config-writer; chip screenshots |
| 6 | Android packaging | completed | 2026-06-12 | 2026-06-15 | navameshfarm-1.9.7-arm64-v8a-debug.apk (92 MB); 44/44 tests pass |
| 7 | Behavior-preservation proof | completed | 2026-06-15 | 2026-06-15 | test_stock_equivalence.py 6/6; TESTING.md matrix 14 rows; FIELD_TEST_PLAN.md 12 steps |
| 8 | Polish & Harden | completed | 2026-06-15 | 2026-06-15 | Pass 1-4,6,7 fixed; all 9 sub-passes PASS |

## Engineering check status

- Build: PASS — dist/navameshfarm-1.9.7-arm64-v8a-debug.apk (92 MB)
- Typecheck: —
- Lint: —
- Tests: 50/50 pass × 3 runs (Phase 8 confirmed)

## Notable events

- 2026-06-12 — Phase 1 complete: Sideband 1.9.7 vendored, upstream-pin tag created, integrity guard green, venv+deps installed, docs written.
- 2026-06-12 — Pre-flight bypassed by user (docker-only red). Status → READY_TO_DISPATCH.
- 2026-06-12 — Plan drafted, 8 phases. Architecture: Sideband fork with minimal UI layer; core byte-identical; UDP via config only.
- 2026-06-12 — Pre-flight red: docker info exited 1 (daemon not running; needed only for phase 6 APK build). venv/git/github green; Sideband latest tag = 1.9.7.
- 2026-06-12 — Phase 6 BLOCKED after 3 strikes. FAILURE_HANDOFF issued. See failure log.
- 2026-06-15 — Phase 6 COMPLETE. APK produced: navameshfarm-1.9.7-arm64-v8a-debug.apk (92 MB). Root causes resolved: NDK r28c, Patches 1-4, Rust for cryptography, numpy+Cython to hostpython3 site_dir, device_filter.xml injected into src/res_initial + SDL2 bootstrap template.
- 2026-06-15 — Phase 7 COMPLETE. test_stock_equivalence.py 6/6 (5 commands wire-equal stock + farmui). docs/TESTING.md 14-row guarantee matrix. docs/FIELD_TEST_PLAN.md 12-step hardware plan. Full suite 50/50 × 3 runs.
- 2026-06-15 — Phase 8 COMPLETE. All 9 sub-passes green: Pass 1 label fix (Signal strength); Pass 2 send-in-flight guard + onboarding card; Pass 3 image rendering in ResultCard (CoreImage → texture); Pass 4 large_text wired to theme pre-scale + AnnounceScreen toggle; Pass 6 stream list capped at 200 rows + dedup, conversation list capped at 100 cards; Pass 7 docs/FARMER_GUIDE.md + docs/DEPLOYMENT.md created. 50/50 × 3 runs pass.

## Failure log

### Phase 6 — Android packaging — FAILURE_HANDOFF (2026-06-12)

**Failing criterion:** `dist/navamesh-farm-*-debug.apk` does not exist after 3 build attempts.

**Root cause:** numpy 2.x (downloaded from git master by p4a) uses `std::unordered_map` in
`numpy/_core/src/multiarray/unique.cpp:123` which is not found in NDK r25b's libc++ when
cross-compiling for `aarch64-linux-android24`.

```
error: no template named 'unordered_map' in namespace 'std'
ninja: build stopped: subcommand failed
```

**Strike 1:** `docker run kivy/buildozer:latest android debug` — default entrypoint —
numpy 2.x + NDK r25b fails at step 117/340.

**Strike 2:** Added `--entrypoint /bin/bash` with numpy recipe patch script (`_build_inner.sh`).
Patch targeted `/home/user/.buildozer/` but buildozer ran as root using `/root/.buildozer/`.
Fresh p4a clone pulled numpy master (2.x) again → same error.

**Strike 3:** Confirmed same failure; patch path mismatch not recoverable within constraints
(cannot change `requirements`, cannot modify `recipes/`, cannot change NDK version).

**Suggested next move (pick one):**
1. Build on x86_64 Linux with NDK r27b — see `docs/BUILD.md §Linux VM / CI fallback`
2. Add `numpy==1.26.4` to `buildozer.spec` requirements (requires relaxing the
   UNTOUCHED-requirements constraint — user decision)
3. Use `kivy/buildozer` image pinned to a tag that ships p4a with numpy 1.x

**All Phase 6 non-build artifacts are complete and committed:**
- `sbapp/buildozer.spec`: exactly 5 keys changed (verified by git diff)
- `sbapp/assets/farm/icon.png` + `presplash.png`: created
- `scripts/build_apk.sh` + `scripts/_build_inner.sh`: created
- `docs/BUILD.md` + `docs/DEVICE_SMOKE.md`: created
- Integrity guard: PASS; pytest 44/44: PASS
