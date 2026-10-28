"""Refresh repository and source-language sections in the profile README."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


OWNER = "dangkhoa2004"
PROFILE_REPOSITORY = OWNER.casefold()
ROOT_PATH = Path(__file__).resolve().parents[2]
README_PATHS = {
    "vi": ROOT_PATH / "README.md",
    "en": ROOT_PATH / "README_EN.md",
}
API_URL = (
    f"https://api.github.com/users/{OWNER}/repos"
    "?type=owner&sort=updated&direction=desc&per_page=100&page=1"
)
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "dangkhoa2004-profile-readme-sync",
    "X-GitHub-Api-Version": "2026-03-10",
}


def fetch_repositories() -> list[dict[str, object]]:
    """Fetch every public owned repository, following GitHub's pagination links."""
    repositories: list[dict[str, object]] = []
    next_url: str | None = API_URL

    while next_url:
        request = Request(next_url, headers=HEADERS)
        with urlopen(request, timeout=30) as response:
            page = json.load(response)
            link_header = response.headers.get("Link", "")

        if not isinstance(page, list):
            raise ValueError("GitHub returned an unexpected repositories response.")
        repositories.extend(page)

        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        next_url = match.group(1) if match else None

    return [
        repo
        for repo in repositories
        if isinstance(repo, dict)
        and not repo.get("private", True)
        and str(repo.get("owner", {}).get("login", "")).casefold() == OWNER.casefold()
        and str(repo.get("name", "")).casefold() != PROFILE_REPOSITORY
    ]


def clean_cell(value: object, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return html.escape(text, quote=False).replace("|", "&#124;").replace("`", "\\`") or "—"


def repository_url(repo: dict[str, object]) -> str:
    owner = str(repo.get("owner", {}).get("login", ""))
    name = str(repo.get("name", ""))
    url = f"https://github.com/{quote(owner, safe='')}/{quote(name, safe='')}"
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError("Unexpected repository URL from GitHub.")
    return url


def fetch_language_totals(repositories: list[dict[str, object]]) -> dict[str, int]:
    """Combine GitHub's detected source-language byte counts across repositories."""
    totals: dict[str, int] = {}
    for repo in repositories:
        url = str(repo.get("languages_url", ""))
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "api.github.com":
            raise ValueError("GitHub returned an unexpected languages API URL.")

        request = Request(url, headers=HEADERS)
        with urlopen(request, timeout=30) as response:
            languages = json.load(response)
        if not isinstance(languages, dict):
            raise ValueError("GitHub returned an unexpected languages response.")

        for language, byte_count in languages.items():
            if isinstance(language, str) and isinstance(byte_count, int):
                totals[language] = totals.get(language, 0) + byte_count
    return totals


def render_languages(language_totals: dict[str, int]) -> str:
    languages = sorted(language_totals, key=lambda name: (-language_totals[name], name.casefold()))
    if not languages:
        return "—"
    return " · ".join(f"`{clean_cell(language)}`" for language in languages)


def render_repositories(repositories: list[dict[str, object]], locale: str) -> str:
    if not repositories:
        return "Chưa tìm thấy repository công khai nào." if locale == "vi" else "No public repositories found."

    if locale == "vi":
        rows = ["| Dự án | Mô tả | Ngôn ngữ chính |", "|---|---|---|"]
    else:
        rows = ["| Repository | Main language |", "|---|---|"]

    for repo in repositories:
        name = clean_cell(repo.get("name"))
        language = clean_cell(repo.get("language"))
        url = repository_url(repo)
        if locale == "vi":
            description = clean_cell(repo.get("description"), limit=140)
            rows.append(f"| [{name}]({url}) | {description} | {language} |")
        else:
            rows.append(f"| [{name}]({url}) | {language} |")
    return "\n".join(rows)


def replace_section(readme: str, name: str, content: str) -> str:
    start = f"<!-- {name}:START -->"
    end = f"<!-- {name}:END -->"
    if readme.count(start) != 1 or readme.count(end) != 1:
        raise ValueError(f"README must contain exactly one {name} section marker pair.")
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    return pattern.sub(f"{start}\n{content}\n{end}", readme)


def main() -> None:
    repositories = fetch_repositories()
    language_totals = fetch_language_totals(repositories)
    languages = render_languages(language_totals)
    for locale, readme_path in README_PATHS.items():
        readme = readme_path.read_text(encoding="utf-8")
        readme = replace_section(readme, "LANGUAGES", languages)
        readme = replace_section(readme, "REPOSITORIES", render_repositories(repositories, locale))
        readme_path.write_text(readme.rstrip() + "\n", encoding="utf-8")
    print(f"Updated Vietnamese and English profile READMEs with {len(repositories)} public repositories.")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise SystemExit(f"Could not update profile README: {error}") from error
