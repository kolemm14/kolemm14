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

COLORS = ["#FF3B30", "#00C2FF", "#FFD60A", "#30D158", "#BF5AF2", "#FF9F0A", "#64D2FF", "#FF375F"]


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
    """Write a compact donut chart with a clear legend for profile visitors."""
    import math

    os.makedirs(ASSETS_DIR, exist_ok=True)
    ranked = languages.most_common()
    if len(ranked) > 5:
        items = ranked[:5]
        items.append(("Other", sum(value for _, value in ranked[5:])))
    else:
        items = ranked

    total = sum(value for _, value in items)
    width, height = 760, 260
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="14" fill="#0b0b0d" stroke="#292929"/>',
        '<text x="28" y="34" fill="#ffffff" font-family="Arial,sans-serif" font-size="18" font-weight="700">LANGUAGES USED</text>',
        '<text x="28" y="54" fill="#a1a1aa" font-family="Arial,sans-serif" font-size="11">Share of detected code across public repositories</text>',
    ]

    if not items or total == 0:
        parts.append('<text x="28" y="120" fill="#d4d4d8" font-family="Arial,sans-serif" font-size="14">No language data available yet</text>')
    else:
        cx, cy, radius = 150, 151, 58
        circumference = 2 * math.pi * radius
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#292929" stroke-width="22"/>')
        offset = 0.0
        for index, (name, value) in enumerate(items):
            share = value / total
            dash = circumference * share
            color = COLORS[index % len(COLORS)]
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{color}" '
                f'stroke-width="22" stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" '
                f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
            )
            offset += dash

            y = 94 + index * 28
            parts.extend([
                f'<circle cx="270" cy="{y - 4}" r="5" fill="{color}"/>',
                f'<text x="284" y="{y}" fill="#f4f4f5" font-family="Arial,sans-serif" font-size="13">{svg_text(name)}</text>',
                f'<text x="720" y="{y}" text-anchor="end" fill="#e4e4e7" font-family="Arial,sans-serif" font-size="12">{share * 100:.1f}%</text>',
            ])
        parts.extend([
            f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" fill="#ffffff" font-family="Arial,sans-serif" font-size="16" font-weight="700">{len(ranked)}</text>',
            f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" fill="#a1a1aa" font-family="Arial,sans-serif" font-size="10">languages</text>',
        ])

    parts.append("</svg>")
    with open(os.path.join(ASSETS_DIR, "language-stats.svg"), "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(parts))

def record_star_history(repositories):
    """Persist a daily snapshot so the chart can show real change over time."""
    history_dir = os.path.join(ROOT, "data")
    history_path = os.path.join(history_dir, "star-history.json")
    os.makedirs(history_dir, exist_ok=True)

    try:
        with open(history_path, "r", encoding="utf-8") as file:
            history = json.load(file)
        if not isinstance(history, list):
            history = []
    except (FileNotFoundError, json.JSONDecodeError):
        history = []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stars = sum(repo.get("stargazers_count", 0) for repo in repositories)
    if history and history[-1].get("date") == today:
        history[-1]["stars"] = stars
    else:
        history.append({"date": today, "stars": stars})

    # Keep one year of daily observations for a compact, useful chart.
    history = history[-365:]
    with open(history_path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(history, file, indent=2)
        file.write("\n")
    return history


def write_repository_chart(repositories, history):
    os.makedirs(ASSETS_DIR, exist_ok=True)
    width, height = 760, 260
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="14" fill="#0b0b0d" stroke="#292929"/>',
        '<text x="28" y="34" fill="#ffffff" font-family="Arial,sans-serif" font-size="18" font-weight="700">STAR HISTORY</text>',
        '<text x="28" y="54" fill="#a1a1aa" font-family="Arial,sans-serif" font-size="11">Total stars across public projects · daily snapshots</text>',
    ]
    if not history:
        parts.append('<text x="28" y="120" fill="#d4d4d8" font-family="Arial,sans-serif" font-size="14">History will appear after the first snapshot.</text>')
    else:
        values = [int(point.get("stars", 0)) for point in history]
        low, high = min(values), max(values)
        span = max(high - low, 1)
        left, right, top, bottom = 42, 718, 84, 205
        points = []
        for i, value in enumerate(values):
            x = left if len(values) == 1 else left + i * (right - left) / (len(values) - 1)
            y = bottom - ((value - low) / span) * (bottom - top)
            points.append((x, y))
        # Add a subtle grid and a filled area under the curve.
        for grid_y in (top, (top + bottom) / 2, bottom):
            parts.append(f'<line x1="{left}" y1="{grid_y:.1f}" x2="{right}" y2="{grid_y:.1f}" stroke="#292929" stroke-dasharray="3 5"/>')
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        area = f"{left},{bottom} " + line + f" {right},{bottom}"
        parts.append(f'<polygon points="{area}" fill="#ef4444" opacity="0.12"/>')
        parts.append(f'<polyline points="{line}" fill="none" stroke="#ff4545" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
        x, y = points[-1]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#ff4545" stroke="#ffffff" stroke-width="2"/>')
        parts.append(f'<text x="{left}" y="232" fill="#a1a1aa" font-family="Arial,sans-serif" font-size="11">{svg_text(history[0].get("date", ""))}</text>')
        parts.append(f'<text x="{right}" y="232" text-anchor="end" fill="#a1a1aa" font-family="Arial,sans-serif" font-size="11">{svg_text(history[-1].get("date", ""))}</text>')
        parts.append(f'<text x="{right}" y="77" text-anchor="end" fill="#ffffff" font-family="Arial,sans-serif" font-size="13" font-weight="700">{values[-1]} stars</text>')
        if len(history) < 2:
            parts.append('<text x="380" y="250" text-anchor="middle" fill="#777777" font-family="Arial,sans-serif" font-size="10">The curve will become meaningful as daily snapshots accumulate.</text>')
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
    history = record_star_history(repositories)
    write_repository_chart(repositories, history)
    update_readme(build_markdown(profile, repositories, languages))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Profile update failed: {error}", file=sys.stderr)
        raise
