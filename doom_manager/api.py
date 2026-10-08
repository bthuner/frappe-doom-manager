import json
import os

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


# ---------------------------------------------------------------- IWADs -----
#
# The engine no longer carries a WAD: build.sh emits doom.js/doom.wasm plus the
# shipped Freedoom as a separate static asset, and the page fetches whichever
# IWAD applies to the session and writes it into the engine's filesystem before
# main() runs. That is what lets a player bring their own without rebuilding.
#
# The rule that shapes all of this: a personal IWAD is somebody's copy of a
# commercial game. It is playable by its owner and by nobody else, and it can
# never become the default, which is what guests are served.

_MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "public", "js", "doom.build.json"
)
_ASSET_BASE = "/assets/doom_manager/js/"


def build_manifest():
    """Engine version and shipped IWAD, written by build.sh."""
    try:
        with open(_MANIFEST_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _iwad_payload(doc=None):
    """What the browser needs to fetch and mount an IWAD."""
    if doc is None:
        manifest = build_manifest()
        file_name = manifest.get("default_iwad")
        if not file_name:
            return None
        return {
            "name": None,
            "title": "Freedoom: Phase 1",
            "file_name": file_name,
            "file_size": manifest.get("default_iwad_size"),
            "is_free": True,
            "is_shipped": True,
            "owned": False,
            # Static, public, BSD-licensed: no permission check to do, and the
            # browser can cache it across engine rebuilds.
            "url": _ASSET_BASE + file_name,
        }

    return {
        "name": doc.name,
        "title": doc.iwad_title,
        "file_name": doc.file_name,
        "file_size": doc.file_size,
        "is_free": bool(doc.is_free),
        "is_shipped": False,
        "owned": bool(doc.player),
        "url": "/api/method/doom_manager.api.download_iwad?iwad=" + doc.name,
    }


def _readable_iwad(name, user):
    doc = frappe.get_doc("Doom Iwad", name)
    if not doc.readable_by(user):
        frappe.throw(_("That IWAD belongs to another player"), frappe.PermissionError)
    return doc


@frappe.whitelist(allow_guest=True)
def list_iwads():
    """Global IWADs plus the caller's own. Never anyone else's."""
    user = frappe.session.user
    rows = frappe.get_all(
        "Doom Iwad",
        fields=["name", "iwad_title", "file_name", "file_size", "is_free", "is_default", "player"],
        filters={"player": ("in", ["", user] if user != "Guest" else [""])},
        order_by="player asc, iwad_title asc",
    )
    out = [_iwad_payload()]  # the shipped Freedoom is always available
    for r in rows:
        out.append(
            {
                "name": r.name,
                "title": r.iwad_title,
                "file_name": r.file_name,
                "file_size": r.file_size,
                "is_free": bool(r.is_free),
                "is_shipped": False,
                "owned": r.player == user and bool(r.player),
                "is_default": bool(r.is_default),
                "url": "/api/method/doom_manager.api.download_iwad?iwad=" + r.name,
            }
        )
    active = get_active_iwad()
    for entry in out:
        entry["active"] = entry["name"] == active["name"]
    return out


@frappe.whitelist(allow_guest=True)
def get_active_iwad():
    """The IWAD this session should play: the player's choice, else the global
    default, else the shipped Freedoom."""
    user = frappe.session.user

    if user != "Guest":
        chosen = frappe.db.get_value("Doom Player Setting", user, "iwad")
        if chosen and frappe.db.exists("Doom Iwad", chosen):
            doc = frappe.get_doc("Doom Iwad", chosen)
            if doc.readable_by(user):
                return _iwad_payload(doc)

    default = frappe.db.get_value("Doom Iwad", {"is_default": 1}, "name")
    if default:
        return _iwad_payload(frappe.get_doc("Doom Iwad", default))

    return _iwad_payload()


@frappe.whitelist()
def register_iwad(file_url, title=None):
    """Turn a file already uploaded through Frappe into a Doom Iwad owned by the
    caller. The controller hashes it, rejects anything that is not an IWAD, and
    decides whether it is free."""
    player = _require_user()

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    if file_doc.owner != player and "System Manager" not in frappe.get_roles(player):
        frappe.throw(_("That upload belongs to another user"), frappe.PermissionError)

    if not file_doc.is_private:
        file_doc.is_private = 1
        file_doc.save(ignore_permissions=True)

    doc = frappe.get_doc(
        {
            "doctype": "Doom Iwad",
            "iwad_title": (title or "").strip() or os.path.basename(file_url),
            "wad_file": file_url,
            "player": player,
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    frappe.logger("doom_manager").info(
        "Doom Iwad %s registered by %s (%s bytes, free=%s)",
        doc.name, player, doc.file_size, bool(doc.is_free),
    )
    return _iwad_payload(doc)


@frappe.whitelist()
def select_iwad(iwad=None):
    """Remember which IWAD this player wants. Passing nothing clears the choice
    and falls back to the default."""
    player = _require_user()

    if iwad:
        _readable_iwad(iwad, player)

    if frappe.db.exists("Doom Player Setting", player):
        setting = frappe.get_doc("Doom Player Setting", player)
        setting.iwad = iwad or None
        setting.flags.ignore_permissions = True
        setting.save(ignore_permissions=True)
    else:
        setting = frappe.get_doc(
            {"doctype": "Doom Player Setting", "player": player, "iwad": iwad or None}
        )
        setting.flags.ignore_permissions = True
        setting.insert(ignore_permissions=True)
    frappe.db.commit()
    return get_active_iwad()


@frappe.whitelist()
def set_default_iwad(iwad):
    """Administrators only. The controller refuses anything but a free IWAD."""
    _require_user()
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Only an administrator can change the default"), frappe.PermissionError)

    doc = frappe.get_doc("Doom Iwad", iwad)
    doc.is_default = 1
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return _iwad_payload(doc)


@frappe.whitelist()
def delete_iwad(iwad):
    """Remove one of the caller's own IWADs."""
    player = _require_user()
    doc = frappe.get_doc("Doom Iwad", iwad)
    if doc.player != player:
        frappe.throw(_("You can only remove your own IWADs"), frappe.PermissionError)

    if frappe.db.get_value("Doom Player Setting", player, "iwad") == iwad:
        frappe.db.set_value("Doom Player Setting", player, "iwad", None)

    frappe.delete_doc("Doom Iwad", iwad, ignore_permissions=True)
    frappe.db.commit()
    return get_active_iwad()


@frappe.whitelist(allow_guest=True)
def download_iwad(iwad):
    """Stream an IWAD to the session that is allowed to have it.

    Guests reach this only for global IWADs; a personal one is refused by
    readable_by(), so one player's copy of a commercial game never leaves their
    own session."""
    doc = _readable_iwad(iwad, frappe.session.user)

    with open(doc.full_path(), "rb") as f:
        content = f.read()

    frappe.local.response.filename = doc.file_name
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
