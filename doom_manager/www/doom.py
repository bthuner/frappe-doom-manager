import frappe

from doom_manager.api import build_manifest


def get_context(context):
	"""Host page for the frappe-ui SPA. `boot` is serialised into window.* by
	the html that `frontend/` builds into www/doom.html; frappe-ui's fetcher
	reads window.csrf_token from it."""
	context.no_cache = 1
	user = frappe.session.user
	is_guest = user == "Guest"
	# The engine assets are not content-hashed and Frappe serves /assets with no
	# Cache-Control, so a browser can hold a stale doom.js or doom.wasm forever.
	# This page is no_cache, so it is the one place that can hand the SPA a fresh
	# build id to hang on those URLs as a query string.
	context.boot = {
		"csrf_token": "" if is_guest else frappe.sessions.get_csrf_token(),
		"session_user": user,
		"full_name": "Guest" if is_guest else (frappe.utils.get_fullname(user) or user),
		"engine_version": build_manifest().get("version", "dev"),
	}
	return context
