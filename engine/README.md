# GenericDoom_Frappe — DoomGeneric → WebAssembly → Frappe

Compiles [DoomGeneric](https://github.com/ozkl/doomgeneric) to WASM with a
small SDL-free Emscripten backend and serves it from the `doom_manager` Frappe
app (sibling repo `../doom_manager_frappe_app/doom_manager`). The game runs at
`/doom` on the Frappe site; finished levels are stored as `Doom Run` documents.

```
GenericDoom_Frappe/          this repo: build pipeline + docker stack
  doomgeneric_emscripten.c   platform backend (main loop, framebuffer hand-off, key queue)
  patch_doom_bridge.py       injects the run-tracking hooks into g_game.c + wi_stuff.c
  build.sh                   emcc build -> ../doom_manager_frappe_app/.../public/js/doom.{js,wasm,data}
  docker/compose.yaml        Frappe v15 + MariaDB + Redis with doom_manager installed
  doom1.wad                  shareware IWAD (not committed elsewhere; drop yours here)
  doomgeneric/               upstream submodule, pinned (build.sh inits it if missing)
```

## Build the engine

Clone with submodules (`doomgeneric/` is pinned to upstream `dcb7a8d`):

```bash
git clone --recurse-submodules ssh://git@forge.heeboo.org:2222/thunerbl/frappe-doom
# already cloned without it:
git submodule update --init
```

Requires `emcc` (emsdk or a distro emscripten package) and `doom1.wad` in this
directory (the shareware IWAD is freely redistributable).

```bash
./build.sh
```

Output lands in `../doom_manager_frappe_app/doom_manager/doom_manager/public/js/`:
`doom.js` (Emscripten glue, exports `createDoomModule`), `doom.wasm`, and
`doom.data` (the packaged WAD, mounted at `/doom1.wad`).

The build is the stock `doomgeneric/Makefile` source set (no SDL, no sound) plus
`doomgeneric_emscripten.c`. Sound is intentionally absent.

## Run Frappe with Doom

```bash
cd docker
docker compose build      # layers the app onto frappe/erpnext:v15.121.1
docker compose up -d      # first start creates site "frontend" and installs doom_manager (~2 min)
docker compose logs -f create-site
```

Then open <http://localhost:8099/doom>. Login at `/login` with
`Administrator` / `admin` to have completed levels saved (guests can play, not
save). Runs are listed under `/app/doom-run`. Reset everything with
`docker compose down -v`.

The compose file is frappe_docker's `pwd.yml` with the image swapped for the
locally built `doom-frappe:local`, MariaDB 10.6, port 8099, and
`--install-app doom_manager` at site creation.

The app is **copied into the image** at build time -- the only volumes are
`sites` and `logs`, nothing bind-mounts the source. A running container
therefore keeps serving the app as it was at the last `docker compose build`.
After changing app code or rebuilding the engine:

```bash
docker compose build && docker compose up -d
# DocType changes (new fields) additionally need:
docker compose exec backend bench --site frontend migrate
```

The order matters. Running `migrate` without rebuilding first migrates the
*old* app baked into the image, reports success, and changes nothing -- the new
columns simply never appear. `Queued rebuilding of search index for frontend`
is the normal last line of a successful migrate: the index rebuild is enqueued
on the long queue, not run inline, so the command is done when it prints that.

## Controls

Enter starts / confirms, Esc opens the menu. Arrows or WASD move (A/D strafe),
Ctrl or left click fires, Space / E / right click uses, Shift runs, Tab shows the
map. Cheat codes are typed as usual (`iddqd`, `idkfa`, `idclev12`).

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
