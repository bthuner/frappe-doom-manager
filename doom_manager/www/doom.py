import frappe


def get_context(context):
	"""Host page for the frappe-ui SPA. `boot` is serialised into window.* by
	the html that `frontend/` builds into www/doom.html; frappe-ui's fetcher
	reads window.csrf_token from it."""
	context.no_cache = 1
	user = frappe.session.user
	is_guest = user == "Guest"
	context.boot = {
		"csrf_token": "" if is_guest else frappe.sessions.get_csrf_token(),
		"session_user": user,
		"full_name": "Guest" if is_guest else (frappe.utils.get_fullname(user) or user),
	}
	return context
