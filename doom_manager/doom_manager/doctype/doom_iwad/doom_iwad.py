import hashlib
import json
import os

import frappe
from frappe import _
from frappe.model.document import Document

# Hashes of IWADs that may be handed to anyone. Everything else is treated as
# someone's personal copy of a commercial game: playable by its owner, never
# served to another session.
#
# The shipped Freedoom is read from the build manifest rather than pinned here,
# so upgrading it in build.sh does not silently demote it. Extend the set for
# another free IWAD (freedoom2.wad, freedm.wad) by adding its hash to
# `doom_free_iwad_sha256` in site config -- there is no reliable way to tell a
# free WAD from a commercial one by inspecting its contents, so this is an
# allowlist on purpose.
_MANIFEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "public", "js", "doom.build.json",
)


def free_iwad_hashes():
    hashes = set(frappe.conf.get("doom_free_iwad_sha256") or [])
    try:
        with open(_MANIFEST) as f:
            shipped = json.load(f).get("default_iwad_sha256")
        if shipped:
            hashes.add(shipped)
    except (OSError, ValueError):
        pass
    return hashes


class DoomIwad(Document):
    def validate(self):
        self._describe_file()
        self._guard_default()

    def _describe_file(self):
        """Fill in name, size and hash from the attachment, and decide whether it
        is one of the IWADs we may serve to everyone."""
        if not self.wad_file:
            frappe.throw(_("Attach a WAD file"))

        path = self._full_path()
        if not os.path.isfile(path):
            frappe.throw(_("Attached file is missing on disk: {0}").format(self.wad_file))

        digest = hashlib.sha256()
        with open(path, "rb") as f:
            header = f.read(4)
            digest.update(header)
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)

        if header not in (b"IWAD", b"PWAD"):
            frappe.throw(_("That file is not a WAD (its header reads {0!r})").format(header))
        if header == b"PWAD":
            frappe.throw(_("This is a PWAD (a patch). The engine needs a full IWAD."))

        self.file_name = os.path.basename(path)
        self.file_size = os.path.getsize(path)
        self.sha256 = digest.hexdigest()
        self.is_free = 1 if self.sha256 in free_iwad_hashes() else 0

    def _guard_default(self):
        if not self.is_default:
            return

        # Marking a personal IWAD as the default would serve one player's copy of
        # a commercial game to every visitor, which is the thing this project
        # deliberately stopped doing.
        if not self.is_free:
            frappe.throw(
                _(
                    "Only a freely redistributable IWAD can be the default, because the "
                    "default is served to guests. {0} is not one of them."
                ).format(self.iwad_title)
            )
        if self.player:
            frappe.throw(_("A player-owned IWAD cannot be the default; leave Player empty."))

        for other in frappe.get_all(
            "Doom Iwad", filters={"is_default": 1, "name": ("!=", self.name)}
        ):
            frappe.db.set_value("Doom Iwad", other.name, "is_default", 0)

    def _full_path(self):
        return frappe.get_doc("File", {"file_url": self.wad_file}).get_full_path()

    def full_path(self):
        return self._full_path()

    def readable_by(self, user):
        """A global IWAD is readable by anyone; a personal one only by its owner."""
        if not self.player:
            return True
        return user == self.player
