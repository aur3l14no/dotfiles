import { hyper } from "./config";

export function moveToRelScreen(
  win: HSWindow | null,
  rel: -1 | 1,
  showNotify: boolean,
): void {
  if (!win || !win.screen) return;

  const toScreen = rel === 1 ? win.screen.next() : win.screen.previous();
  if (!toScreen) return;

  if (win.isFullscreen) {
    win.toggleFullscreen();
    hs.timer.doAfter(1, () => {
      win.moveAndResize(toScreen.frame);
      win.toggleFullscreen();
    });
  } else {
    const currentFrame = win.frame;
    if (!currentFrame) return;
    const unitRect = currentFrame.toUnitRect(win.screen.frame);
    const targetFrame = unitRect.fromUnitRect(toScreen.frame);
    // Apply twice so cross-DPI screen moves preserve intended dimensions
    win.moveAndResize(targetFrame);
    win.moveAndResize(targetFrame);
  }

  if (showNotify) {
    const appName = win.application?.name || win.title || "Window";
    hs.ui.alert(`Move ${appName} to ${toScreen.name}`).duration(2).show();
  }
}

export const hotkeys: (HSHotkey | null)[] = [
  hs.hotkey.bind(hyper, ",", () => moveToRelScreen(hs.window.focusedWindow(), -1, true)),
  hs.hotkey.bind(hyper, ".", () => moveToRelScreen(hs.window.focusedWindow(), 1, true)),
];
