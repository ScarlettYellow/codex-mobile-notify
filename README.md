# Codex Mobile Notify

Codex Mobile Notify is an open-source Codex skill that sends a mobile push notification when a task finishes or when Codex needs your input, approval, or manual action.

It is designed for long-running Codex tasks where you do not want to keep watching the app while work is in progress.

<p align="center">
  <img src="assets/bark-notifications.png" alt="Bark notification screenshot" width="320" />
</p>

## What it does

- Sends a Bark push when Codex reaches a terminal state for the current turn
- Supports both `complete` and `action-needed` notifications
- Uses a per-turn once key to suppress duplicate pushes
- Stays lightweight and dependency-free by using Python's standard library

## What it does not do

- It is not a global Codex event hook
- It does not monitor every Codex task automatically
- It does not directly listen to macOS system dialogs or OS-level permission windows
- It only applies when the current task explicitly triggers the skill

## Trigger modes

This skill should trigger when the user message includes any of the following:

- An English intent phrase such as `notify me when you're done`, `notify me when complete`, `send me a mobile notification`, or `let me know when you need me`
- A compatible Chinese phrase such as `完成后通知我` or `用 Bark 通知我`
- The exact token `@@`

`@@` must be matched exactly. Do not use fuzzy matching.

## Requirements

- Codex with local skills support
- Python 3
- An iPhone with the [Bark app](https://apps.apple.com/us/app/bark-custom-notifications/id1403753865)
- A valid `BARK_DEVICE_KEY`

## Installation

1. Clone or copy this repository somewhere on your machine.
2. Copy the repository contents into your Codex skills directory:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills/codex-mobile-notify/agents"
mkdir -p "$CODEX_HOME/skills/codex-mobile-notify/scripts"
cp SKILL.md "$CODEX_HOME/skills/codex-mobile-notify/"
cp agents/openai.yaml "$CODEX_HOME/skills/codex-mobile-notify/agents/"
cp scripts/send_bark.py "$CODEX_HOME/skills/codex-mobile-notify/scripts/"
```

3. Restart Codex or refresh the skills list so the new skill appears.

## Configuration

Set the required Bark key:

```bash
export BARK_DEVICE_KEY="your-device-key"
```

Optional environment variables:

```bash
export BARK_BASE_URL="https://api.day.app"
export BARK_GROUP="Codex"
export BARK_SOUND="minuet"
export BARK_ICON="https://example.com/icon.png"
export BARK_URL="codex://"
export BARK_STATE_DIR="$HOME/.codex/state/codex-mobile-notify"
```

## Manual script usage

Completion:

```bash
python3 scripts/send_bark.py --event complete --title "Codex Completed" --body "Current task: Finished and ready for review."
```

Action needed:

```bash
python3 scripts/send_bark.py --event action-needed --title "Codex Needs You" --body "Current task: Waiting for your approval before I can continue."
```

Optional dedupe key:

```bash
python3 scripts/send_bark.py --once-key "task-123" --event complete --title "Codex Completed" --body "Current task: Finished and ready for review."
```

## Example prompts

English trigger:

```text
Review this bug and notify me when you're done.
```

English prompt with explicit skill reference:

```text
Use $codex-mobile-notify for this task. Fix the failing test, then notify me when you're done.
```

Chinese compatibility trigger:

```text
修复这个问题，完成后通知我。
```

Exact token trigger:

```text
Please investigate this issue and @@
```

## Action-needed behavior

The skill should send `action-needed` before replying whenever Codex is blocked on something only the user can do, such as:

- answering a blocking question
- approving a command or file change
- granting a permission
- completing login, 2FA, captcha, or browser auth
- clicking a picker, dialog, or GUI control
- providing a secret or account choice

## Limitations

- This is a per-task opt-in skill
- It does not provide universal mobile notifications for every Codex task
- It depends on Bark for delivery to the phone
- It can classify likely blocked states, but it is still not an OS-level watcher

## Troubleshooting

If pushes are not arriving:

1. Verify that `BARK_DEVICE_KEY` is set
2. Confirm the Bark app is installed and notifications are allowed
3. Run the script manually to confirm end-to-end delivery
4. Check whether the notification was intentionally suppressed by the once key or dedupe window

## License

MIT
