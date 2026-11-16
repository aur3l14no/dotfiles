// Software KVM: wake display when monitor-attached MSI USB hub (productID 16292) connects,
// and switch monitor input to HDMI 1 via lunar on Ctrl+Option+Shift+\.

export interface UsbDeviceEvent {
  productName: string;
  vendorName: string;
  productID: number;
  vendorID: number;
  serialNumber?: string;
  locationID?: number;
}

export function onUsbAdded(device: UsbDeviceEvent): void {
  if (device && device.productID === 16292) {
    console.info("[USBKVM] Detected MSI connection, waking up");
    hs.power.declareActivity();
  }
}

hs.usb.on("added", onUsbAdded);

export const kvmHotkey: HSHotkey | null = hs.hotkey.bind(
  ["ctrl", "option", "shift"],
  "\\",
  () => {
    console.info("[USBKVM] Switching to HDMI 1");
    void hs.task.shell(
      `${hs.fs.homeDirectory()}/.local/bin/lunar set input hdmi1`,
      {},
    );
  },
);
