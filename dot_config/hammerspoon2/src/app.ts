import { hyper, key2App } from "./config";

export function toggleApplication(bundleID: string): void {
  const app = hs.application.matchingBundleID(bundleID);
  if (app && app.isActive) {
    app.hide();
  } else {
    void hs.application.launchOrFocus(bundleID);
  }
}

export const hotkeys: (HSHotkey | null)[] = key2App.map(([key, bundleID]) =>
  hs.hotkey.bind(hyper, key, () => {
    toggleApplication(bundleID);
  }),
);
