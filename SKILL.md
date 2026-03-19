---
name: "codex-mobile-notify"
description: "Use when the user explicitly wants Codex to send a mobile push when a task finishes or when Codex needs the user's input or approval. Also trigger when the user message contains @@. This skill is per-task opt-in and sends one Bark notification at the terminal state of the current turn."
---

# Codex Mobile Notify

Use this skill only when the user clearly asks to be notified when the task is done, asks for a mobile notification, wants a push on completion, or explicitly includes the token `@@` in their message. This skill is per-task opt-in. It is not a global Codex completion hook.

## Trigger shortcuts

Either of these should trigger the skill:

- An English phrase such as "notify me when you're done", "notify me when complete", "send me a mobile notification", or "let me know when you need me".
- A compatible Chinese phrase such as "完成后通知我" or "用 Bark 通知我".
- The exact token `@@` appearing in the user message.

Only treat the exact `@@` token as a trigger. Do not use fuzzy matching.

## Prerequisite check (required)

Before promising a push, verify that Python is available and `BARK_DEVICE_KEY` is set:

```bash
python3 --version
test -n "$BARK_DEVICE_KEY"
```

If `BARK_DEVICE_KEY` is missing, stop and tell the user to configure Bark first:

```bash
export BARK_DEVICE_KEY="your-device-key"
# Optional:
export BARK_BASE_URL="https://api.day.app"
export BARK_GROUP="Codex"
export BARK_SOUND="minuet"
export BARK_ICON="https://example.com/icon.png"
export BARK_URL="codex://"
```

## When to notify

Send exactly one Bark push for the current turn:

- `complete`: the task is done and your final response is ready.
- `action-needed`: you cannot continue without the user.

Use `action-needed` for:

- waiting for a user answer
- waiting for command approval
- waiting for file approval
- waiting for the user to grant a macOS or app permission
- waiting for login, 2FA, captcha, or browser-based auth
- waiting for the user to click a picker, confirmation dialog, or GUI control
- waiting for a secret, token, credential, or account choice that only the user can provide
- a blocker that needs the user's decision

Do not send both for the same turn. If you already sent `action-needed`, do not send `complete` later in that turn.

## Blocked-state heuristics

Treat the turn as `action-needed` before you message the user whenever any of these is true:

- a tool call has already produced an approval request
- you are about to ask the user a clarifying question that blocks progress
- a command or app flow depends on the user accepting a system permission dialog
- a browser or desktop app flow has reached a login, 2FA, captcha, SSO, or manual consent screen
- a command launched a GUI flow and progress now depends on a manual click or selection
- a required credential is missing and you cannot safely continue without it
- output or behavior strongly suggests the task is stalled waiting for manual interaction rather than more compute time

When a browser, desktop app, or permission flow appears stalled, do not wait silently. Prefer classifying it as `action-needed` and notify the user.

## Message format

Keep pushes short and plain:

- `complete` title: `Codex Completed`
- `action-needed` title: `Codex Needs You`
- Body: `<task title>: <one-sentence summary>`

If you do not have a good task title, use `Current task`.

Do not include:

- secrets
- full diffs
- long code blocks
- stack traces
- multi-paragraph prose

## Skill path

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export BARK_NOTIFY_PY="$CODEX_HOME/skills/codex-mobile-notify/scripts/send_bark.py"
```

## Once key

At the start of the turn, choose one short task-scoped once key and reuse it for every Bark call in that turn. Prefer a stable identifier already visible in context, such as:

- conversation id
- request id
- approval id
- task id

If no stable id is visible, create a short task-local key and reuse the exact same string for the rest of the turn. The script uses this key to suppress duplicate Bark pushes for the same terminal state.

## Commands

Completion:

```bash
python3 "$BARK_NOTIFY_PY" --once-key "task-123" --event complete --title "Codex Completed" --body "Current task: Finished and ready for review."
```

Blocked / needs user action:

```bash
python3 "$BARK_NOTIFY_PY" --once-key "task-123" --event action-needed --title "Codex Needs You" --body "Current task: Waiting for your approval before I can continue."
```

Permission / manual interaction blocker:

```bash
python3 "$BARK_NOTIFY_PY" --once-key "task-123" --event action-needed --title "Codex Needs You" --body "Current task: Waiting for you to grant a system permission."
```

## Workflow

1. Verify Bark configuration before starting substantial work.
2. Pick one once key for the turn and reuse it.
3. Do the task normally.
4. Immediately before the final assistant message or blocker message, send one Bark push.
5. If the Bark script fails, still deliver the actual Codex response and explicitly say the push failed.
6. Only claim that a push was sent when the script exited successfully.

## Guardrails

- Never send pushes for intermediate progress updates.
- Prefer `action-needed` over `complete` whenever the user must act before work can continue.
- Use `action-needed` for permission dialogs, login prompts, and GUI interactions that block progress.
- Reuse the same once key across the turn so duplicate blocker pushes are suppressed.
- Keep the body to a single sentence.
- This skill does not provide global automatic notifications for every Codex task. Use it only for the current task.
