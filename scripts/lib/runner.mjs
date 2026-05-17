// scripts/lib/runner.mjs
export function runnerFile(os, { label, cmd }) {
  if (os === 'mac') {
    return {
      filename: `${label}.plist`,
      content: `<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string><string>${cmd}</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>\n`,
      install_hint: `cp ${label}.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/${label}.plist`,
    };
  }
  if (os === 'linux' || os === 'wsl') {
    return {
      filename: `${label}.service`,
      content: `[Unit]\nDescription=${label}\n[Service]\nExecStart=${cmd}\nRestart=always\n[Install]\nWantedBy=default.target\n`,
      install_hint: `mkdir -p ~/.config/systemd/user && cp ${label}.service ~/.config/systemd/user/ && systemctl --user enable --now ${label}`,
    };
  }
  return {
    filename: `${label}.runner.txt`,
    content: `# Windows native: WSL 권장. WSL 안에서 systemd user unit 사용, 또는 tmux:\ntmux new -d -s ${label} '${cmd}'\n`,
    install_hint: 'WSL 권장 — 위 파일 참고하여 수동 실행.',
  };
}
