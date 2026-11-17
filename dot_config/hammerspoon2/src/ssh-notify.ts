// Stream macOS unified log events from /usr/libexec/sshd-session and show a
// top-right banner whenever an inbound SSH session is accepted.

const KNOWN_KEYS: Readonly<Record<string, string>> = {
  "SHA256:y93Hj+oRsOmtT1W0gR5wq0QTkv8abEuKwiRYaKRZgcU": "groves",
  "SHA256:2ImB/ba3YNEmjGcbYPW8ewKeHQIfbwrNZvBhC4ZuemM": "john-macbook",
  "SHA256:1dwseCJx7sZkhjmeQ0G6+9B0MsIcYYlQIolvl40iPF4": "fusco-thinkbook",
  "SHA256:81IPlqdJAvFnn+NAzbU8tttkJwYf3PXVJ8/VdTdqqdU": "murph-troy",
  "SHA256:eAmi0asTIvjYqcTZ9Y/1B98uQ6bV0q7B87HXXQixb8Q": "admin-backup",
  "SHA256:gw31aSENiGYs0nCSIbMPn5sb5yRjdFJn/SwUl5DB+x0": "Termius",
  "SHA256:fYtM9UiRvv447m+J8ub6iKrb8IStYl7wVyuaHHIIaqY": "codex-ios",
};

const DEBOUNCE_SECONDS = 30;
const WITHDRAW_SECONDS = 15;
const PREDICATE = [
  'process == "sshd-session"',
  'senderImagePath == "/usr/libexec/sshd-session"',
  'eventMessage BEGINSWITH "Accepted "',
].join(" AND ");

export interface SshNotifyState {
  stopping: boolean;
  task: HSTask | null;
  retryTimer: HSTimer | null;
  buf: string;
  lastSeen: Map<string, number>;
}

const g = globalThis as typeof globalThis & {
  __sshNotify?: SshNotifyState;
};

if (g.__sshNotify) {
  g.__sshNotify.stopping = true;
  if (g.__sshNotify.retryTimer) {
    g.__sshNotify.retryTimer.stop();
    g.__sshNotify.retryTimer = null;
  }
  if (g.__sshNotify.task && g.__sshNotify.task.isRunning) {
    g.__sshNotify.task.terminate();
  }
}

export const state: SshNotifyState = {
  stopping: false,
  task: null,
  retryTimer: null,
  buf: "",
  lastSeen: new Map<string, number>(),
};
g.__sshNotify = state;

const ACCEPTED_RE = /Accepted (\S+) for (\S+) from (\S+) port (\d+)(.*)/;
const FINGERPRINT_RE = /(SHA256:\S+)/;

export function handleLine(line: string): void {
  const match = ACCEPTED_RE.exec(line);
  if (!match) return;

  const [, method, user, peerIp, port, rest] = match;
  const fp = rest ? (FINGERPRINT_RE.exec(rest)?.[1] ?? null) : null;
  const keyName = fp ? (KNOWN_KEYS[fp] ?? null) : null;
  const dedupKey = `${peerIp}|${fp ?? method}`;
  const now = Math.floor(Date.now() / 1000);

  const prev = state.lastSeen.get(dedupKey);
  if (prev !== undefined && now - prev < DEBOUNCE_SECONDS) {
    return;
  }
  state.lastSeen.set(dedupKey, now);

  const title = keyName ? "SSH Login" : "SSH Login (Unknown Key)";
  const subtitle = `${user}@${hs.appinfo.machineName} ← ${peerIp}:${port}`;
  const body = keyName
    ? `Key: ${keyName} (${method})`
    : `UNKNOWN KEY: ${fp ?? "none"} (${method})`;

  const notification = hs.notify.create({
    title,
    subtitle,
    body,
  });
  if (!notification) return;
  notification.send();
  hs.timer.doAfter(WITHDRAW_SECONDS, () => {
    notification.withdraw();
  });
}

export function startWatcher(): void {
  if (state.stopping) return;

  state.buf = "";
  state.task = hs.task.create(
    "/usr/bin/log",
    ["stream", "--info", "--style", "compact", "--predicate", PREDICATE],
    () => {
      state.task = null;
      if (!state.stopping) {
        state.retryTimer = hs.timer.doAfter(5, startWatcher);
      }
    },
    null,
    (stream, chunk) => {
      if (stream !== "stdout" || !chunk) return;
      state.buf += chunk;
      while (true) {
        const nl = state.buf.indexOf("\n");
        if (nl === -1) break;
        const line = state.buf.slice(0, nl);
        state.buf = state.buf.slice(nl + 1);
        handleLine(line);
      }
    },
  );
  state.task.start();
}

startWatcher();
