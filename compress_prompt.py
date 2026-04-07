#!/usr/bin/env python3
"""
Prompt compression hook for Claude Code.
Strips filler phrases and shortens verbose patterns to reduce token usage.
"""
import sys
import json
import re


FILLER_PHRASES = [
    r"\bplease\b,?\s*",
    r"\bkindly\b,?\s*",
    r"can you\s+",
    r"could you\s+",
    r"would you\s+",
    r"will you\s+",
    r"i want you to\s+",
    r"i need you to\s+",
    r"i'd like you to\s+",
    r"i would like you to\s+",
    r"i'd like\s+",
    r"i would like\s+",
    r"make sure (to\s+)?",
    r"be sure (to\s+)?",
    r"don't forget (to\s+)?",
    r"remember to\s+",
    r"feel free to\s+",
    r"go ahead and\s+",
    r"try to\s+",
    r"attempt to\s+",
    r"in order to\s+",
    r"as (much as )?possible",
    r"if (that'?s? )?possible",
    r"if you can",
    r"if you could",
    r"thank you[.!]?\s*",
    r"thanks[.!]?\s*",
]

COMPRESSIONS = [
    (r"write (a |an )?function that\s+", "fn that "),
    (r"write (a |an )?function (to|which)\s+", "fn to "),
    (r"write (a |an )?(script|program|code) (that|to|which)\s+", "code to "),
    (r"create (a |an )?function that\s+", "fn that "),
    (r"create (a |an )?function (to|which)\s+", "fn to "),
    (r"implement (a |an )?function that\s+", "fn that "),
    (r"implement (a |an )?function (to|which)\s+", "fn to "),
    (r"give me (an? )?example(s)? of\s+", "example: "),
    (r"show me (an? )?example(s)? of\s+", "example: "),
    (r"provide (an? )?example(s)? of\s+", "example: "),
    (r"explain (in detail )?how (to\s+|I (can|should)\s+)", "how to "),
    (r"explain what\s+", "what is "),
    (r"what is the best way to\s+", "best way to "),
    (r"what('?s| is) the (most )?efficient way to\s+", "efficient way to "),
    (r"how (do|can) (i|you|we)\s+", "how to "),
    (r"what (are|is) (the )?difference(s)? between\s+", "diff: "),
    (r"help me (to\s+)?understand\s+", "explain "),
    (r"help me (to\s+)?", "help "),
    (r"\bi am\b", "I'm"),
    (r"\byou are\b", "you're"),
    (r"\bdo not\b", "don't"),
    (r"\bdoes not\b", "doesn't"),
    (r"\bcannot\b", "can't"),
    (r"\bwill not\b", "won't"),
    (r"\bshould not\b", "shouldn't"),
    (r"\bwould not\b", "wouldn't"),
    (r"\bit is\b", "it's"),
    (r"\bthat is\b", "that's"),
]


def compress(text):
    original_len = len(text)

    # Only compress single-line prompts or short prompts (skip code blocks etc.)
    if "```" in text or len(text) > 2000:
        return text

    result = text

    # Apply filler phrase removal (case-insensitive)
    for pattern in FILLER_PHRASES:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)

    # Apply compressions (case-insensitive)
    for pattern, replacement in COMPRESSIONS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Clean up whitespace
    result = re.sub(r"[ \t]+", " ", result).strip()
    result = re.sub(r"\s*\n\s*\n\s*\n+", "\n\n", result)

    # Capitalize first letter if we lowercased it
    if result and text[0].isupper() and result[0].islower():
        result = result[0].upper() + result[1:]

    # Only use compressed version if it's actually shorter
    if len(result) >= original_len:
        return text

    return result


def main():
    input_data = json.load(sys.stdin)
    prompt = input_data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    compressed = compress(prompt)

    if compressed == prompt:
        sys.exit(0)

    saved = len(prompt) - len(compressed)
    pct = int(saved / len(prompt) * 100)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": f"[Prompt compressed {pct}% ({saved} chars saved)]\nCompressed prompt: {compressed}",
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
