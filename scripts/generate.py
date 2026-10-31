#!/usr/bin/env python3
"""Update the text-only GitHub statistics section in the profile README."""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "kolemm14")
TOKEN = os.environ.get("GITHUB_TOKEN")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(ROOT, "README.md")
START = "<!-- PROFILE-STATS:START -->"
END = "<!-- PROFILE-STATS:END -->"


def github_get(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kolemm14-profile-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_repositories():
    repositories = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        batch = github_get(url)
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    
    return [
        repo for repo in repositories
        if not repo.get("fork", False)
        and not repo.get("archived", False)
        and repo.get("name", "").lower() != USERNAME.lower()
    ]



def get_language_totals(repositories):
    totals = Counter()

    # Limit language lookups to the 30 most recently updated repositories.
    for repo in repositories[:30]:
        try:
            languages = github_get(repo["languages_url"])
            totals.update(languages)
        except (urllib.error.URLError, TimeoutError, KeyError) as error:
            print(f"Skipping languages for {repo.get('name')}: {error}")

    return totals


def build_markdown(profile, repositories):
    stars = sum(repo.get("stargazers_count", 0) for repo in repositories)
    forks = sum(repo.get("forks_count", 0) for repo in repositories)
    languages = get_language_totals(repositories)
    top_languages = ", ".join(
        f"`{name}`" for name, _ in languages.most_common(6)
    ) or "No language data available yet"

    ranked = sorted(
        repositories,
        key=lambda repo: (
            repo.get("stargazers_count", 0),
            repo.get("updated_at", ""),
        ),
        reverse=True,
    )[:3]

    lines = [
        '<div align="center">',
        "",
        "| Public repositories | Stars earned | Forks | Followers |",
        "|:--:|:--:|:--:|:--:|",
        (
            f"| **{len(repositories)}** | **{stars}** | **{forks}** "
            f"| **{profile.get('followers', 0)}** |"
        ),
        "",
        f"**Most used languages:** {top_languages}",
        "",
        "</div>",
        "",
        "### Selected repositories",
        "",
    ]

    if ranked:
        lines.append("| Repository | Description | Stars |")
        lines.append("|:--|:--|:--:|")
        for repo in ranked:
            name = repo.get("name", "Repository")
            url = repo.get("html_url", f"https://github.com/{USERNAME}/{name}")
            description = (repo.get("description") or "No description provided.")
            description = description.replace("|", "\\|").replace("\n", " ")
            if len(description) > 105:
                description = description[:102].rstrip() + "..."
            lines.append(
                f"| [**{name}**]({url}) | {description} "
                f"| {repo.get('stargazers_count', 0)} |"
            )
    else:
        lines.append("*No public repositories found yet.*")

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.extend(["", f"<sub>Last updated: {updated}</sub>"])
    return "\n".join(lines)


def update_readme(markdown):
    with open(README_PATH, "r", encoding="utf-8") as file:
        content = file.read()

    pattern = re.compile(
        re.escape(START) + r".*?" + re.escape(END),
        flags=re.DOTALL,
    )
    replacement = f"{START}\n{markdown}\n{END}"

    if not pattern.search(content):
        raise RuntimeError(
            "Statistics markers are missing from README.md; "
            "refusing to overwrite manually written content."
        )

    updated = pattern.sub(lambda _: replacement, content, count=1)
    if updated != content:
        with open(README_PATH, "w", encoding="utf-8", newline="\n") as file:
            file.write(updated)
        print("README statistics updated.")
    else:
        print("README is already up to date.")


def main():
    print(f"Fetching public GitHub data for {USERNAME}...")
    profile = github_get(f"https://api.github.com/users/{USERNAME}")
    repositories = get_repositories()
    markdown = build_markdown(profile, repositories)
    update_readme(markdown)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Profile update failed: {error}", file=sys.stderr)
        raise
