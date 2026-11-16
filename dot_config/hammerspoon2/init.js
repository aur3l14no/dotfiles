"use strict";

if (!hs.permissions.checkNotifications()) {
  hs.permissions.requestNotifications();
}

// Watch init.js, tsconfig.json, and src/*.ts directly (ignore compiled/ output)
let reloadTimer = null;
const configWatcher = hs.fs
  .createPathWatcher(hs.appinfo.configDir)
  .setCallback((paths) => {
    const shouldReload = paths.some(
      (p) =>
        !p.includes("/compiled/") &&
        (p.endsWith(".ts") ||
          p.endsWith("/init.js") ||
          p.endsWith("/tsconfig.json")),
    );
    if (shouldReload) {
      if (reloadTimer) reloadTimer.stop();
      reloadTimer = hs.timer.doAfter(0.2, () => hs.reload());
    }
  })
  .start();

globalThis.__hs2Retained = { configWatcher };

function findTsc() {
  const user = (hs.appinfo.environment && hs.appinfo.environment.USER) || "y";
  const candidates = [
    `/etc/profiles/per-user/${user}/bin/tsc`,
    `${hs.fs.homeDirectory()}/.nix-profile/bin/tsc`,
    "/run/current-system/sw/bin/tsc",
    "/opt/homebrew/bin/tsc",
    "/usr/local/bin/tsc",
  ];
  return candidates.find((p) => hs.fs.exists(p)) || null;
}

(async () => {
  const tsc = findTsc();
  if (!tsc) {
    console.error("[HS2] tsc not found in standard paths");
    hs.ui.alert("Hammerspoon 2: tsc not found").duration(4).show();
    return;
  }

  try {
    await hs.task.runAsync(
      tsc,
      ["-p", `${hs.appinfo.configDir}/tsconfig.json`],
      {},
    );
  } catch (err) {
    const detail =
      (err && (err.stdout || err.stderr || err.message)) || String(err);
    console.error(`[HS2] TypeScript build failed:\n${detail}`);
    hs.ui
      .alert("Hammerspoon 2: TypeScript build failed (see Console)")
      .duration(4)
      .show();
    return;
  }

  hs.clearConsole();

  const config = require("./compiled/config.js");
  const util = require("./compiled/util.js");
  const app = require("./compiled/app.js");
  const caffeinate = require("./compiled/caffeinate.js");
  const win = require("./compiled/window.js");
  const screen = require("./compiled/screen.js");
  const autohide = require("./compiled/autohide.js");
  const kvm = require("./compiled/kvm.js");
  const sshNotify = require("./compiled/ssh-notify.js");

  util.registerUtilHotkeys();

  globalThis.__hs2Retained = {
    configWatcher,
    config,
    util,
    app,
    caffeinate,
    win,
    screen,
    autohide,
    kvm,
    sshNotify,
  };

  util.notify("There is no spoon!");
})();
