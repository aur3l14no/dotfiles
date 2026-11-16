// Automatically hide inactive background apps (without hs.spaces filtering).

const whiteList = new Set<string>([
  "Google Chrome",
  "Hammerspoon",
  "Hammerspoon 2",
  "TencentMeeting",
  "Preview",
]);

// When non-empty, only apps in blackList are auto-hidden
const blackList = new Set<string>([
  // temporary fun
  "Spotify",
  "Telegram",
  "Element",
  // temporary tool
  "Paperlib",
  "Bitwarden",
  "Chatbox",
  "Surge",
  "Surge Dashboard",
  // temporary work
  "Mail",
  "System Settings",
]);

const minAppsToKeep = 4;
const minTimeToKeep = 30;
const doEverySeconds = 10;

// appName -> epoch seconds
const lastActive = new Map<string, number>();

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

export function recordActive(app: HSApplication | null): void {
  if (!app || !app.name) return;
  lastActive.set(app.name, nowSeconds());
}

export function clearActive(app: HSApplication | null): void {
  if (!app || !app.name) return;
  lastActive.delete(app.name);
}

function doHide(): void {
  const now = nowSeconds();
  const sorted = [...lastActive.entries()].sort((a, b) => b[1] - a[1]);

  sorted.forEach(([name, activeAt], index) => {
    if (index < minAppsToKeep) return;
    if (whiteList.has(name)) return;

    if (
      now - activeAt >= minTimeToKeep &&
      (blackList.size === 0 || blackList.has(name))
    ) {
      const app = hs.application.matchingName(name);
      if (app && app.mainWindow) {
        console.info(`[AUTOHIDE] Auto hiding ${app.name}`);
        app.hide();
      }
      lastActive.delete(name);
    }
  });
}

hs.application.on("didActivate", recordActive);
hs.application.on("didDeactivate", recordActive);
hs.application.on("didHide", clearActive);
hs.application.on("didTerminate", clearActive);

export const autohideTimer: HSTimer = hs.timer.doEvery(doEverySeconds, doHide);
