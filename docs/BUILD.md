# Navamesh Farm — APK Build Guide

## Quick start (Docker)

```bash
bash scripts/build_apk.sh
```

Requires Docker Desktop running.  The first build downloads the Android SDK/NDK and
compiles all p4a recipes (~30-60 min).  Subsequent builds use the `navamesh-buildozer-cache`
Docker volume and complete in ~5-10 min.

Output: `dist/navamesh-farm-1.9.7-arm64-v8a-debug.apk`

---

## Architecture

The app is a **packaging-metadata-only fork** of Sideband 1.9.7.  The entire Sideband
build chain (p4a recipes, sidebandservice.py, patches/) is used byte-identically.
These 6 lines in `sbapp/buildozer.spec` differ from upstream (5 metadata + NDK):

| Key              | Upstream value                            | Navamesh value                         |
|------------------|-------------------------------------------|----------------------------------------|
| `title`          | `Sideband`                                | `Navamesh Farm`                        |
| `package.name`   | `sideband`                                | `navameshfarm`                         |
| `package.domain` | `io.unsigned`                             | `farm.navamesh`                        |
| `icon.filename`  | `%(source.dir)s/assets/icon.png`          | `%(source.dir)s/assets/farm/icon.png`  |
| `presplash.filename` | `%(source.dir)s/assets/presplash_small.png` | `%(source.dir)s/assets/farm/presplash.png` |
| `android.ndk`    | `25b`                                     | `28c`                                  |

**NDK r28c:** the current p4a numpy recipe builds numpy 2.3.0, whose C++ (`unique.cpp`)
needs a newer libc++ than NDK r25b ships (`std::unordered_map` not found).  NDK r28c
(p4a's own recommended version) compiles it cleanly, and the current SDL2 recipe
supports r28c.  No effect on RNS/LXMF protocol behaviour.

**Android Python version:** the vendored `recipes/python3` + `recipes/hostpython3`
pin **Python 3.11.5** for the Android build (with `recipes/cython` at 3.1.6).  This is
upstream Sideband's own choice and is why kivy 2.3.0 compiles — it is *not* a Navamesh
change.  These local recipes require a current python-for-android (they use
`PyProjectRecipe`), so the build uses p4a's default (latest) branch.  The recipes are
passed via `p4a.local_recipes = ../recipes/`; the build must therefore run from a tree
where `../recipes/` resolves (the build script copies both `sbapp/` and `recipes/` into
the build volume).

Verify: `git diff upstream-pin -- sbapp/buildozer.spec`

---

## Docker details

```
Image:   navamesh-buildozer:py312  (built from Dockerfile.buildozer at project root)
Base:    python:3.12-slim-bookworm + buildozer 1.5.0 + Cython 3.0.11
Volumes: navamesh-buildozer-cache  (SDK/NDK cache, ~4 GB after first build)
         navamesh-build-dir        (per-project build tree)
         navamesh-src              (project source copy)
```

**Why three volumes / no bind mount:** Docker Desktop on macOS shares host
directories via VirtioFS, which does not support the file-locking and access
patterns python-for-android uses — the build dies with
`OSError: [Errno 35] Resource deadlock avoided`.  `build_apk.sh` therefore copies
the project source into the `navamesh-src` volume once, runs the entire build on
ext4 Docker volumes (no bind mount), and copies the finished APK back to `dist/`
at the end.  On native Linux you can bind-mount directly; the volume copy is a
macOS-specific workaround but is harmless on Linux.

`kivy/buildozer:latest` ships Python 3.14, which breaks kivy 2.3.0's pre-Cythonized
C extensions (`_PyList_Extend`, `_PyUnicode_FastCopyCharacters` removed in 3.12+).
The custom image pins Python 3.12 and buildozer 1.5.0, matching what Sideband 1.9.7
was built against.  `scripts/build_apk.sh` builds this image automatically on first run.

On Apple Silicon (arm64), the build runs under QEMU emulation via Docker Desktop's
linux/amd64 layer.  Expect ~2× slower compile times vs native x86_64.

---

## Linux VM / CI fallback

If Docker is unavailable or the emulated build is too slow, use an x86_64 Linux VM or
a CI runner:

### Ubuntu 22.04 (native x86_64)

```bash
# Install system deps
sudo apt-get update && sudo apt-get install -y \
  python3-pip python3-venv git zip unzip \
  openjdk-17-jdk build-essential libssl-dev libffi-dev \
  libpq-dev autoconf libtool pkg-config cmake

# Install buildozer
pip3 install --user buildozer==1.5.0

# In sbapp/
cd sbapp
buildozer android debug
```

### GitHub Actions (CI)

Add a workflow that uses `kivy/buildozer` Docker image or the
`ArtemSBulgakov/buildozer-action` Action.  See `.github/workflows/` for the
skeleton.

### macOS direct (not recommended)

macOS buildozer support is experimental.  Known issues: Homebrew OpenSSL path,
missing `zlib.h`.  Use the Docker path if on macOS.

---

## Verifying the APK without a device

```bash
# List contents
unzip -l dist/navamesh-farm-*-debug.apk | grep -E "farmui|sidebandservice|assets"

# Confirm package metadata
aapt dump badging dist/navamesh-farm-*-debug.apk | head -10
```

Expected entries:
- `assets/farmui/` — farm UI code
- `services/sidebandservice.py` — unmodified foreground service
- `assets/farm/icon.png` — farm icon
- Package: `farm.navamesh.navameshfarm`

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `QEMU segfault` | Use Linux VM instead of arm64 Docker emulation |
| `NDK download timeout` | Set `ANDROID_NDK_PATH` to a pre-downloaded NDK r28c |
| `pycodec2 build fail` | Ensure `codec2` recipe is in `../recipes/` (included) |
| `patchelf not found` | `apt-get install patchelf` before build |
| `_PyList_Extend undeclared` | p4a built Python 3.14; `p4a.branch = v2024.01.21` pins Python 3.12 |
| `Resource deadlock avoided` | flock on macOS bind mount; build tree is on the `navamesh-build-dir` Docker volume |
| `No matching distribution found for codec2` | local `recipes/` not reachable; build copies `sbapp/` + `recipes/` + `libs/` into the volume |
| `cannot stat '.../libs/able/able'` | top-level `libs/` not copied into the build volume (script copies it) |
| `cannot stat '/home/markqvist/.../LXST'` | LXST source is baked into the image at that path (see Dockerfile.buildozer) |
