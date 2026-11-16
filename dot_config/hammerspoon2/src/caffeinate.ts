import { hyper } from "./config";
import { notify } from "./util";

export const caffeinateTrayIcon: HSMenuBarItem = hs.menubar.create();

function setCaffeinateIcon(state: boolean): void {
  const file = state ? "caffeinate-on.pdf" : "caffeinate-off.pdf";
  const icon = HSImage.fromPath(`${hs.appinfo.configDir}/assets/${file}`);
  if (icon) {
    icon.template = true;
    caffeinateTrayIcon.setIcon(icon);
  }
}

export function toggleCaffeinate(): void {
  const currentlyPrevented = hs.power.isSleepPrevented("display");
  if (currentlyPrevented) {
    hs.power.allowSleep("display");
    notify("System will sleep when idle");
    setCaffeinateIcon(false);
  } else {
    hs.power.preventSleep("display");
    notify("System never sleep");
    setCaffeinateIcon(true);
  }
}

export const caffeinateHotkey: HSHotkey | null = hs.hotkey.bind(
  hyper,
  "=",
  toggleCaffeinate,
);

caffeinateTrayIcon.setClickCallback(() => {
  toggleCaffeinate();
});
setCaffeinateIcon(hs.power.isSleepPrevented("display"));
