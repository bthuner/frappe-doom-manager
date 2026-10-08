# engine/ — DoomGeneric → WebAssembly

Compiles [DoomGeneric](https://github.com/ozkl/doomgeneric) to WASM with a
small SDL-free Emscripten backend, and drops the result into the app's
`doom_manager/public/js/`, where the `/doom` page loads it.

```
engine/
  doomgeneric_emscripten.c   platform backend (main loop, framebuffer hand-off, key queue)
  patch_doom_bridge.py       injects the run-tracking hooks into g_game.c + wi_stuff.c
  build.sh                   emcc build -> ../doom_manager/public/js/doom.{js,wasm} + doom.build.json
  doomgeneric/               upstream submodule, pinned to dcb7a8d (build.sh inits it if missing)
```

## Build

Requires `emcc` (emsdk or a distro emscripten package).

```bash
engine/build.sh
```

The IWAD defaults to `freedoom1.wad`, already shipped in
`doom_manager/public/js/` — BSD-licensed and the only game data this project
may redistribute. If you own Doom, drop `doom1.wad` (or `doom.wad`) in
`engine/` and build with it — locally:

```bash
IWAD=doom1.wad engine/build.sh
```

id Software's shareware `doom1.wad` is **not** shipped. Its licence covers
redistributing the complete, unmodified shareware package, not a lone IWAD
served over HTTP, so a build made with it must stay local. See
`../LICENSES.md`, which also carries the GPL-2.0 offer of source for the
compiled engine.

Output: `doom.js` (Emscripten glue, exports `createDoomModule`), `doom.wasm`,
and `doom.build.json` (a version hash used to bust browser caches, plus the
default IWAD's name, size and sha256). The IWAD is not baked in: the page
fetches it at runtime and writes it into MEMFS before `main()`.

The build is the stock `doomgeneric/Makefile` source set (no SDL, no sound) plus
`doomgeneric_emscripten.c`. Sound is intentionally absent.

## How the pieces talk

- `DG_DrawFrame` hands the `0x00RRGGBB` framebuffer pointer to
  `window.DoomBridge._blitFrame(ptr, w, h)`; `doom_engine.js` swizzles it into
  an `ImageData` and paints the 640×400 canvas.
- Key events are mapped to `doomkeys.h` codes in JS and pushed with
  `Module.ccall('DG_PushKey', ...)`; `i_input.c` drains them through `DG_GetKey`.
- `main()` drives `doomgeneric_Tick` with `emscripten_set_main_loop` (no
  ASYNCIFY; `DG_SleepMs` is a no-op because `TryRunTics` already yields once a
  tic has elapsed).
- `patch_doom_bridge.py` adds three `EM_ASM` hooks, so that a `Doom Run` spans a
  whole level instead of being written once at the end:

  | Hook | Injected into | Fires |
  |---|---|---|
  | `onDoomLevelStart(ep, map, tk, ti, ts)` | `g_game.c` `G_Ticker` | a level began |
  | `onDoomLevelComplete(ep, map, k, tk, i, ti, s, ts, secs)` | `wi_stuff.c` `WI_initVariables` | the exit was reached |
  | `onDoomGameOver(...same...)` | `g_game.c` `G_DoReborn` | the player died |

  Episode and map are 1-based on all three; counts are raw with the level total
  alongside (6 kills out of 9), not the percentages the intermission shows.
  `useDoomEngine.js` turns them into `onLevelStart` / `onLevelEnd` listeners and
  `Play.vue` calls the whitelisted `doom_manager.api.start_run` — which
  get-or-creates the `Doom Level` and inserts a **draft** `Doom Run` — then
  `finish_run`, which fills in the counts and submits it. `outcome` is
  `Completed` or `Died`.
- The start hook lives in `G_Ticker`, not in the obvious `G_DoLoadLevel`, because
  `G_DoPlayDemo` calls `G_InitNew` (which loads the level and clears
  `demoplayback`) and only sets `demoplayback = true` *after* it returns. Inside
  `G_DoLoadLevel` the flag reads false even for the attract-mode demos, so every
  idle title screen would open a run. Testing `(levelstarttic, gamemap)` once per
  tic instead sees the flag settled, one tic later.
- Doom 1 has no GAME OVER screen: in single player, dying goes through
  `G_DoReborn`, which sets `gameaction = ga_loadlevel`. That reload bumps
  `levelstarttic`, so the next run opens by itself.
- A player who closes the tab mid-level leaves a draft `Doom Run` behind. Drafts
  are `docstatus 0`, so `get_runs` and `get_leaderboard` (which filter on
  `docstatus 1`) ignore them.

## History / gotchas

- The first build attempts produced an 11 KB `doomgeneric.wasm` with no `main`
  export: the custom backend never defined `main()`, and DoomGeneric's
  `D_DoomLoop` runs a single tick and returns, so nothing ever ran. The
  `Makefile.emscripten` route also linked SDL2 and dropped our flags. `build.sh`
  now only uses the manual `emcc` invocation.
- `i_input.c` must stay in the build: it defines `I_GetEvent`, the only
  consumer of `DG_GetKey`.
- Recent Emscripten requires `HEAPU32` to be listed in
  `EXPORTED_RUNTIME_METHODS`; the JS re-reads `Module.HEAPU32` every frame
  because the view is replaced when memory grows.
- In the official Frappe image `sites/assets` is re-linked at container start
  to `/home/frappe/frappe-bench/assets`, so the app's asset symlink is baked into
  the image by the Dockerfile rather than created at site-creation time.
- `doomgeneric/` is a submodule pinned to upstream `dcb7a8d`, declared `ignore = dirty`
  because `build.sh` copies `doomgeneric_emscripten.c` into it and patches
  `wi_stuff.c` on every build. Those edits are regenerated, never committed, so
  the checkout stays vanilla and no fork is needed.
