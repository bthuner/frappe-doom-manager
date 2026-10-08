#!/usr/bin/env bash
set -euo pipefail

# build.sh -- compile DoomGeneric to WebAssembly with a custom SDL-free
# Emscripten backend and drop the output into the doom_manager Frappe app.
#
# Prereqs:
#   1. emcc on PATH (emsdk activated, or a distro emscripten package)
#   2. An IWAD next to this script. freedoom1.wad ships with the repo (BSD);
#      drop your own doom1.wad or doom.wad beside it to play the real thing.
#
# Usage:
#   ./build.sh
#
# Output: doom.js / doom.wasm / doom.data in
#   ../doom_manager_frappe_app/doom_manager/doom_manager/public/js/

DOOMGENERIC_REPO="https://github.com/ozkl/doomgeneric.git"
BUILD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$BUILD_ROOT/doomgeneric"
DG_SRC="$SRC_DIR/doomgeneric"
OUT_DIR="${OUT_DIR:-$BUILD_ROOT/../doom_manager_frappe_app/doom_manager/doom_manager/public/js}"

command -v emcc >/dev/null || { echo "ERROR: emcc not found on PATH"; exit 1; }

# doomgeneric/ is a git submodule pinned to a known-good upstream commit. A clone
# without --recurse-submodules leaves the directory present but empty, so test for
# an actual source file rather than for the directory.
if [ ! -f "$DG_SRC/doomgeneric.c" ]; then
  if [ -f "$BUILD_ROOT/.gitmodules" ]; then
    git -C "$BUILD_ROOT" submodule update --init doomgeneric
  else
    git clone "$DOOMGENERIC_REPO" "$SRC_DIR"
  fi
fi

# The engine locates its IWAD by filename: d_iwad.c walks the iwads[] table
# looking in FILES_DIR ("." -- which is / under Emscripten), so the preload
# target below must keep the file's own name.
#
# Freedoom is the default precisely because it is the only IWAD here that may be
# redistributed. Opting into a personal one is deliberate and never automatic --
# picking up a doom1.wad just because it happens to sit in the directory would
# quietly bake a non-redistributable WAD into the published doom.data.
#   IWAD=doom1.wad ./build.sh
IWAD="${IWAD:-freedoom1.wad}"

if [ ! -f "$BUILD_ROOT/$IWAD" ]; then
  echo "ERROR: IWAD '$IWAD' not found at $BUILD_ROOT/$IWAD"
  exit 1
fi
echo "== Using IWAD: $IWAD =="

if [ "$IWAD" != "freedoom1.wad" ]; then
  echo "   NOTE: $IWAD is not redistributable -- keep this build local."
fi

echo "== Copying Emscripten backend into the source tree =="
cp "$BUILD_ROOT/doomgeneric_emscripten.c" "$DG_SRC/"
rm -f "$DG_SRC/sound_stubs.c"

echo "== Injecting the run-tracking bridge (idempotent) =="
python3 "$BUILD_ROOT/patch_doom_bridge.py" "$DG_SRC"

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

cd "$DG_SRC"

# Same SDL-free source set as the stock doomgeneric/Makefile (which builds the
# xlib backend without any sound library), plus our backend. Excluded:
#   doomgeneric_<platform>.c  other platform backends (sdl/allegro/xlib/win/...)
#   i_sdl*.c, i_allegro*.c    sound/music backends needing SDL_mixer / Allegro
#   mus2mid.c                 only used by the SDL music backend
# Note: i_input.c must stay -- it defines I_GetEvent(), which drains DG_GetKey().
SOURCES=$(ls *.c | grep -v -E '^(doomgeneric_.*|i_sdl.*|i_allegro.*|mus2mid)\.c$')
SOURCES="$SOURCES doomgeneric_emscripten.c"

echo "== Compiling with emcc =="
emcc \
  $SOURCES \
  -O2 \
  -Wno-everything \
  -s WASM=1 \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s STACK_SIZE=1MB \
  -s ENVIRONMENT=web \
  -s MODULARIZE=1 \
  -s EXPORT_NAME=createDoomModule \
  -s EXPORTED_RUNTIME_METHODS=ccall,cwrap,HEAPU32,FS \
  -s EXPORTED_FUNCTIONS=_main,_DG_PushKey \
  -s FORCE_FILESYSTEM=1 \
  -o "$OUT_DIR/doom.js"

# The IWAD is no longer baked into the binary. It is fetched at runtime and
# written into MEMFS before main(), so that a player can bring their own without
# rebuilding the engine -- and so that a 27 MB WAD is not re-downloaded whenever
# the engine changes. The shipped Freedoom becomes a plain static asset.
echo "== Publishing the default IWAD as a static asset =="
cp "$BUILD_ROOT/$IWAD" "$OUT_DIR/$IWAD"

# Asset URLs are not content-hashed and Frappe serves /assets without a
# Cache-Control header, so a browser can hold a stale engine indefinitely. The
# page itself is no_cache, so it can hand the SPA a version to append as a query
# string; that is enough to bust the three engine files together.
echo "== Writing the build manifest =="
# Hash both files: EXPORTED_RUNTIME_METHODS and friends change doom.js without
# touching doom.wasm, so hashing the wasm alone would leave browsers pinned to a
# stale glue script under an unchanged version.
VERSION="$(cat "$OUT_DIR/doom.js" "$OUT_DIR/doom.wasm" | sha256sum | cut -c1-12)"
cat > "$OUT_DIR/doom.build.json" <<JSON
{
  "version": "$VERSION",
  "default_iwad": "$IWAD",
  "default_iwad_size": $(stat -c%s "$OUT_DIR/$IWAD"),
  "default_iwad_sha256": "$(sha256sum "$OUT_DIR/$IWAD" | cut -d' ' -f1)"
}
JSON
cat "$OUT_DIR/doom.build.json"

# doom.data only exists in builds that still preloaded a WAD; drop the stale one.
rm -f "$OUT_DIR/doom.data"

echo "== Done =="
ls -la "$OUT_DIR"/doom.js "$OUT_DIR"/doom.wasm "$OUT_DIR/$IWAD" "$OUT_DIR"/doom.build.json
