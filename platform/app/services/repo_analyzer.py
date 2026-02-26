"""Repo analyzer: fetch README, directory tree, and infer tech stack via GitHub API.

Supports both github.com and GitHub Enterprise instances (e.g. scm.starbucks.com).
The correct API base URL and auth token are resolved automatically from the repo URL.
"""
from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Directories to skip when building tree
_IGNORE_DIRS = {
    "node_modules", ".git", ".github", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", "dist", "build", ".next", ".nuxt", "target",
    ".mypy_cache", ".pytest_cache", ".tox", "egg-info",
}

# File-based tech stack inference rules: filename -> tech list
_TECH_RULES: dict[str, list[str]] = {
    "package.json": ["Node.js"],
    "tsconfig.json": ["TypeScript"],
    "pyproject.toml": ["Python"],
    "requirements.txt": ["Python"],
    "setup.py": ["Python"],
    "go.mod": ["Go"],
    "Cargo.toml": ["Rust"],
    "pom.xml": ["Java", "Maven"],
    "build.gradle": ["Java", "Gradle"],
    "build.gradle.kts": ["Kotlin", "Gradle"],
    "Gemfile": ["Ruby"],
    "composer.json": ["PHP"],
    "Dockerfile": ["Docker"],
    "docker-compose.yml": ["Docker"],
    "docker-compose.yaml": ["Docker"],
    ".dockerignore": ["Docker"],
    "Makefile": ["Make"],
    "CMakeLists.txt": ["C/C++", "CMake"],
}

# Content-based inference: look inside certain files for framework hints
_CONTENT_HINTS: dict[str, list[tuple[str, str]]] = {
    "package.json": [
        ("react", "React"),
        ("vue", "Vue.js"),
        ("angular", "Angular"),
        ("next", "Next.js"),
        ("nuxt", "Nuxt.js"),
        ("express", "Express"),
        ("nestjs", "NestJS"),
        ("vite", "Vite"),
        ("tailwindcss", "Tailwind CSS"),
    ],
    "pyproject.toml": [
        ("fastapi", "FastAPI"),
        ("django", "Django"),
        ("flask", "Flask"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("celery", "Celery"),
    ],
    "requirements.txt": [
        ("fastapi", "FastAPI"),
        ("django", "Django"),
        ("flask", "Flask"),
        ("sqlalchemy", "SQLAlchemy"),
    ],
}


@dataclass
class RepoContext:
    readme_summary: str = ""
    tree: str = ""
    tech_stack: List[str] = field(default_factory=list)
    default_branch: str = "main"


# ---------------------------------------------------------------------------
# Multi-host support: resolve API base URL and token from repo URL host
# ---------------------------------------------------------------------------

def _resolve_api_config(host: str) -> tuple[str, str]:
    """Resolve GitHub API base URL and auth token for the given host.

    Returns (api_base_url, token).
    - For github.com: uses https://api.github.com and GITHUB_TOKEN
    - For GHE instances: uses GHE_BASE_URL and GHE_TOKEN when configured,
      or falls back to https://<host>/api/v3
    """
    if host == "github.com":
        return "https://api.github.com", settings.GITHUB_TOKEN

    # Check if GHE_BASE_URL is configured and matches this host
    if settings.GHE_BASE_URL:
        ghe_parsed = urlparse(settings.GHE_BASE_URL)
        if ghe_parsed.hostname == host:
            return settings.GHE_BASE_URL.rstrip("/"), settings.GHE_TOKEN

    # Fallback: assume GitHub Enterprise at standard API path
    return f"https://{host}/api/v3", settings.GHE_TOKEN


def parse_repo_url(repo_url: str) -> tuple[str, str, str]:
    """Extract owner, repo name, and host from a GitHub / GHE URL.

    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - git@github.com:owner/repo.git
      - https://scm.starbucks.com/owner/repo
      - git@scm.starbucks.com:owner/repo.git

    Returns (owner, repo, host).
    """
    # SSH format: git@<host>:<owner>/<repo>.git
    ssh_match = re.match(r"git@([^:]+):(.+?)/(.+?)(?:\.git)?$", repo_url)
    if ssh_match:
        return ssh_match.group(2), ssh_match.group(3), ssh_match.group(1)

    parsed = urlparse(repo_url)
    host = parsed.hostname or ""
    parts = parsed.path.strip("/").split("/")
    if len(parts) >= 2:
        owner = parts[0]
        repo = parts[1].removesuffix(".git")
        return owner, repo, host

    raise ValueError(f"Cannot parse Git repo URL: {repo_url}")


def _build_headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


async def _fetch_readme(
    client: httpx.AsyncClient, api_base: str, owner: str, repo: str, headers: dict,
) -> str:
    """Fetch README content, truncated to 2000 chars."""
    try:
        resp = await client.get(
            f"{api_base}/repos/{owner}/{repo}/readme",
            headers=headers,
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        content_b64 = data.get("content", "")
        content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        return content[:2000]
    except Exception:
        logger.warning("Failed to fetch README for %s/%s", owner, repo, exc_info=True)
        return ""


async def _fetch_tree(
    client: httpx.AsyncClient,
    api_base: str,
    owner: str,
    repo: str,
    branch: str,
    headers: dict,
    max_depth: int = 2,
) -> tuple[str, list[str]]:
    """Fetch repo tree and build directory structure string.

    Also returns root file list for tech inference.
    """
    try:
        resp = await client.get(
            f"{api_base}/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
            headers=headers,
        )
        if resp.status_code != 200:
            return "", []
        data = resp.json()
        items = data.get("tree", [])
    except Exception:
        logger.warning("Failed to fetch tree for %s/%s", owner, repo, exc_info=True)
        return "", []

    root_files: list[str] = []
    lines: list[str] = []

    for item in items:
        path = item.get("path", "")
        item_type = item.get("type", "")
        parts = path.split("/")

        # Skip ignored directories
        if any(p in _IGNORE_DIRS for p in parts):
            continue

        # Only include up to max_depth
        depth = len(parts)
        if depth > max_depth:
            continue

        # Collect root-level files for tech inference
        if depth == 1 and item_type == "blob":
            root_files.append(parts[0])

        indent = "  " * (depth - 1)
        name = parts[-1]
        suffix = "/" if item_type == "tree" else ""
        lines.append(f"{indent}{name}{suffix}")

    tree_str = "\n".join(lines[:200])  # Cap at 200 lines
    return tree_str, root_files


async def _fetch_file_content(
    client: httpx.AsyncClient,
    api_base: str,
    owner: str,
    repo: str,
    path: str,
    branch: str,
    headers: dict,
) -> Optional[str]:
    """Fetch a single file's content from the repo."""
    try:
        resp = await client.get(
            f"{api_base}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": branch},
            headers=headers,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        content_b64 = data.get("content", "")
        return base64.b64decode(content_b64).decode("utf-8", errors="replace")
    except Exception:
        return None


def _infer_tech_stack(root_files: list[str], file_contents: dict[str, str]) -> list[str]:
    """Infer tech stack from root files and their contents."""
    techs: set[str] = set()

    # File-based rules
    for filename in root_files:
        if filename in _TECH_RULES:
            techs.update(_TECH_RULES[filename])

    # Content-based hints
    for filename, hints in _CONTENT_HINTS.items():
        content = file_contents.get(filename, "").lower()
        if not content:
            continue
        for keyword, tech in hints:
            if keyword in content:
                techs.add(tech)

    return sorted(techs)


async def analyze_repo(repo_url: str, branch: str = "main") -> RepoContext:
    """Analyze a GitHub / GHE repo and return context information.

    Fetches README, directory tree, and infers tech stack via GitHub API.
    Automatically detects whether the repo lives on github.com or a GitHub
    Enterprise instance (e.g. scm.starbucks.com) and uses the correct
    API endpoint and credentials.
    """
    owner, repo, host = parse_repo_url(repo_url)
    api_base, token = _resolve_api_config(host)
    headers = _build_headers(token)

    logger.info(
        "Analyzing repo %s/%s on host=%s api_base=%s",
        owner, repo, host, api_base,
    )

    async with httpx.AsyncClient(
        timeout=30.0,
        transport=httpx.AsyncHTTPTransport(proxy=None),
    ) as client:
        # Fetch README and tree in parallel
        readme = await _fetch_readme(client, api_base, owner, repo, headers)
        tree_str, root_files = await _fetch_tree(
            client, api_base, owner, repo, branch, headers,
        )

        # Fetch key files for tech stack inference
        files_to_check = [f for f in root_files if f in _CONTENT_HINTS]
        file_contents: dict[str, str] = {}
        for filename in files_to_check:
            content = await _fetch_file_content(
                client, api_base, owner, repo, filename, branch, headers,
            )
            if content:
                file_contents[filename] = content

    tech_stack = _infer_tech_stack(root_files, file_contents)

    return RepoContext(
        readme_summary=readme,
        tree=tree_str,
        tech_stack=tech_stack,
        default_branch=branch,
    )

