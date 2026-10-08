# Licensing

This project ships three things under three different licences. The important
one is the first: **the compiled engine is GPL-2.0**, and publishing it carries
an obligation to offer its source.

| Component | Licence |
|---|---|
| `doom.wasm`, `doom.js` — the compiled engine | **GPL-2.0**, derived from DoomGeneric and the Doom source release |
| `doomgeneric_emscripten.c`, `patch_doom_bridge.py` | **GPL-2.0** — they are part of that derived work |
| `build.sh` | **GPL-2.0**, same reason |
| The `doom_manager` Frappe app (Python, Vue, DocTypes) | **MIT** — see its own `license.txt` |
| `freedoom1.wad` (shipped, and packed into `doom.data`) | **BSD 3-clause**, © 2001-2024 contributors to the Freedoom project |

## Written offer of source (GPL-2.0 §3)

The engine binary served at `/assets/doom_manager/js/doom.wasm` is a derivative
work of [DoomGeneric](https://github.com/ozkl/doomgeneric), itself derived from
id Software's Doom source release, both under GPL-2.0. The complete
corresponding source is:

- **DoomGeneric**, pinned at commit `dcb7a8d` — declared as a git submodule in
  this repository, so `git clone --recurse-submodules` fetches the exact tree
  the binary was built from.
- **`doomgeneric_emscripten.c`** in this repository — the SDL-free Emscripten
  platform backend.
- **`patch_doom_bridge.py`** in this repository — the four `EM_ASM` hooks
  injected into `g_game.c` and `wi_stuff.c` at build time.
- **`build.sh`** in this repository — the exact `emcc` invocation.

Those four together reproduce the binary. Nothing else is needed and nothing is
withheld.

## Why the MIT app does not launder the GPL engine

`doom_manager` is MIT and stays MIT: it is a Frappe application that talks to
the engine across a browser-global boundary (`window.onDoomLevelStart` and
friends). It is not linked into the engine and contains none of its code. But
the MIT licence covers the app only — it does not extend to `doom.wasm`,
`doom.js` or `doom.data`, which are distributed under GPL-2.0 and BSD
respectively. Anyone redistributing the built assets inherits those terms.

## On IWADs

`freedoom1.wad` is here because it is the only game data this project may
lawfully redistribute. It is BSD-licensed and the Doom engine recognises it
natively (`d_iwad.c`, `{ "freedoom1.wad", doom, retail, "Freedoom: Phase 1" }`).
`FREEDOOM-COPYING.txt` and `FREEDOOM-CREDITS.txt` accompany it, as the BSD
licence requires for binary redistribution.

**id Software's shareware `doom1.wad` is deliberately not shipped.** The
shareware licence permits non-commercial redistribution of the *complete,
unmodified shareware package* — not a lone IWAD extracted from it and served
over HTTP. If you own a copy of Doom, build with it locally:

```bash
IWAD=doom1.wad ./build.sh    # or doom.wad
```

`build.sh` will say so, and the resulting `doom.data` must not be published.
`.gitignore` refuses to track any `*.wad` other than `freedoom1.wad`.

*This file records how the project is licensed. It is not legal advice.*
