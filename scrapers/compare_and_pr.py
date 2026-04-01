#!/usr/bin/env python3
"""
compare_and_pr.py
=================
Compares freshly scraped CSVs against the current versions on GitHub.
For each file that has changed (ignoring the timestamp on line 1),
creates a new branch and opens a Pull Request with a clear diff summary.

Requirements:
    pip install requests

Environment variables required:
    GITHUB_TOKEN   — Personal Access Token with repo scope
                     (set in GitHub Actions secrets, or locally in your shell)

Usage:
    python compare_and_pr.py

Run this from the same folder as the scraped CSVs.
"""

import os
import sys
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

REPO_OWNER  = "itsJustinCase"
REPO_NAME   = "gamble-eagle"
BASE_BRANCH = "main"

# CSVs to check: local filename → path in the GitHub repo
CSV_FILES = {
    "france.csv":           "france.csv",
    "france_blacklist.csv": "france_blacklist.csv",
    "spain.csv":       "spain.csv",
    "denmark.csv":     "denmark.csv",
    "sweden.csv":      "sweden.csv",
    "netherlands.csv": "netherlands.csv",
    "ontario.csv":     "ontario.csv",
    "brazil.csv":      "brazil.csv",
    "NJ.csv":          "NJ.csv",
    "MI.csv":          "MI.csv",
    "australia.csv":           "australia.csv",
    "australia_blacklist.csv": "australia_blacklist.csv",
    "greece.csv":      "greece.csv",
    "portugal.csv":    "portugal.csv",
    "romania.csv":     "romania.csv",
    "UK.csv":          "UK.csv",
}

GITHUB_API  = "https://api.github.com"

# ── GitHub API helpers ────────────────────────────────────────────────────────

def get_token():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("❌  GITHUB_TOKEN environment variable not set.")
        print("    Set it with:  export GITHUB_TOKEN=your_token_here")
        sys.exit(1)
    return token


def gh_headers(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_current_file(token, repo_path):
    """
    Fetch the current content and SHA of a file from the GitHub repo.
    Returns (lines_list, sha) where lines_list excludes the timestamp line 1.
    Returns (None, None) if the file doesn't exist yet.
    """
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_path}"
    r = requests.get(url, headers=gh_headers(token))
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    import base64
    content = base64.b64decode(data["content"]).decode("utf-8")
    lines = [l for l in content.splitlines() if l.strip()]
    # Skip line 1 (timestamp) for comparison
    url_lines = lines[1:] if lines else []
    return url_lines, data["sha"]


def get_branch_sha(token, branch):
    """Get the commit SHA of the tip of a branch."""
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/heads/{branch}"
    r = requests.get(url, headers=gh_headers(token))
    r.raise_for_status()
    return r.json()["object"]["sha"]


def create_branch(token, branch_name, from_sha):
    """Create a new branch from a given commit SHA."""
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs"
    payload = {
        "ref": f"refs/heads/{branch_name}",
        "sha": from_sha,
    }
    r = requests.post(url, json=payload, headers=gh_headers(token))
    if r.status_code == 422:
        print(f"    ℹ️   Branch '{branch_name}' already exists — reusing it.")
    else:
        r.raise_for_status()


def push_file(token, branch_name, repo_path, local_content, file_sha):
    """
    Push updated file content to a branch.
    file_sha is required for updates; pass None for new files.
    """
    import base64
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_path}"
    payload = {
        "message": f"update {repo_path}",
        "content": base64.b64encode(local_content.encode("utf-8")).decode("ascii"),
        "branch": branch_name,
    }
    if file_sha:
        payload["sha"] = file_sha
    r = requests.put(url, json=payload, headers=gh_headers(token))
    r.raise_for_status()


def open_pr(token, branch_name, title, body):
    """Open a Pull Request from branch_name into BASE_BRANCH."""
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
    payload = {
        "title": title,
        "body":  body,
        "head":  branch_name,
        "base":  BASE_BRANCH,
    }
    r = requests.post(url, json=payload, headers=gh_headers(token))
    if r.status_code == 422:
        # PR already open for this branch
        print(f"    ℹ️   PR already open for branch '{branch_name}' — skipping.")
        return None
    r.raise_for_status()
    return r.json()["html_url"]

# ── Diff logic ────────────────────────────────────────────────────────────────

def compute_diff(old_lines, new_lines):
    """
    Compare two lists of URL strings (already stripped of timestamp line).
    Comments (lines starting with #) are excluded from comparison.
    Returns (added, removed) as sorted lists.
    """
    def clean(lines):
        return {l.strip().lower() for l in lines
                if l.strip() and not l.strip().startswith('#')}

    old_set = clean(old_lines) if old_lines else set()
    new_set = clean(new_lines)

    added   = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    return added, removed


def format_pr_body(changes):
    """
    Build a readable PR description from a list of
    (filename, added_list, removed_list) tuples.
    """
    lines = [
        "## Gamble Eagle — Licensed Operator List Update",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    for filename, added, removed in changes:
        total_added   = len(added)
        total_removed = len(removed)
        lines.append(f"### {filename}  (+{total_added} / -{total_removed})")
        if added:
            lines.append("")
            lines.append("**Added:**")
            for url in added:
                lines.append(f"- `{url}`")
        if removed:
            lines.append("")
            lines.append("**Removed:**")
            for url in removed:
                lines.append(f"- `{url}`")
        lines.append("")

    lines.append("---")
    lines.append("*Review the changes above and merge to deploy to the extension.*")
    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  GAMBLE EAGLE — Compare & PR")
    print("=" * 60)

    token = get_token()
    changes = []   # (filename, added, removed)
    file_data = {} # filename → (local_content, file_sha, repo_path)

    # ── 1. Compare each CSV ───────────────────────────────────────────────────
    for local_name, repo_path in CSV_FILES.items():
        print(f"\n🔍  Checking {local_name}...")

        if not os.path.exists(local_name):
            print(f"    ⚠️   Local file not found — skipping.")
            continue

        with open(local_name, "r", encoding="utf-8") as f:
            local_content = f.read()

        local_lines = [l for l in local_content.splitlines() if l.strip()]
        # Skip timestamp (line 1) for comparison
        local_url_lines = local_lines[1:] if local_lines else []

        github_url_lines, file_sha = get_current_file(token, repo_path)

        added, removed = compute_diff(github_url_lines, local_url_lines)

        if not added and not removed:
            print(f"    ✅  No changes.")
            continue

        print(f"    📊  +{len(added)} added, -{len(removed)} removed")
        if added:
            for u in added[:5]:
                print(f"        + {u}")
            if len(added) > 5:
                print(f"        ... and {len(added) - 5} more")
        if removed:
            for u in removed[:5]:
                print(f"        - {u}")
            if len(removed) > 5:
                print(f"        ... and {len(removed) - 5} more")

        changes.append((local_name, added, removed))
        file_data[local_name] = (local_content, file_sha, repo_path)

    # ── 2. If no changes anywhere, done ──────────────────────────────────────
    if not changes:
        print("\n✅  All lists are up to date — no PR needed.")
        return

    # ── 3. Create branch and push all changed files ───────────────────────────
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
    branch_name = f"update-lists-{stamp}"
    print(f"\n🌿  Creating branch '{branch_name}'...")
    base_sha = get_branch_sha(token, BASE_BRANCH)
    create_branch(token, branch_name, base_sha)

    for local_name, added, removed in changes:
        local_content, file_sha, repo_path = file_data[local_name]
        print(f"    📤  Pushing {local_name}...")
        push_file(token, branch_name, repo_path, local_content, file_sha)

    # ── 4. Open PR ────────────────────────────────────────────────────────────
    changed_files = [f for f, _, _ in changes]
    title = f"[Lists] Update {', '.join(changed_files)} — {stamp}"
    body  = format_pr_body(changes)

    print(f"\n🔀  Opening PR...")
    pr_url = open_pr(token, branch_name, title, body)

    if pr_url:
        print(f"\n✅  PR opened: {pr_url}")
    print("\n🏁  Done.")


if __name__ == "__main__":
    main()
