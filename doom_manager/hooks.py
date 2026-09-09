from . import __version__ as app_version

app_name = "doom_manager"
app_title = "Doom Manager"
app_publisher = "Observatoire des Refontes Utiles"
app_description = "Model Doom gameplay data as Frappe DocTypes; WASM engine runs client-side."
app_email = "contact@example.org"
app_license = "MIT"

# Serve the game page assets
app_include_js = []
app_include_css = []

# /doom itself resolves to www/doom.html; deeper paths are vue-router routes of
# the same single-page app.
website_route_rules = [
    {"from_route": "/doom/<path:app_path>", "to_route": "doom"},
]