"""Render bilingual monochrome profile charts from public GitHub REST data."""

from __future__ import annotations

import html
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sync_repositories import HEADERS, OWNER, ROOT_PATH, fetch_language_totals, fetch_repositories


LABELS = {
    "vi": ("GitHub qua những con số", "Dữ liệu từ các repository công khai", "Repository", "Lượt thích", "Bản sao", "Người theo dõi", "Ngôn ngữ sử dụng nhiều nhất", "Dự án cập nhật gần đây", "Nguồn: GitHub API · cập nhật hằng ngày"),
    "en": ("GitHub at a glance", "Data from public repositories", "Repositories", "Stars", "Forks", "Followers", "Most used languages", "Recently updated projects", "Source: GitHub API · updated daily"),
}
SHADES = ("#f5f5f5", "#d4d4d4", "#a3a3a3", "#737373", "#525252", "#404040")


def svg_text(x: int, y: int, value: object, size: int = 16, color: str = "#f5f5f5", weight: int = 400) -> str:
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}">{html.escape(str(value))}</text>')


def fetch_profile() -> dict[str, object]:
    headers = dict(HEADERS)
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/users/{OWNER}", headers=headers)
    with urlopen(request, timeout=30) as response:
        profile = json.load(response)
    if not isinstance(profile, dict) or str(profile.get("login", "")).casefold() != OWNER.casefold():
        raise ValueError("GitHub returned an unexpected user response.")
    return profile


def render(locale: str, profile: dict[str, object], repositories: list[dict[str, object]], languages: dict[str, int]) -> str:
    title, subtitle, repos_label, stars_label, forks_label, followers_label, languages_label, projects_label, source = LABELS[locale]
    stats = (
        (len(repositories), repos_label),
        (sum(int(repo.get("stargazers_count") or 0) for repo in repositories), stars_label),
        (sum(int(repo.get("forks_count") or 0) for repo in repositories), forks_label),
        (int(profile.get("followers") or 0), followers_label),
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="488" viewBox="0 0 900 488" role="img" aria-label="{html.escape(title)}">',
        '<rect width="900" height="488" rx="14" fill="#0d1117"/>',
        '<rect x="1" y="1" width="898" height="486" rx="13" fill="none" stroke="#30363d"/>',
        '<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif">',
        svg_text(32, 48, title, 25, weight=700),
        svg_text(32, 74, subtitle, 13, "#a3a3a3"),
    ]
    for index, (value, label) in enumerate(stats):
        x = 32 + index * 214
        parts.extend((
            f'<rect x="{x}" y="100" width="194" height="82" rx="8" fill="#161b22" stroke="#30363d"/>',
            svg_text(x + 16, 139, value, 26, weight=700),
            svg_text(x + 16, 164, label, 13, "#a3a3a3"),
        ))
    parts.extend((svg_text(32, 224, languages_label, 17, weight=600), '<line x1="32" y1="239" x2="868" y2="239" stroke="#30363d"/>'))
    top_languages = sorted(languages.items(), key=lambda item: (-item[1], item[0].casefold()))[:6]
    total_bytes = sum(languages.values())
    if top_languages and total_bytes:
        for index, (language, byte_count) in enumerate(top_languages):
            x = 32 + index % 2 * 428
            y = 274 + index // 2 * 55
            percentage = byte_count / total_bytes * 100
            parts.extend((
                svg_text(x, y, language, 13, "#e5e5e5", 500),
                svg_text(x + 330, y, f"{percentage:.1f}%", 12, "#a3a3a3"),
                f'<rect x="{x}" y="{y + 10}" width="380" height="7" rx="3" fill="#30363d"/>',
                f'<rect x="{x}" y="{y + 10}" width="{max(2, round(380 * byte_count / total_bytes))}" height="7" rx="3" fill="{SHADES[index]}"/>',
            ))
    else:
        parts.append(svg_text(32, 278, "Chưa có dữ liệu" if locale == "vi" else "No language data yet", 13, "#a3a3a3"))
    parts.extend(('<line x1="32" y1="425" x2="868" y2="425" stroke="#30363d"/>', svg_text(32, 452, projects_label, 13, "#a3a3a3", 600)))
    recent = sorted(repositories, key=lambda repo: str(repo.get("updated_at") or ""), reverse=True)[:3]
    for index, repo in enumerate(recent):
        name = str(repo.get("name") or "")
        parts.append(svg_text(250 + index * 205, 452, name[:19] + "…" if len(name) > 20 else name, 13, "#e5e5e5"))
    parts.extend((svg_text(32, 476, source, 11, "#737373"), '</g></svg>'))
    return "\n".join(parts) + "\n"


def main() -> None:
    if token := os.environ.get("GITHUB_TOKEN"):
        HEADERS["Authorization"] = f"Bearer {token}"
    profile = fetch_profile()
    repositories = fetch_repositories()
    languages = fetch_language_totals(repositories)
    for locale, filename in (("vi", "github-metrics.svg"), ("en", "github-metrics-en.svg")):
        (ROOT_PATH / filename).write_text(render(locale, profile, repositories, languages), encoding="utf-8")
    print(f"Rendered bilingual metrics from {len(repositories)} public repositories.")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise SystemExit(f"Could not render GitHub metrics: {error}") from error
