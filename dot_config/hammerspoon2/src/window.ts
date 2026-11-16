import { hyper } from "./config";

export type LayoutName =
  | "fullscreen"
  | "left"
  | "right"
  | "center"
  | "center-large"
  | "left-top"
  | "left-bottom"
  | "right-top"
  | "right-bottom"
  | "corner";

type BaseLayout = "fullscreen" | "left" | "right" | "center" | "corner";
type CyclingLayout = "left" | "right" | "center";

export const presetLayout: Record<LayoutName, HSRect> = {
  fullscreen: new HSRect(0, 0, 1, 1),
  left: new HSRect(0, 0, 0.55, 1),
  right: new HSRect(0.55, 0, 0.45, 1),
  center: new HSRect(0.25, 0.15, 0.5, 0.7),
  "center-large": new HSRect(0.15, 0.1, 0.7, 0.8),
  "left-top": new HSRect(0, 0, 0.55, 0.55),
  "left-bottom": new HSRect(0, 0.45, 0.55, 0.55),
  "right-top": new HSRect(0.55, 0, 0.45, 0.55),
  "right-bottom": new HSRect(0.55, 0.45, 0.45, 0.55),
  corner: new HSRect(0.95, 0.95, 0.05, 0.05),
};

const moveWindowState: Record<CyclingLayout, readonly LayoutName[]> = {
  left: ["left", "left-top", "left-bottom"],
  right: ["right", "right-top", "right-bottom"],
  center: ["center", "center-large"],
};

function isCyclingLayout(layout: BaseLayout): layout is CyclingLayout {
  return layout === "left" || layout === "right" || layout === "center";
}

let lastMovedWinId: number | null = null;
let lastLayout: BaseLayout | null = null;
let moveWindowCounter = 0;

export function moveWindow(win: HSWindow | null, layout: BaseLayout): void {
  if (!win || !win.screen) return;

  let targetKey: LayoutName = layout;
  if (
    win.id === lastMovedWinId &&
    layout === lastLayout &&
    isCyclingLayout(layout)
  ) {
    const variants = moveWindowState[layout];
    moveWindowCounter = (moveWindowCounter + 1) % variants.length;
    targetKey = variants[moveWindowCounter];
  } else {
    lastMovedWinId = win.id;
    lastLayout = layout;
    moveWindowCounter = 0;
  }

  win.moveAndResize(presetLayout[targetKey].fromUnitRect(win.screen.frame));
}

export const hotkeys: (HSHotkey | null)[] = [
  hs.hotkey.bind(hyper, "space", () => moveWindow(hs.window.focusedWindow(), "center")),
  hs.hotkey.bind(hyper, "h", () => moveWindow(hs.window.focusedWindow(), "left")),
  hs.hotkey.bind(hyper, "l", () => moveWindow(hs.window.focusedWindow(), "right")),
  hs.hotkey.bind(hyper, "/", () => moveWindow(hs.window.focusedWindow(), "corner")),
  hs.hotkey.bind(hyper, "return", () => moveWindow(hs.window.focusedWindow(), "fullscreen")),
];
