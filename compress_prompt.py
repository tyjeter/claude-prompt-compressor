#!/usr/bin/env python3
"""
Prompt compression hook for Claude Code.
Strips filler phrases and shortens verbose patterns to reduce token usage.
"""
import sys
import json
import re

# ---------------------------------------------------------------------------
# Patterns — compiled once at import time for speed
# ---------------------------------------------------------------------------

_FILLER_PHRASES = [
    r"\bplease\b,?\s*",
    r"\bkindly\b,?\s*",
    r"\bjust\b\s+",
    r"can you\s+",
    r"could you\s+",
    r"would you\s+",
    r"will you\s+",
    r"i was wondering if (you could\s+)?",
    r"i was hoping (you could\s+)?",
    r"is it possible (for you )?(to\s+)?",
    r"i want you to\s+",
    r"i need you to\s+",
    r"i'd like you to\s+",
    r"i would like you to\s+",
    r"i'd like\s+",
    r"i would like\s+",
    r"quick question:?\s*",
    r"just (a )?quick(ly)?\s+",
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
    r"cheers[.!]?\s*",
    r"at (your )?earliest convenience\s*",
    r"as soon as (you can|possible)\s*",
]

_COMPRESSIONS = [
    # Function/code writing
    (r"(write|create|implement|make) (a |an )?function that\s+", "fn that "),
    (r"(write|create|implement|make) (a |an )?function (to|which)\s+", "fn to "),
    (r"(write|create|implement|make) (a |an )?(script|program|code) (that|to|which)\s+", "code to "),
    # Examples
    (r"(give|show|provide|write) me (an? )?example(s)? of\s+", "example: "),
    (r"(give|show|provide) (an? )?example(s)? of\s+", "example: "),
    # Explanations
    (r"explain (in detail |in simple terms |simply )?how (to\s+|I (can|should)\s+)", "how to "),
    (r"explain (in detail |in simple terms |simply )?what\s+", "what is "),
    (r"help me (to\s+)?understand\s+", "explain "),
    (r"help me (to\s+)?", "help "),
    # Best/efficient way
    (r"what('?s| is) the best way to\s+", "best way to "),
    (r"what('?s| is) the (most )?efficient way to\s+", "efficient way to "),
    (r"what('?s| is) the (most )?optimal way to\s+", "optimal way to "),
    (r"what('?s| is) the (most )?common way to\s+", "common way to "),
    # How do/can I
    (r"how (do|can) (i|you|we)\s+", "how to "),
    (r"how (should|would) (i|you|we)\s+", "how to "),
    # Differences
    (r"what (are|is) (the )?difference(s)? between\s+", "diff: "),
    (r"what('?s| is) (the )?difference between\s+", "diff: "),
    # Debugging
    (r"(why is|why does|why isn't|why doesn't|why won't)\s+", "why "),
    (r"(what is|what's) (causing|wrong with|the issue with)( the issue with)?\s+", "issue: "),
    # Contractions — expand verbose forms
    (r"\bi am\b", "I'm"),
    (r"\byou are\b", "you're"),
    (r"\bthey are\b", "they're"),
    (r"\bwe are\b", "we're"),
    (r"\bdo not\b", "don't"),
    (r"\bdoes not\b", "doesn't"),
    (r"\bdid not\b", "didn't"),
    (r"\bcannot\b", "can't"),
    (r"\bwill not\b", "won't"),
    (r"\bshould not\b", "shouldn't"),
    (r"\bwould not\b", "wouldn't"),
    (r"\bcould not\b", "couldn't"),
    (r"\bhave not\b", "haven't"),
    (r"\bhas not\b", "hasn't"),
    (r"\bit is\b", "it's"),
    (r"\bthat is\b", "that's"),
    (r"\bthere is\b", "there's"),
    (r"\bthere are\b", "there're"),
]

# Redundant/padded word pairs: verbose → concise
_REDUNDANCIES = [
    (r"\bcompletely (finish|done|complete|eliminate|remove|destroy)\b", r"\1"),
    (r"\babsolutely (necessary|essential|certain|sure)\b", r"\1"),
    (r"\bvery unique\b", "unique"),
    (r"\bvery (important|critical|crucial)\b", r"\1"),
    (r"\bend result\b", "result"),
    (r"\bfinal (result|outcome|conclusion)\b", r"\1"),
    (r"\bbasic (fundamentals|basics|principles)\b", r"\1"),
    (r"\bfuture (plans|planning)\b", r"\1"),
    (r"\bpast (history|experience)\b", r"\1"),
    (r"\bunnecessary (filler|padding|fluff)\b", r"\1"),
    (r"\badvance (planning|warning|notice)\b", r"\1"),
    (r"\bclose (proximity|together)\b", "close"),
    (r"\bexact (same|opposite)\b", r"\1"),
    (r"\bsomewhat (rather|fairly)\b", "somewhat"),
    (r"\bperiod of time\b", "period"),
    (r"\bpoint in time\b", "point"),
    (r"\bin the (event|case) (that|of)\b", "if"),
    (r"\bdue to the fact that\b", "because"),
    (r"\bin spite of the fact that\b", "although"),
    (r"\bat this point in time\b", "now"),
    (r"\bfor the purpose of\b", "for"),
    (r"\bwith (the )?regard(s)? to\b", "regarding"),
    (r"\bin (the )?addition to\b", "also"),
]

# Pre-compile everything
_FILLER_RE = [(re.compile(p, re.IGNORECASE), "") for p in _FILLER_PHRASES]
_COMPRESS_RE = [(re.compile(p, re.IGNORECASE), r) for p, r in _COMPRESSIONS]
_REDUNDANCY_RE = [(re.compile(p, re.IGNORECASE), r) for p, r in _REDUNDANCIES]
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\s*\n\s*\n\s*\n+")

# Matches fenced code blocks: ```...```
_CODE_BLOCK_RE = re.compile(r"(```[\s\S]*?```)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Core compression — applied to plain-text segments only
# ---------------------------------------------------------------------------

def _compress_segment(text):
    for pattern, repl in _FILLER_RE:
        text = pattern.sub(repl, text)
    for pattern, repl in _COMPRESS_RE:
        text = pattern.sub(repl, text)
    for pattern, repl in _REDUNDANCY_RE:
        text = pattern.sub(repl, text)
    return text


def compress(text):
    # Skip trivially short prompts
    if len(text) < 20:
        return text

    original_len = len(text)

    # Split on code blocks so we only compress prose, not code
    parts = _CODE_BLOCK_RE.split(text)
    compressed_parts = []
    for part in parts:
        if part.startswith("```"):
            compressed_parts.append(part)  # leave code blocks untouched
        else:
            compressed_parts.append(_compress_segment(part))

    result = "".join(compressed_parts)

    # Clean up whitespace
    result = _WHITESPACE_RE.sub(" ", result).strip()
    result = _BLANK_LINES_RE.sub("\n\n", result)

    # Restore capitalisation if first letter was lowered
    if result and text[0].isupper() and result[0].islower():
        result = result[0].upper() + result[1:]

    # Only return compressed version if it's actually shorter
    if len(result) >= original_len:
        return text

    return result


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

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
