// Vue wrapper around the DoomGeneric WASM build (doom.js / doom.wasm / doom.data
// from GenericDoom_Frappe/build.sh). The engine is a process-wide singleton:
// emscripten's main loop cannot be torn down, so the module is created once
// and simply re-attached to whichever <canvas> is currently mounted.
import { reactive, readonly } from 'vue'

const ASSET_BASE = '/assets/doom_manager/js/'

// Key codes from doomgeneric/doomkeys.h
const KEY = {
  RIGHTARROW: 0xae, LEFTARROW: 0xac, UPARROW: 0xad, DOWNARROW: 0xaf,
  STRAFE_L: 0xa0, STRAFE_R: 0xa1, USE: 0xa2, FIRE: 0xa3,
  ESCAPE: 27, ENTER: 13, TAB: 9, BACKSPACE: 0x7f, PAUSE: 0xff,
  EQUALS: 0x3d, MINUS: 0x2d,
  RSHIFT: 0x80 + 0x36, RCTRL: 0x80 + 0x1d, RALT: 0x80 + 0x38,
  HOME: 0x80 + 0x47, END: 0x80 + 0x4f, PGUP: 0x80 + 0x49, PGDN: 0x80 + 0x51,
  INS: 0x80 + 0x52, DEL: 0xc8,
}

const CODE_MAP = {
  ArrowRight: KEY.RIGHTARROW, ArrowLeft: KEY.LEFTARROW,
  ArrowUp: KEY.UPARROW, ArrowDown: KEY.DOWNARROW,
  KeyW: KEY.UPARROW, KeyS: KEY.DOWNARROW, KeyA: KEY.STRAFE_L, KeyD: KEY.STRAFE_R,
  KeyE: KEY.USE, Space: KEY.USE,
  ControlLeft: KEY.FIRE, ControlRight: KEY.FIRE,
  ShiftLeft: KEY.RSHIFT, ShiftRight: KEY.RSHIFT,
  AltLeft: KEY.RALT, AltRight: KEY.RALT,
  Enter: KEY.ENTER, NumpadEnter: KEY.ENTER, Escape: KEY.ESCAPE, Tab: KEY.TAB,
  Backspace: KEY.BACKSPACE, Pause: KEY.PAUSE,
  Equal: KEY.EQUALS, NumpadAdd: KEY.EQUALS, Minus: KEY.MINUS, NumpadSubtract: KEY.MINUS,
  Home: KEY.HOME, End: KEY.END, PageUp: KEY.PGUP, PageDown: KEY.PGDN,
  Insert: KEY.INS, Delete: KEY.DEL,
}
for (let f = 1; f <= 10; f++) CODE_MAP['F' + f] = 0x80 + 0x3b + (f - 1)
CODE_MAP.F11 = 0x80 + 0x57
CODE_MAP.F12 = 0x80 + 0x58

function doomKeyFor(ev) {
  if (Object.prototype.hasOwnProperty.call(CODE_MAP, ev.code)) return CODE_MAP[ev.code]
  // Letters, digits and punctuation: Doom expects lowercase ASCII. ev.key keeps
  // this layout-independent (cheat codes, menu shortcuts).
  if (typeof ev.key === 'string' && ev.key.length === 1) {
    const c = ev.key.toLowerCase().charCodeAt(0)
    if (c >= 0x20 && c < 0x7f) return c
  }
  return 0
}

const state = reactive({
  status: 'idle', // idle | loading | ready | error
  message: '',
  level: null,
  // Raw counts, with what the level holds alongside: 6 kills out of 9, not 67%.
  kills: null,
  items: null,
  secrets: null,
  totalKills: null,
  totalItems: null,
  totalSecrets: null,
  timeSeconds: null,
  outcome: null, // null while the level is running, then 'Completed' | 'Died'
  completedRuns: 0,
})

let module = null
let modulePromise = null
let canvas = null
let ctx = null
let image = null
let pixels = null
let pending = []
let active = false // key events are only forwarded while the Play page is visible
const down = {}
const startListeners = new Set()
const endListeners = new Set()

function blitFrame(ptr, w, h) {
  if (!module || !canvas) return
  if (!image || image.width !== w || image.height !== h) {
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
    }
    image = ctx.createImageData(w, h)
    pixels = new Uint32Array(image.data.buffer)
  }
  // Always re-read HEAPU32: the view is replaced when memory grows.
  const src = module.HEAPU32.subarray(ptr >> 2, (ptr >> 2) + w * h)
  // Engine packs 0x00RRGGBB; ImageData is RGBA bytes = little-endian 0xAABBGGRR.
  for (let i = 0, n = w * h; i < n; i++) {
    const p = src[i]
    pixels[i] = 0xff000000 | ((p & 0xff) << 16) | (p & 0xff00) | ((p >>> 16) & 0xff)
  }
  ctx.putImageData(image, 0, 0)
}

window.DoomBridge = Object.assign(window.DoomBridge || {}, {
  _blitFrame: blitFrame,
  onTitle() {},
})

// The three hooks injected by GenericDoom_Frappe/patch_doom_bridge.py. Episode
// and map are 1-based on all of them, and every count comes with its level
// total. A run is opened on start and closed on end, whichever way it ends.
const levelNameFor = (episode, map) => 'E' + episode + 'M' + map

window.onDoomLevelStart = function (episode, map, totalKills, totalItems, totalSecrets) {
  const payload = {
    level: levelNameFor(episode, map),
    total_kills: totalKills,
    total_items: totalItems,
    total_secrets: totalSecrets,
  }
  Object.assign(state, {
    level: payload.level,
    kills: 0,
    items: 0,
    secrets: 0,
    totalKills,
    totalItems,
    totalSecrets,
    timeSeconds: 0,
    outcome: null,
  })
  startListeners.forEach((fn) => fn(payload))
}

// Pushed ~5x a second while a level is being played, so the counters and the
// clock move with the game instead of jumping at the intermission screen. No
// listener set: the tiles read engine.state directly, and a run is only written
// to the server at the level's start and end.
window.onDoomStats = function (kills, totalKills, items, totalItems, secrets, totalSecrets, seconds) {
  Object.assign(state, {
    kills,
    items,
    secrets,
    totalKills,
    totalItems,
    totalSecrets,
    timeSeconds: seconds,
  })
}

function levelEnded(outcome, episode, map, kills, totalKills, items, totalItems,
                    secrets, totalSecrets, seconds) {
  const payload = {
    level: levelNameFor(episode, map),
    outcome,
    kills,
    items,
    secrets,
    time_seconds: seconds,
  }
  Object.assign(state, {
    level: payload.level,
    kills,
    items,
    secrets,
    totalKills,
    totalItems,
    totalSecrets,
    timeSeconds: seconds,
    outcome,
    completedRuns: state.completedRuns + (outcome === 'Completed' ? 1 : 0),
  })
  endListeners.forEach((fn) => fn(payload))
}

// Reached the exit: fired from wi_stuff.c as the intermission screen starts.
window.onDoomLevelComplete = (...stats) => levelEnded('Completed', ...stats)

// Died: Doom 1 has no GAME OVER screen, so this comes from G_DoReborn, which is
// what single player does instead -- it reloads the level, which in turn opens
// the next run through onDoomLevelStart.
window.onDoomGameOver = (...stats) => levelEnded('Died', ...stats)

function pushKey(pressed, key) {
  if (!module) {
    pending.push([pressed, key])
    return
  }
  module.ccall('DG_PushKey', null, ['number', 'number'], [pressed, key])
}

function isTyping(ev) {
  const t = ev.target
  return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)
}

function releaseAll() {
  Object.keys(down).forEach((code) => {
    const key = CODE_MAP[code]
    if (key) pushKey(0, key)
    delete down[code]
  })
}

window.addEventListener('keydown', (ev) => {
  if (!active || isTyping(ev)) return
  const key = doomKeyFor(ev)
  if (!key) return
  ev.preventDefault()
  if (down[ev.code]) return // ignore auto-repeat
  down[ev.code] = true
  pushKey(1, key)
})
window.addEventListener('keyup', (ev) => {
  if (!active || isTyping(ev)) return
  const key = doomKeyFor(ev)
  if (!key) return
  ev.preventDefault()
  delete down[ev.code]
  pushKey(0, key)
})
window.addEventListener('blur', releaseAll)
window.addEventListener('mouseup', (ev) => {
  if (active) pushKey(0, ev.button === 2 ? KEY.USE : KEY.FIRE)
})

function loadScript() {
  if (typeof window.createDoomModule === 'function') return Promise.resolve()
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = ASSET_BASE + 'doom.js'
    s.onload = resolve
    s.onerror = () => reject(new Error('doom.js not found: run GenericDoom_Frappe/build.sh first'))
    document.head.appendChild(s)
  })
}

function boot() {
  if (modulePromise) return modulePromise
  state.status = 'loading'
  state.message = 'Loading DOOM…'
  modulePromise = loadScript()
    .then(() =>
      window.createDoomModule({
        canvas,
        locateFile: (path) => ASSET_BASE + path,
        // No -iwad: hardcoding the filename here duplicated a decision that
        // lives in build.sh, and the two silently drifted apart the moment the
        // shipped WAD changed. Left alone, the engine searches for every IWAD
        // name it knows (d_iwad.c iwads[]) in FILES_DIR "." -- which is / under
        // Emscripten, where build.sh preloads whichever WAD it used.
        arguments: [],
        print: (text) => console.log('[doom]', text),
        printErr: (text) => console.warn('[doom]', text),
      }),
    )
    .then((m) => {
      module = m
      window.DoomBridge.module = m
      pending.forEach((k) => pushKey(k[0], k[1]))
      pending = []
      state.status = 'ready'
      state.message = 'Press Esc for the menu, Enter to confirm.'
      return m
    })
    .catch((err) => {
      state.status = 'error'
      state.message = String(err && err.message ? err.message : err)
      console.error(err)
      throw err
    })
  return modulePromise
}

export function useDoomEngine() {
  return {
    state: readonly(state),
    KEY,
    /** Bind (or re-bind) the engine's output to a canvas element and start it. */
    attach(el) {
      canvas = el
      ctx = el.getContext('2d')
      image = null
      pixels = null
      boot().catch(() => {})
    },
    /** Whether keyboard/mouse input is forwarded to the engine. */
    setActive(value) {
      active = value
      if (!value) releaseAll()
    },
    pushKey,
    /** Simulate a full key press (menu navigation from UI buttons). */
    tap(key) {
      pushKey(1, key)
      setTimeout(() => pushKey(0, key), 60)
    },
    /** Called when a level starts, i.e. when a run should be opened. */
    onLevelStart(fn) {
      startListeners.add(fn)
      return () => startListeners.delete(fn)
    },
    /** Called when a level ends, by the exit or by death; payload.outcome says which. */
    onLevelEnd(fn) {
      endListeners.add(fn)
      return () => endListeners.delete(fn)
    },
  }
}
