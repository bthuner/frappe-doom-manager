#!/usr/bin/env python3
"""
patch_doom_bridge.py -- injects the Frappe run-tracking bridge into DoomGeneric.

A Doom Run is opened when a level starts and closed when it ends, either by
reaching the exit or by dying. That needs three hooks, in two files:

  g_game.c   G_Ticker          -> window.onDoomLevelStart(ep, map, tk, ti, ts)
  g_game.c   G_DoReborn        -> window.onDoomGameOver(ep, map, k, tk, i, ti, s, ts, secs)
  wi_stuff.c WI_initVariables  -> window.onDoomLevelComplete(same shape)

Why the start hook lives in G_Ticker rather than in G_DoLoadLevel, the obvious
place: G_DoPlayDemo() calls G_InitNew() -- which loads the level and clears
demoplayback -- and only sets demoplayback = true *after* it returns. Inside
G_DoLoadLevel the flag is therefore false even for the attract-mode demos, and
every idle title screen would open a run. Testing (levelstarttic, gamemap) once
per tic instead sees the flag settled, one tic (~28 ms) after the load.

Counts are raw with their level totals alongside (6 kills out of 9), not the
percentages the intermission screen shows; the UI can always divide. Episode
and map are 1-based on all three hooks -- wminfo's are 0-based, so the
level-complete hook adds one to match the other two.

Idempotent: blocks from any previous version of this script are replaced.

Usage:
    python3 patch_doom_bridge.py path/to/doomgeneric/doomgeneric
"""
import os
import re
import sys

VERSION = "v3"
PREFIX = "/* FRAPPE_DOOM_BRIDGE"

INCLUDE = """
%s_INCLUDE %s */
#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif
""" % (PREFIX, VERSION)

# --- g_game.c: level start, once per (levelstarttic, gamemap), real games only.
START = """
%s_START %s */
#ifdef __EMSCRIPTEN__
    {
        static int fdb_last_tic = -1;
        static int fdb_last_map = -1;

        if (gamestate == GS_LEVEL && usergame && !demoplayback
            && (levelstarttic != fdb_last_tic || gamemap != fdb_last_map))
        {
            fdb_last_tic = levelstarttic;
            fdb_last_map = gamemap;
            EM_ASM({
                if (window.onDoomLevelStart) {
                    window.onDoomLevelStart($0, $1, $2, $3, $4);
                }
            }, gameepisode, gamemap, totalkills, totalitems, totalsecret);
        }
    }
#endif
""" % (PREFIX, VERSION)

# --- g_game.c: death. Doom 1 has no GAME OVER screen; in single player dying
# routes through G_DoReborn, which reloads the level (gameaction = ga_loadlevel).
# That reload bumps levelstarttic, so the start hook opens the next run by itself.
GAMEOVER = """
%s_GAMEOVER %s */
#ifdef __EMSCRIPTEN__
    if (!netgame && !demoplayback && usergame && playernum == consoleplayer)
    {
        player_t *fdb_p = &players[playernum];

        EM_ASM({
            if (window.onDoomGameOver) {
                window.onDoomGameOver($0, $1, $2, $3, $4, $5, $6, $7, $8);
            }
        }, gameepisode, gamemap,
           fdb_p->killcount,   totalkills,
           fdb_p->itemcount,   totalitems,
           fdb_p->secretcount, totalsecret,
           leveltime / 35);
    }
#endif
""" % (PREFIX, VERSION)

# --- wi_stuff.c: level finished by reaching the exit.
COMPLETE = """
%s_COMPLETE %s */
#ifdef __EMSCRIPTEN__
    {
        int fdb_pnum = wminfo.pnum;

        EM_ASM({
            if (window.onDoomLevelComplete) {
                window.onDoomLevelComplete($0, $1, $2, $3, $4, $5, $6, $7, $8);
            }
        }, wminfo.epsd + 1, wminfo.last + 1,
           wminfo.plyr[fdb_pnum].skills,  wminfo.maxkills,
           wminfo.plyr[fdb_pnum].sitems,  wminfo.maxitems,
           wminfo.plyr[fdb_pnum].ssecret, wminfo.maxsecret,
           wminfo.plyr[fdb_pnum].stime / 35);
    }
#endif
""" % (PREFIX, VERSION)

# (file, human-readable hook name, regex matching the opening brace, code)
INJECTIONS = [
    ("g_game.c", "G_Ticker",
     r"(void\s+G_Ticker\s*\(\s*void\s*\)\s*\{)", START),
    ("g_game.c", "G_DoReborn",
     r"(void\s+G_DoReborn\s*\(\s*int\s+playernum\s*\)\s*\{)", GAMEOVER),
    ("wi_stuff.c", "WI_initVariables",
     r"(void\s+WI_initVariables\s*\([^)]*\)\s*\{)", COMPLETE),
]

# Any block this script ever injected, up to its closing #endif.
BLOCK_RE = re.compile(r"\n*" + re.escape(PREFIX) + r"_[A-Z]+ v\d+ \*/.*?\n#endif\n", re.DOTALL)


def patch_file(path, hooks):
    with open(path) as f:
        src = f.read()

    src, removed = BLOCK_RE.subn("", src)
    if removed:
        print("  removed %d stale block(s)" % removed)

    # Inject bottom-up so earlier match offsets stay valid.
    found = []
    for name, anchor, code in hooks:
        m = re.search(anchor, src, re.MULTILINE)
        if not m:
            sys.exit("ERROR: could not locate %s in %s" % (name, path))
        found.append((m.end(), name, code))

    for end, name, code in sorted(found, reverse=True):
        src = src[:end] + code + src[end:]
        print("  injected into %s" % name)

    # emscripten.h goes after the last #include at the top of the file.
    includes = list(re.finditer(r"^#include\s+[<\"].*$", src, re.MULTILINE))
    if not includes:
        sys.exit("ERROR: no #include lines found in %s" % path)
    top = includes[-1].end()
    src = src[:top] + "\n" + INCLUDE + src[top:]

    with open(path, "w") as f:
        f.write(src)


def main(src_dir):
    by_file = {}
    for filename, name, anchor, code in INJECTIONS:
        by_file.setdefault(filename, []).append((name, anchor, code))

    for filename, hooks in by_file.items():
        path = os.path.join(src_dir, filename)
        if not os.path.isfile(path):
            sys.exit("ERROR: %s not found (is %s the doomgeneric source dir?)" % (path, src_dir))
        print("Patching %s (%s)" % (filename, VERSION))
        patch_file(path, hooks)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
