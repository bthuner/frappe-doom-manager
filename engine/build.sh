#!/usr/bin/env bash
set -euo pipefail

# build.sh -- compile DoomGeneric to WebAssembly with a custom SDL-free
# Emscripten backend and drop the output into the doom_manager Frappe app.
#
# Prereqs:
#   1. emcc on PATH (emsdk activated, or a distro emscripten package)
#   2. A legally owned doom1.wad (shareware is fine) next to this script
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

if [ ! -f "$BUILD_ROOT/doom1.wad" ]; then
  echo "ERROR: place a doom1.wad (shareware or owned copy) at $BUILD_ROOT/doom1.wad"
  exit 1
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
  -s EXPORTED_RUNTIME_METHODS=ccall,cwrap,HEAPU32 \
  -s EXPORTED_FUNCTIONS=_main,_DG_PushKey \
  --preload-file "$BUILD_ROOT/doom1.wad@/doom1.wad" \
  -o "$OUT_DIR/doom.js"

echo "== Done =="
ls -la "$OUT_DIR"/doom.js "$OUT_DIR"/doom.wasm "$OUT_DIR"/doom.data
