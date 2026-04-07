# claude-prompt-compressor

A Claude Code hook that automatically compresses verbose prompts before they reach the AI, reducing token usage.

## What it does

Strips filler phrases and shortens common verbose patterns:

- `"could you please write a function that sorts a list"` → `"fn that sorts a list"` (38% smaller)
- `"can you give me an example of async await in javascript"` → `"example: async await in javascript"` (45% smaller)
- Short/precise prompts pass through unchanged

## Install

1. Copy `compress_prompt.py` to `~/.claude/`:

```sh
cp compress_prompt.py ~/.claude/compress_prompt.py
```

2. Add the hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/compress_prompt.py",
            "timeout": 5,
            "statusMessage": "Compressing prompt..."
          }
        ]
      }
    ]
  }
}
```

## How it works

The hook intercepts every prompt via the `UserPromptSubmit` event. If compression saves characters, the compressed version is injected as additional context for the model to use.

Prompts containing code blocks or over 2000 characters are skipped automatically.

## Requirements

- Python 3 (no external packages)
- Claude Code with hooks support
