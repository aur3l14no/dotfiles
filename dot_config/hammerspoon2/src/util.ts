export function notify(msg: string): void {
  const n = hs.notify.create({
    title: "Hammerspoon",
    body: msg,
  });
  if (!n) return;
  n.send();
  hs.timer.doAfter(3, () => {
    n.withdraw();
  });
}

export const hotkeys: (HSHotkey | null)[] = [];

export function registerUtilHotkeys(): (HSHotkey | null)[] {
  // Paste clipboard as keystrokes
  hotkeys.push(
    hs.hotkey.bind(["cmd", "alt", "ctrl", "shift"], "v", () => {
      const contents = hs.pasteboard.readString();
      if (!contents) return;
      [...contents].forEach((ch, idx) => {
        hs.timer.doAfter(idx * 0.1, () => {
          hs.eventtap.keyStrokes(ch);
        });
      });
    }),
  );

  // Print frontmost window info
  hotkeys.push(
    hs.hotkey.bind(["cmd", "alt", "ctrl"], "w", () => {
      const win = hs.window.focusedWindow();
      if (!win) return;
      console.log(win);
      console.log(win.application);
      console.log(win.application?.bundleID);
    }),
  );

  return hotkeys;
}
