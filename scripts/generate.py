#!/usr/bin/env python3
"""Generate fresh GitHub profile statistics and SVG charts."""

import html
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
ASSETS_DIR = os.path.join(ROOT, "assets")
START = "<!-- PROFILE-STATS:START -->"
END = "<!-- PROFILE-STATS:END -->"

COLORS = ["#ff3030", "#e34f26", "#b91c1c", "#ff6b6b", "#8b5cf6", "#64748b"]


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

    # Exclude forks, archived projects, and the profile repository itself.
    return [
        repo for repo in repositories
        if not repo.get("fork", False)
        and not repo.get("archived", False)
        and repo.get("name", "").lower() != USERNAME.lower()
    ]


def get_language_totals(repositories):
    totals = Counter()
    for repo in repositories[:30]:
        try:
            totals.update(github_get(repo["languages_url"]))
        except (urllib.error.URLError, TimeoutError, KeyError) as error:
            print(f"Skipping languages for {repo.get('name')}: {error}")
    return totals


def svg_text(value):
    return html.escape(str(value), quote=True)


def write_language_chart(languages):
    os.makedirs(ASSETS_DIR, exist_ok=True)
    items = languages.most_common(6)
    width, height = 760, max(190, 100 + len(items) * 43)
    total = sum(value for _, value in items) or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#090909"/><stop offset="1" stop-color="#251014"/></linearGradient></defs>',
        '<rect width="100%" height="100%" rx="18" fill="url(#bg)" stroke="#4b171d"/>',
        '<text x="28" y="38" fill="#ffffff" font-family="Arial,sans-serif" font-size="19" font-weight="700">LANGUAGE DISTRIBUTION</text>',
        '<text x="28" y="60" fill="#a1a1aa" font-family="Arial,sans-serif" font-size="11">Based on byte counts from up to 30 recently updated repositories</text>',
    ]
    if not items:
        parts.append('<text x="28" y="110" fill="#d4d4d8" font-family="Arial,sans-serif" font-size="14">No language data available yet</text>')
    else:
        for index, (name, value) in enumerate(items):
            y = 91 + index * 43
            percent = value / total * 100
            bar_width = 390 * value / max(v for _, v in items)
            color = COLORS[index % len(COLORS)]
            parts.extend([
                f'<text x="28" y="{y + 12}" fill="#f4f4f5" font-family="Arial,sans-serif" font-size="13">{svg_text(name)}</text>',
                f'<rect x="210" y="{y}" width="390" height="14" rx="7" fill="#292126"/>',
                f'<rect x="210" y="{y}" width="{bar_width:.2f}" height="14" rx="7" fill="{color}"/>',
                f'<text x="720" y="{y + 12}" text-anchor="end" fill="#e4e4e7" font-family="Arial,sans-serif" font-size="12">{percent:.1f}%</text>',
            ])
    parts.append("</svg>")
    with open(os.path.join(ASSETS_DIR, "language-stats.svg"), "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(parts))


def write_repository_chart(repositories):
    os.makedirs(ASSETS_DIR, exist_ok=True)
    items = sorted(
        repositories,
        key=lambda repo: (repo.get("stargazers_count", 0), repo.get("updated_at", "")),
        reverse=True,
    )[:5]
    width, height = 760, max(190, 100 + len(items) * 43)
    max_stars = max((repo.get("stargazers_count", 0) for repo in items), default=0) or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#090909"/><stop offset="1" stop-color="#251014"/></linearGradient><linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#7f1d1d"/><stop offset="1" stop-color="#ff3030"/></linearGradient></defs>',
        '<rect width="100%" height="100%" rx="18" fill="url(#bg)" stroke="#4b171d"/>',
        '<text x="28" y="38" fill="#ffffff" font-family="Arial,sans-serif" font-size="19" font-weight="700">TOP REPOSITORIES</text>',
        '<text x="28" y="60" fill="#a1a1aa" font-family="Arial,sans-serif" font-size="11">Ranked by stars, then last update</text>',
    ]
    if not items:
        parts.append('<text x="28" y="110" fill="#d4d4d8" font-family="Arial,sans-serif" font-size="14">No public repositories found</text>')
    else:
        for index, repo in enumerate(items):
            y = 91 + index * 43
            name = repo.get("name", "Repository")
            if len(name) > 24:
                name = name[:21] + "..."
            stars = repo.get("stargazers_count", 0)
            bar_width = 390 * stars / max_stars if stars else 3
            parts.extend([
                f'<text x="28" y="{y + 12}" fill="#f4f4f5" font-family="Arial,sans-serif" font-size="12">{svg_text(name)}</text>',
                f'<rect x="250" y="{y}" width="390" height="14" rx="7" fill="#292126"/>',
                f'<rect x="250" y="{y}" width="{bar_width:.2f}" height="14" rx="7" fill="url(#bar)"/>',
                f'<text x="720" y="{y + 12}" text-anchor="end" fill="#e4e4e7" font-family="Arial,sans-serif" font-size="12">★ {stars}</text>',
            ])
    parts.append("</svg>")
    with open(os.path.join(ASSETS_DIR, "repository-stats.svg"), "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(parts))


def build_markdown(profile, repositories, languages):
    stars = sum(repo.get("stargazers_count", 0) for repo in repositories)
    forks = sum(repo.get("forks_count", 0) for repo in repositories)
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
        '<img src="assets/language-stats.svg" alt="Language distribution chart" width="100%" />',
        "",
        '<img src="assets/repository-stats.svg" alt="Top repositories by stars chart" width="100%" />',
        "",
        "</div>",
        "",
        "### Selected repositories",
        "",
    ]

    if ranked:
        lines.extend(["| Repository | Description | Stars |", "|:--|:--|:--:|"])
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
    languages = get_language_totals(repositories)

    write_language_chart(languages)
    write_repository_chart(repositories)
    update_readme(build_markdown(profile, repositories, languages))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Profile update failed: {error}", file=sys.stderr)
        raise
