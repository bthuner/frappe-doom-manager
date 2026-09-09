import frappe
from frappe import _
from frappe.utils import cint

# A run is opened when the level starts and closed when it ends. "Died" covers
# what Doom 1 has instead of a GAME OVER screen: in single player, dying routes
# through G_DoReborn, which reloads the level.
OUTCOME_IN_PROGRESS = "In Progress"
OUTCOME_COMPLETED = "Completed"
OUTCOME_DIED = "Died"
FINAL_OUTCOMES = (OUTCOME_COMPLETED, OUTCOME_DIED)


def _require_user():
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in to save Doom runs"), frappe.PermissionError)
	return frappe.session.user


def _get_or_create_level(level):
	"""Doom Level is looked up by level_name and created on first sight, since
	the DocType has no autoname and its names are hashes."""
	level = (level or "").strip().upper()
	if not level:
		frappe.throw(_("Missing level name"))

	name = frappe.db.get_value("Doom Level", {"level_name": level}, "name")
	if name:
		return name

	episode = level[1] if len(level) >= 2 and level[0] == "E" else ""
	doc = frappe.get_doc(
		{"doctype": "Doom Level", "level_name": level, "episode": episode}
	).insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def start_run(level, total_kills=0, total_items=0, total_secrets=0):
	"""Open a draft Doom Run as a level starts.

	`level` is the map name reported by the engine (e.g. "E1M1"); the totals are
	what the level holds, so finish_run only has to supply what was achieved.
	The draft stays at docstatus 0 until finish_run submits it -- a player who
	closes the tab mid-level simply leaves a draft behind.
	"""
	player = _require_user()

	run = frappe.get_doc(
		{
			"doctype": "Doom Run",
			"player": player,
			"level": _get_or_create_level(level),
			"outcome": OUTCOME_IN_PROGRESS,
			"kills": 0,
			"items": 0,
			"secrets": 0,
			"total_kills": cint(total_kills),
			"total_items": cint(total_items),
			"total_secrets": cint(total_secrets),
			"deaths": 0,
			"time_seconds": 0,
			"completed": 0,
		}
	)
	run.flags.ignore_permissions = True
	run.insert(ignore_permissions=True)
	frappe.db.commit()

	frappe.logger("doom_manager").info(
		"Doom Run %s: %s started %s (%s monsters, %s items, %s secrets)",
		run.name, player, level, cint(total_kills), cint(total_items), cint(total_secrets),
	)
	return run.name


@frappe.whitelist()
def finish_run(run, outcome=OUTCOME_COMPLETED, kills=0, items=0, secrets=0, time_seconds=0):
	"""Close the draft opened by start_run and submit it.

	`outcome` is "Completed" (reached the exit) or "Died". Counts are raw, not
	percentages: the level totals are already on the draft.
	"""
	player = _require_user()

	if outcome not in FINAL_OUTCOMES:
		frappe.throw(_("Unknown outcome {0}").format(outcome))

	doc = frappe.get_doc("Doom Run", run)
	if doc.player != player:
		frappe.throw(_("This run belongs to another player"), frappe.PermissionError)
	if doc.docstatus != 0:
		frappe.throw(_("Run {0} is already closed").format(run))

	completed = outcome == OUTCOME_COMPLETED
	doc.outcome = outcome
	doc.kills = cint(kills)
	doc.items = cint(items)
	doc.secrets = cint(secrets)
	doc.time_seconds = cint(time_seconds)
	doc.deaths = 0 if completed else 1
	doc.completed = 1 if completed else 0
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	doc.submit()
	frappe.db.commit()

	frappe.logger("doom_manager").info(
		"Doom Run %s: %s %s after %ss (%s/%s kills, %s/%s items, %s/%s secrets)",
		doc.name, player, outcome.lower(), doc.time_seconds,
		doc.kills, doc.total_kills, doc.items, doc.total_items, doc.secrets, doc.total_secrets,
	)
	return doc.name


@frappe.whitelist()
def record_run(level, kills=0, items=0, secrets=0, time_seconds=0, outcome=OUTCOME_COMPLETED,
			   total_kills=0, total_items=0, total_secrets=0):
	"""One-shot open-and-close, for callers that only see the end of a level."""
	run = start_run(level, total_kills, total_items, total_secrets)
	return finish_run(run, outcome, kills, items, secrets, time_seconds)


RUN_FIELDS = [
	"name", "player", "level", "outcome",
	"kills", "items", "secrets",
	"total_kills", "total_items", "total_secrets",
	"deaths", "time_seconds", "completed", "creation",
]


def _level_names():
	return {
		d.name: d.level_name
		for d in frappe.get_all("Doom Level", fields=["name", "level_name"])
	}


def _full_names(users):
	names = {}
	for user in set(users):
		names[user] = frappe.utils.get_fullname(user) or user
	return names


def _decorate(runs):
	levels = _level_names()
	players = _full_names(r.player for r in runs)
	for r in runs:
		r.level_name = levels.get(r.level, r.level)
		r.player_name = players.get(r.player, r.player)
	return runs


@frappe.whitelist(allow_guest=True)
def get_runs(limit=25):
	"""Latest closed runs for the frontend feed. Drafts (docstatus 0) are runs
	still in progress and are left out. Guests may read: runs are public scores,
	and get_all ignores DocType permissions anyway."""
	return _decorate(
		frappe.get_all(
			"Doom Run",
			fields=RUN_FIELDS,
			filters={"docstatus": 1},
			order_by="creation desc",
			limit=cint(limit) or 25,
		)
	)


@frappe.whitelist(allow_guest=True)
def get_leaderboard():
	"""Per level: fastest completed run, best kill count and run count. Only
	runs that reached the exit are ranked -- a death has no meaningful time."""
	runs = _decorate(
		frappe.get_all(
			"Doom Run",
			fields=RUN_FIELDS,
			filters={"docstatus": 1, "completed": 1},
			order_by="time_seconds asc",
		)
	)
	board = {}
	for r in runs:
		entry = board.setdefault(
			r.level,
			{
				"level": r.level,
				"level_name": r.level_name,
				"runs": 0,
				"fastest": None,
				"most_kills": None,
			},
		)
		entry["runs"] += 1
		if entry["fastest"] is None:  # runs are sorted by time_seconds asc
			entry["fastest"] = r
		if entry["most_kills"] is None or cint(r.kills) > cint(entry["most_kills"].kills):
			entry["most_kills"] = r
	return sorted(board.values(), key=lambda e: e["level_name"])
