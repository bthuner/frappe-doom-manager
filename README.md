# Doom Manager — Frappe App

A civic-tech-flavored side project: model Doom's gameplay data (monsters, weapons,
levels, spawn placement, and play sessions) as Frappe DocTypes, while the actual
game engine runs client-side as WebAssembly in the browser.

## What's included

- `doom_manager/doom_manager/doctype/doom_monster` — reference DocType for monster stats
- `doom_manager/doom_manager/doctype/doom_weapon` — reference DocType for weapons
- `doom_manager/doom_manager/doctype/doom_level` — parent DocType for a level/map
- `doom_manager/doom_manager/doctype/doom_level_monster` — child table: monster spawns on a level
- `doom_manager/doom_manager/doctype/doom_level_item` — child table: item pickups on a level
- `doom_manager/doom_manager/doctype/doom_run` — submittable DocType logging a completed play session
- `doom_manager/doom_manager/www/doom/index.html` — browser page hosting the WASM Doom canvas
- `doom_manager/doom_manager/public/js/doom_engine.js` — boots the WASM engine, paints the canvas, maps keys
- `doom_manager/doom_manager/public/js/doom_run.js` — sends level results to `doom_manager.api.record_run`
- `doom_manager/doom_manager/api.py` — whitelisted endpoint that stores a Doom Run

## Install

The quickest route is the Docker stack in the sibling repo:

```bash
cd ../GenericDoom_Frappe          # build the WASM engine into this app's public/js
./build.sh
cd docker && docker compose build && docker compose up -d
# http://localhost:8099/doom  (Administrator / admin)
```

On an existing bench:

```bash
cd frappe-bench
bench get-app doom_manager /path/to/this/folder
bench --site your-site.local install-app doom_manager
bench build --app doom_manager    # links public/ into sites/assets
```

The engine files `public/js/doom.js`, `doom.wasm`, `doom.data` are produced by
`GenericDoom_Frappe/build.sh`; the page at `/doom` shows an error until they exist.

## Notes

- Play works for guests; saving a `Doom Run` needs a logged-in user. The page
  calls the whitelisted `doom_manager.api.record_run`, which get-or-creates the
  `Doom Level` (looked up by `level_name`, e.g. `E1M1`) and inserts + submits
  the run with `ignore_permissions`, so no API keys live in client JS.
- `doom_level_monster` and `doom_level_item` are child tables (`istable: 1`); full
  WAD geometry is out of scope. Only gameplay/meta data is modelled.
- Rendering, input and the tick loop stay in JS/WASM (`public/js/doom_engine.js`).
- Set `developer_mode = 1` in the site config before editing DocType JSON directly.
