// doom_run.js
// Receives level-complete events from the engine bridge and persists them as
// "Doom Run" documents through doom_manager.api.record_run, using the
// logged-in session (frappe.call handles CSRF). Guests can play but not save.

(function () {
  "use strict";

  function currentUser() {
    var el = document.getElementById("doom-page");
    return (el && el.dataset.user) || "Guest";
  }

  function hudAppend(text) {
    var hud = document.getElementById("hud");
    if (hud) hud.insertAdjacentHTML("beforeend", " — " + text);
  }

  function submitDoomRun(payload) {
    if (currentUser() === "Guest") {
      hudAppend(payload.level + " done (log in to save runs)");
      return;
    }
    frappe.call({
      method: "doom_manager.api.record_run",
      args: {
        level: payload.level,
        kills: payload.kills || 0,
        items: payload.items || 0,
        secrets: payload.secrets || 0,
        time_seconds: payload.time_seconds || 0,
      },
      callback: function (r) {
        if (r.message) {
          console.log("Doom Run saved:", r.message);
          hudAppend("saved as " + r.message);
        }
      },
      error: function (err) {
        console.error("Failed to save Doom Run", err);
        hudAppend("save failed (see console)");
      },
    });
  }

  window.DoomBridge = window.DoomBridge || {};

  window.DoomBridge.onLevelComplete = function (result) {
    submitDoomRun(result);
  };

  window.DoomBridge.onTick = function (state) {
    var killsEl = document.getElementById("kills");
    var timeEl = document.getElementById("time");
    var levelEl = document.getElementById("level");
    if (killsEl && state.kills != null) killsEl.textContent = state.kills;
    if (timeEl && state.time_seconds != null) timeEl.textContent = state.time_seconds;
    if (levelEl && state.level) levelEl.textContent = state.level;
  };
})();
