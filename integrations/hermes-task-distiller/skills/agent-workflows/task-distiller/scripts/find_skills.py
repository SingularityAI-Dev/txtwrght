#!/usr/bin/env python3
"""
find_skills.py -- check the wider skill ecosystem before building something from scratch.

Tries, in order:
  1. `hermes skills search <query>` -- the native Hermes Skills Hub. If your installed
     Hermes version exposes a different subcommand name, run `hermes skills --help` once
     and adjust HERMES_SEARCH_CMD below; Hub subcommands have moved around across releases.
  2. `npx skills find <query>` -- the skills.sh CLI (https://skills.sh), guaranteed to
     exist since it's that project's own documented interface. Anything found there can be
     installed straight into Hermes via `hermes skills install <owner/repo>` (Hermes can
     consume GitHub identifiers, skills.sh identifiers, and well-known
     /.well-known/skills/index.json endpoints natively).

Usage:
    python3 find_skills.py "sync github issues notion"
"""
import shutil
import subprocess
import sys

HERMES_SEARCH_CMD = ["hermes", "skills", "search"]  # verify against your Hermes version
SKILLS_SH_CMD = ["npx", "skills", "find"]


def run(cmd: list[str]) -> bool:
    print(f"$ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.stdout:
            print(result.stdout)
        if result.returncode != 0 and result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode == 0 and bool(result.stdout.strip())
    except FileNotFoundError:
        print(f"  ({cmd[0]} not found on PATH)")
        return False
    except subprocess.TimeoutExpired:
        print("  (timed out)")
        return False


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: find_skills.py <query terms>")
    query = " ".join(sys.argv[1:])

    found = False
    if shutil.which("hermes"):
        found = run(HERMES_SEARCH_CMD + [query])
    if not found:
        print("\nFalling back to skills.sh via npx...\n")
        found = run(SKILLS_SH_CMD + [query])

    print(
        "\nBefore building something new, sanity-check any hits: prefer 1K+ installs, a "
        "reputable source (vercel-labs, anthropics, microsoft, openai, huggingface, or "
        "another org you recognize), and a well-starred repo. See https://skills.sh for "
        "the leaderboard, and references/finding-existing-skills.md for the full checklist."
    )
    if not found:
        print(
            "\nNo hits from either source. If this is something you'll do often, this is "
            "exactly what task-distiller's record -> script -> scaffold -> register flow "
            "is for -- proceed with that."
        )


if __name__ == "__main__":
    main()
