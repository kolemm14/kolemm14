
import json
import os
import urllib.request
import urllib.error
from html import escape
from datetime import datetime, timezone, timedelta
from pathlib import Path

USERNAME = os.environ["GITHUB_USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "GitHub-Profile-Stats"
}


def request(url, data=None):
    body = None
    headers = HEADERS.copy()

    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url, data=body, headers=headers
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def get_repositories():
    repos = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}"
            f"/repos?type=owner&sort=updated"
            f"&per_page=100&page={page}"
        )

        batch = request(url)
        repos.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return [r for r in repos if not r["fork"]]


def get_languages(repos):
    languages = {}

    for repo in repos:
        url = (
            f"https://api.github.com/repos/"
            f"{USERNAME}/{repo['name']}/languages"
        )

        try:
            result = request(url)

            for name, size in result.items():
                languages[name] = (
                    languages.get(name, 0) + size
                )
        except Exception as error:
            print(f"Langages ignorés: {repo['name']}: {error}")

    return dict(
        sorted(
            languages.items(),
            key=lambda item: item[1],
            reverse=True
        )[:8]
    )


def get_contributions():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    result = request(
        "https://api.github.com/graphql",
        {
            "query": query,
            "variables": {"login": USERNAME}
        }
    )

    user = result["data"]["user"]
    return user["contributionsCollection"]["contributionCalendar"]


def svg_start(title, width=900, height=300):
    return f"""
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
<defs>
  <linearGradient id="red" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#ff1744"/>
    <stop offset="50%" stop-color="#d50000"/>
    <stop offset="100%" stop-color="#6a0000"/>
  </linearGradient>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#151515"/>
    <stop offset="100%" stop-color="#090909"/>
  </linearGradient>
</defs>
<rect width="100%" height="100%" rx="18" fill="url(#bg)"/>
<rect x="0" y="0" width="5" height="100%"
      rx="2" fill="url(#red)"/>
<text x="35" y="48" fill="#ffffff"
      font-size="23" font-weight="bold"
      font-family="Arial">{escape(title)}</text>
"""


def save_svg(name, content):
    path = ASSETS / name
    path.write_text(
        content + "\n</svg>",
        encoding="utf-8"
    )
    print(f"Generated: {path}")


def generate_stats(repos, profile):
    stars = sum(r["stargazers_count"] for r in repos)
    forks = sum(r["forks_count"] for r in repos)

    values = [
        ("REPOSITORIES", len(repos)),
        ("TOTAL STARS", stars),
        ("TOTAL FORKS", forks),
        ("FOLLOWERS", profile["followers"])
    ]

    svg = svg_start("GITHUB OVERVIEW", 900, 230)

    for i, (label, value) in enumerate(values):
        x = 35 + i * 215

        svg += f"""
<rect x="{x}" y="85" width="190" height="105"
      rx="12" fill="#202020"
      stroke="#3a2020"/>
<text x="{x+15}" y="120" fill="#999"
      font-size="13" font-family="Arial">{label}</text>
<text x="{x+15}" y="165" fill="url(#red)"
      font-size="32" font-weight="bold"
      font-family="Arial">{value}</text>
"""

    save_svg("stats.svg", svg)


def generate_languages(languages):
    total = sum(languages.values()) or 1
    svg = svg_start("LANGUAGE DISTRIBUTION", 900, 300)

    x = 35
    y = 95
    bar_width = 820

    colors = [
        "#ff1744", "#d50000", "#ff5252",
        "#9b0000", "#ff8a80", "#b71c1c",
        "#ef5350", "#650000"
    ]

    for i, (name, size) in enumerate(languages.items()):
        percentage = size / total * 100
        width = bar_width * percentage / 100
        color = colors[i % len(colors)]

        svg += f"""
<rect x="{x}" y="{y}" width="{width:.2f}"
      height="17" fill="{color}"/>
<text x="{x}" y="{y+42}" fill="#eeeeee"
      font-size="14" font-family="Arial">
      {escape(name)} — {percentage:.1f}%
</text>
"""
        x += width

    if not languages:
        svg += '<text x="35" y="120" fill="#aaa">No language data</text>'

    save_svg("languages.svg", svg)


def generate_contributions(calendar):
    days = [
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ][-364:]

    svg = svg_start("CONTRIBUTION ACTIVITY", 900, 200)

    colors = [
        "#242424", "#650000",
        "#a00000", "#d50000", "#ff1744"
    ]

    start_x = 35
    start_y = 85
    cell = 11
    gap = 4

    max_count = max(
        (d["contributionCount"] for d in days),
        default=1
    ) or 1

    for i, day in enumerate(days):
        count = day["contributionCount"]
        level = min(4, int(count / max_count * 4))
        x = start_x + (i // 7) * (cell + gap)
        y = start_y + (i % 7) * (cell + gap)

        svg += f"""
<rect x="{x}" y="{y}" width="{cell}"
      height="{cell}" rx="2"
      fill="{colors[level]}">
<title>{day['date']}: {count} contributions</title>
</rect>
"""

    total = calendar["totalContributions"]

    svg += f"""
<text x="35" y="180" fill="#ff5252"
      font-size="14" font-family="Arial">
      {total} contributions in the selected year
</text>
"""

    save_svg("contributions.svg", svg)


def main():
    print(f"Fetching GitHub data for {USERNAME}")

    repos = get_repositories()
    profile = request(
        f"https://api.github.com/users/{USERNAME}"
    )

    languages = get_languages(repos)

    try:
        calendar = get_contributions()
        generate_contributions(calendar)
    except Exception as error:
        print(f"Contribution calendar unavailable: {error}")

    generate_stats(repos, profile)
    generate_languages(languages)

    print("All available statistics generated.")


if __name__ == "__main__":
    main()
