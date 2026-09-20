#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
OWNERS = ("raillen", "poppy-team", "hummrun")
EXCLUDED_REPOS = {"raillen/raillen"}
WINDOW_DAYS = 30
MAX_COMMIT_PAGES_PER_REPO = 10


def api_get(path: str, params: dict[str, str | int] | None = None):
    url = f"https://api.github.com{path}"
    if params:
        url += "?" + urlencode(params)

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "raillen-profile-metrics",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        # Empty repositories return 409 on the commits endpoint.
        if error.code in {404, 409}:
            return []
        raise


def list_repositories(owner: str) -> list[dict]:
    repositories: list[dict] = []

    for page in range(1, 6):
        batch = api_get(
            f"/users/{owner}/repos",
            {
                "per_page": 100,
                "page": page,
                "type": "owner",
                "sort": "pushed",
                "direction": "desc",
            },
        )

        if not isinstance(batch, list):
            break

        repositories.extend(batch)

        if len(batch) < 100:
            break

    return repositories


def parse_github_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def repository_languages(full_name: str) -> Counter[str]:
    data = api_get(f"/repos/{full_name}/languages")
    if not isinstance(data, dict):
        return Counter()
    return Counter({str(language): int(size) for language, size in data.items()})


def repository_commits(
    full_name: str,
    since: datetime,
) -> list[datetime]:
    dates: list[datetime] = []

    for page in range(1, MAX_COMMIT_PAGES_PER_REPO + 1):
        batch = api_get(
            f"/repos/{full_name}/commits",
            {
                "since": since.isoformat().replace("+00:00", "Z"),
                "per_page": 100,
                "page": page,
            },
        )

        if not isinstance(batch, list):
            break

        for item in batch:
            commit = item.get("commit", {})
            author = commit.get("author") or {}
            timestamp = parse_github_time(author.get("date"))
            if timestamp:
                dates.append(timestamp)

        if len(batch) < 100:
            break

    return dates


def collect_metrics() -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)

    repositories: list[dict] = []

    for owner in OWNERS:
        for repository in list_repositories(owner):
            full_name = repository.get("full_name", "")
            if (
                not full_name
                or full_name in EXCLUDED_REPOS
                or repository.get("fork")
                or repository.get("archived")
            ):
                continue

            repositories.append(repository)

    active_repositories = [
        repository
        for repository in repositories
        if (parse_github_time(repository.get("pushed_at")) or datetime.min.replace(tzinfo=timezone.utc))
        >= since
    ]

    languages: Counter[str] = Counter()
    commit_dates: list[datetime] = []

    # Metrics follow active work. Old repositories remain part of the project count,
    # but do not burn API calls every day.
    for repository in active_repositories:
        full_name = repository["full_name"]
        languages.update(repository_languages(full_name))
        commit_dates.extend(repository_commits(full_name, since))

    daily = Counter(
        timestamp.astimezone(timezone.utc).date().isoformat()
        for timestamp in commit_dates
    )

    top_repositories = sorted(
        active_repositories,
        key=lambda repository: repository.get("pushed_at") or "",
        reverse=True,
    )[:5]

    total_language_bytes = sum(languages.values())
    top_languages = []

    for language, size in languages.most_common(5):
        percentage = (size / total_language_bytes * 100) if total_language_bytes else 0
        top_languages.append((language, percentage))

    return {
        "generated_at": now,
        "since": since,
        "repositories": repositories,
        "active_repositories": active_repositories,
        "commits": len(commit_dates),
        "daily": daily,
        "top_languages": top_languages,
        "top_repositories": top_repositories,
    }


def render_svg(metrics: dict, *, dark: bool) -> str:
    if dark:
        background = "#0d1117"
        surface = "#161b22"
        border = "#30363d"
        primary = "#f0f6fc"
        secondary = "#8b949e"
        accent = "#d2a8ff"
        green = "#3fb950"
        yellow = "#d29922"
        blue = "#58a6ff"
        bar = "#a371f7"
    else:
        background = "#ffffff"
        surface = "#f6f8fa"
        border = "#d0d7de"
        primary = "#1f2328"
        secondary = "#656d76"
        accent = "#8250df"
        green = "#1a7f37"
        yellow = "#9a6700"
        blue = "#0969da"
        bar = "#8250df"

    now: datetime = metrics["generated_at"]
    daily: Counter[str] = metrics["daily"]
    days = [
        (now - timedelta(days=offset)).date()
        for offset in reversed(range(WINDOW_DAYS))
    ]
    values = [daily.get(day.isoformat(), 0) for day in days]
    max_value = max(values) if values else 0

    chart_x = 48
    chart_y = 220
    chart_width = 804
    chart_height = 82
    gap = 4
    bar_width = (chart_width - gap * (WINDOW_DAYS - 1)) / WINDOW_DAYS

    bars = []
    for index, value in enumerate(values):
        height = 3 if max_value == 0 else max(3, (value / max_value) * chart_height)
        x = chart_x + index * (bar_width + gap)
        y = chart_y + chart_height - height
        opacity = 0.38 if value == 0 else 0.95
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
            f'height="{height:.2f}" rx="2" fill="{bar}" opacity="{opacity}"/>'
        )

    language_parts = []
    start_x = 49
    available = 802

    for language, percentage in metrics["top_languages"]:
        width = available * percentage / 100
        if width < 2:
            continue
        language_parts.append(
            f'<rect x="{start_x:.2f}" y="352" width="{width:.2f}" '
            f'height="8" rx="4" fill="{accent}" opacity="0.88"/>'
        )
        start_x += width + 2

    languages_text = " · ".join(
        f"{language} {percentage:.0f}%"
        for language, percentage in metrics["top_languages"]
    ) or "warming up"

    repo_names = " · ".join(
        repository["name"]
        for repository in metrics["top_repositories"]
    ) or "quiet day in the lab"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="405" viewBox="0 0 900 405" role="img" aria-labelledby="title desc">
  <title id="title">Raillen Lab Pulse</title>
  <desc id="desc">Activity across Raillen, Poppy Team and Humm.run during the last 30 days.</desc>

  <rect x="1" y="1" width="898" height="403" rx="22" fill="{background}" stroke="{border}"/>

  <text x="48" y="51" fill="{primary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="24" font-weight="700">
    raillen lab pulse
  </text>
  <text x="48" y="76" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="13">
    last 30 days across raillen · poppy team · humm.run
  </text>

  <rect x="48" y="99" width="190" height="91" rx="14" fill="{surface}" stroke="{border}"/>
  <text x="65" y="126" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="12">commits · 30d</text>
  <text x="65" y="166" fill="{green}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="31" font-weight="700">{metrics["commits"]}</text>

  <rect x="252" y="99" width="190" height="91" rx="14" fill="{surface}" stroke="{border}"/>
  <text x="269" y="126" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="12">active repos · 30d</text>
  <text x="269" y="166" fill="{blue}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="31" font-weight="700">{len(metrics["active_repositories"])}</text>

  <rect x="456" y="99" width="190" height="91" rx="14" fill="{surface}" stroke="{border}"/>
  <text x="473" y="126" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="12">public projects</text>
  <text x="473" y="166" fill="{accent}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="31" font-weight="700">{len(metrics["repositories"])}</text>

  <rect x="660" y="99" width="192" height="91" rx="14" fill="{surface}" stroke="{border}"/>
  <text x="677" y="126" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="12">ecosystem</text>
  <text x="677" y="158" fill="{yellow}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="18" font-weight="700">3 little homes</text>
  <text x="677" y="178" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="11">raillen · poppy · humm</text>

  <text x="48" y="211" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="12">daily commit weather</text>
  {"".join(bars)}

  <text x="48" y="328" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="11">
    30 days ago
  </text>
  <text x="812" y="328" text-anchor="end" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="11">
    today
  </text>

  <text x="48" y="347" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="11">active-language mix</text>
  {"".join(language_parts)}
  <text x="48" y="379" fill="{primary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="11">{escape(languages_text)}</text>

  <text x="852" y="379" text-anchor="end" fill="{secondary}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="10">
    updated {now.date().isoformat()}
  </text>

  <title>{escape(repo_names)}</title>
</svg>
"""


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    metrics = collect_metrics()

    (ASSETS / "lab-pulse-dark.svg").write_text(
        render_svg(metrics, dark=True),
        encoding="utf-8",
    )
    (ASSETS / "lab-pulse-light.svg").write_text(
        render_svg(metrics, dark=False),
        encoding="utf-8",
    )

    summary = {
        "generated_at": metrics["generated_at"].isoformat(),
        "window_days": WINDOW_DAYS,
        "owners": OWNERS,
        "commits": metrics["commits"],
        "active_repositories": len(metrics["active_repositories"]),
        "public_projects": len(metrics["repositories"]),
        "top_languages": metrics["top_languages"],
        "top_repositories": [
            repository["full_name"]
            for repository in metrics["top_repositories"]
        ],
    }

    (ASSETS / "lab-pulse.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
