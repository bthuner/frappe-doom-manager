// doom_engine.js
// Boots the DoomGeneric WASM build (doom.js / doom.wasm / doom.data, produced
// by GenericDoom_Frappe/build.sh) and connects it to the page:
//   - DoomBridge._blitFrame(ptr, w, h): paints the engine's framebuffer
//   - keyboard/mouse -> DG_PushKey(pressed, doomKey)
//   - window.onDoomLevelComplete(...) -> DoomBridge.onLevelComplete({...})
// Load order in www/doom/index.html: doom.js, doom_run.js, then this file.

(function () {
  "use strict";

  var ASSET_BASE = "/assets/doom_manager/js/";

  // Key codes from doomgeneric/doomkeys.h
  var KEY = {
    RIGHTARROW: 0xae, LEFTARROW: 0xac, UPARROW: 0xad, DOWNARROW: 0xaf,
    STRAFE_L: 0xa0, STRAFE_R: 0xa1, USE: 0xa2, FIRE: 0xa3,
    ESCAPE: 27, ENTER: 13, TAB: 9, BACKSPACE: 0x7f, PAUSE: 0xff,
    EQUALS: 0x3d, MINUS: 0x2d,
    RSHIFT: 0x80 + 0x36, RCTRL: 0x80 + 0x1d, RALT: 0x80 + 0x38,
    HOME: 0x80 + 0x47, END: 0x80 + 0x4f, PGUP: 0x80 + 0x49, PGDN: 0x80 + 0x51,
    INS: 0x80 + 0x52, DEL: 0xc8,
  };

  var CODE_MAP = {
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
  };
  for (var f = 1; f <= 10; f++) CODE_MAP["F" + f] = 0x80 + 0x3b + (f - 1);
  CODE_MAP.F11 = 0x80 + 0x57;
  CODE_MAP.F12 = 0x80 + 0x58;

  function doomKeyFor(ev) {
    if (CODE_MAP.hasOwnProperty(ev.code)) return CODE_MAP[ev.code];
    // Letters, digits and punctuation: Doom expects lowercase ASCII. Using
    // ev.key keeps this layout-independent (cheat codes, menu shortcuts, chat).
    if (typeof ev.key === "string" && ev.key.length === 1) {
      var c = ev.key.toLowerCase().charCodeAt(0);
      if (c >= 0x20 && c < 0x7f) return c;
    }
    return 0;
  }

  var bridge = (window.DoomBridge = window.DoomBridge || {});
  var canvas = document.getElementById("doom-canvas");
  var ctx = canvas.getContext("2d");
  var image = null;   // ImageData reused every frame
  var pixels = null;  // Uint32Array view over image.data
  var module = null;
  var pending = [];   // keys pushed before the module is ready

  bridge._blitFrame = function (ptr, w, h) {
    if (!module) return;
    if (!image || image.width !== w || image.height !== h) {
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      image = ctx.createImageData(w, h);
      pixels = new Uint32Array(image.data.buffer);
    }
    // Always re-read HEAPU32: the view is replaced when memory grows.
    var src = module.HEAPU32.subarray(ptr >> 2, (ptr >> 2) + w * h);
    // Engine packs 0x00RRGGBB; ImageData is RGBA bytes = little-endian 0xAABBGGRR.
    for (var i = 0, n = w * h; i < n; i++) {
      var p = src[i];
      pixels[i] = 0xff000000 | ((p & 0xff) << 16) | (p & 0xff00) | ((p >>> 16) & 0xff);
    }
    ctx.putImageData(image, 0, 0);
  };

  bridge.onTitle = function (title) {
    document.title = title + " — Frappe";
  };

  function pushKey(pressed, key) {
    if (!module) {
      pending.push([pressed, key]);
      return;
    }
    module.ccall("DG_PushKey", null, ["number", "number"], [pressed, key]);
  }

  function isTyping(ev) {
    var t = ev.target;
    return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
  }

  var down = {};
  window.addEventListener("keydown", function (ev) {
    if (isTyping(ev)) return;
    var key = doomKeyFor(ev);
    if (!key) return;
    ev.preventDefault();
    if (down[ev.code]) return; // ignore auto-repeat
    down[ev.code] = true;
    pushKey(1, key);
  });
  window.addEventListener("keyup", function (ev) {
    if (isTyping(ev)) return;
    var key = doomKeyFor(ev);
    if (!key) return;
    ev.preventDefault();
    delete down[ev.code];
    pushKey(0, key);
  });
  window.addEventListener("blur", function () {
    // Release everything so the player doesn't keep running when focus is lost.
    Object.keys(down).forEach(function (code) {
      var key = CODE_MAP[code];
      if (key) pushKey(0, key);
    });
    down = {};
  });

  // Mouse: click on the canvas fires, right click uses.
  canvas.addEventListener("contextmenu", function (ev) { ev.preventDefault(); });
  canvas.addEventListener("mousedown", function (ev) {
    ev.preventDefault();
    canvas.focus();
    pushKey(1, ev.button === 2 ? KEY.USE : KEY.FIRE);
  });
  window.addEventListener("mouseup", function (ev) {
    pushKey(0, ev.button === 2 ? KEY.USE : KEY.FIRE);
  });

  // Level complete, fired from the patched wi_stuff.c (WI_initVariables).
  // epsd/last are 0-based; kills/items/secrets are percentages.
  window.onDoomLevelComplete = function (epsd, last, kills, items, secrets, seconds) {
    var level = "E" + (epsd + 1) + "M" + (last + 1);
    var payload = {
      level: level,
      kills: kills,
      items: items,
      secrets: secrets,
      time_seconds: seconds,
      completed: 1,
    };
    if (bridge.onTick) bridge.onTick({ level: level, kills: kills, time_seconds: seconds });
    if (bridge.onLevelComplete) bridge.onLevelComplete(payload);
  };

  function setStatus(text) {
    var el = document.getElementById("doom-status");
    if (el) el.textContent = text;
  }

  if (typeof createDoomModule !== "function") {
    setStatus("doom.js not found: run GenericDoom_Frappe/build.sh first.");
    console.error("doom_engine.js: createDoomModule is undefined (doom.js missing?)");
    return;
  }

  setStatus("Loading DOOM…");
  createDoomModule({
    canvas: canvas,
    locateFile: function (path) { return ASSET_BASE + path; },
    arguments: ["-iwad", "/doom1.wad"],
    print: function (text) { console.log("[doom]", text); },
    printErr: function (text) { console.warn("[doom]", text); },
    onRuntimeInitialized: function () {
      setStatus("Press Enter to start. Arrows/WASD move, Ctrl or click fires, Space/E uses, Esc menu.");
    },
  }).then(function (m) {
    module = m;
    bridge.module = m;
    pending.forEach(function (k) { pushKey(k[0], k[1]); });
    pending = [];
  }).catch(function (err) {
    setStatus("Failed to start DOOM: " + err);
    console.error(err);
  });
})();
