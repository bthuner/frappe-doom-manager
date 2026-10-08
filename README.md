# Doom Manager — Frappe App

A civic-tech-flavored side project: model Doom's gameplay data (monsters, weapons,
levels, spawn placement, and play sessions) as Frappe DocTypes, while the actual
game engine runs client-side as WebAssembly in the browser.

The repo root is the Frappe app itself, so `bench get-app` works on it as is.
The engine build and a ready-to-run Docker stack live alongside it:

```
setup.py, Dockerfile        the Frappe app (MIT)
doom_manager/               Python package: DocTypes, api.py, www/doom, public/js
frontend/                   Vue / frappe-ui SPA served at /doom
engine/                     DoomGeneric -> WASM build pipeline (GPL-2.0), see engine/README.md
docker/compose.yaml         Dokos + MariaDB + Redis with doom_manager installed
LICENSES.md                 what is licensed how, and the GPL-2.0 offer of source
```

## Quick start (Docker)

```bash
git clone --recurse-submodules ssh://git@forge.heeboo.org:2222/thunerbl/frappe-doom-manager
cd frappe-doom-manager/docker
docker compose build      # builds the SPA and layers the app onto the Dokos image
docker compose up -d      # first start creates site "frontend" and installs doom_manager (~2 min)
docker compose logs -f create-site
```

Then open <http://localhost:8098/doom>. Login at `/login` with
`Administrator` / `admin` to have completed levels saved (guests can play, not
save). Runs are listed under `/app/doom-run`. Reset everything with
`docker compose down -v`.

The built engine (`doom_manager/public/js/doom.{js,wasm}`) is committed, so the
stack runs without `emcc`. Rebuild it after touching `engine/` with
`engine/build.sh` (needs the submodule: `git submodule update --init`).

The compose file is frappe_docker's `pwd.yml` with the image swapped for the
locally built `doom-dokos:local`, MariaDB 10.6, port 8098, and
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

## Install on an existing bench

```bash
cd frappe-bench
bench get-app ssh://git@forge.heeboo.org:2222/thunerbl/frappe-doom-manager
bench --site your-site.local install-app doom_manager
bench build --app doom_manager    # links public/ into sites/assets
```

## Controls

Enter starts / confirms, Esc opens the menu. Arrows or WASD move (A/D strafe),
Ctrl or left click fires, Space / E / right click uses, Shift runs, Tab shows the
map. Cheat codes are typed as usual (`iddqd`, `idkfa`, `idclev12`).

## What's included

- `doom_manager/doom_manager/doctype/doom_monster` — reference DocType for monster stats
- `doom_manager/doom_manager/doctype/doom_weapon` — reference DocType for weapons
- `doom_manager/doom_manager/doctype/doom_level` — parent DocType for a level/map
- `doom_manager/doom_manager/doctype/doom_level_monster` — child table: monster spawns on a level
- `doom_manager/doom_manager/doctype/doom_level_item` — child table: item pickups on a level
- `doom_manager/doom_manager/doctype/doom_run` — submittable DocType logging a play session
- `doom_manager/doom_manager/doctype/doom_iwad` — IWADs players bring themselves
- `doom_manager/www/doom.html` — page hosting the SPA and the WASM Doom canvas
- `frontend/src/composables/useDoomEngine.js` — boots the WASM engine, paints the canvas, maps keys
- `doom_manager/api.py` — whitelisted endpoints that open and close a Doom Run

## Notes

- Play works for guests; saving a `Doom Run` needs a logged-in user. The page
  calls the whitelisted `doom_manager.api.start_run` / `finish_run`, which
  get-or-create the `Doom Level` (e.g. `E1M1`) and insert, then submit, the run
  with `ignore_permissions`, so no API keys live in client JS. How the engine
  reports level start / end is described in `engine/README.md`.
- `doom_level_monster` and `doom_level_item` are child tables (`istable: 1`); full
  WAD geometry is out of scope. Only gameplay/meta data is modelled.
- Set `developer_mode = 1` in the site config before editing DocType JSON directly.

## Licensing

The app is MIT; the compiled engine is GPL-2.0; the shipped Freedoom IWAD is
BSD. Details, and the offer of source for the engine, in `LICENSES.md`.
