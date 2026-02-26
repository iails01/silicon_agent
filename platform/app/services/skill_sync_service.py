"""Synchronize skill definitions from filesystem (skills/) into the database."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import SkillModel

logger = logging.getLogger(__name__)

_SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent / "skills"


def _parse_skill_md(path: Path) -> Optional[Dict]:
    """Parse a SKILL.md frontmatter (--- delimited YAML-like block) + body."""
    text = path.read_text(encoding="utf-8")
    # Extract frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        return None

    front = match.group(1)
    body = match.group(2).strip()

    meta: Dict = {}
    for line in front.splitlines():
        line = line.strip()
        if line.startswith("metadata:") or line.startswith("emoji:"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val:
                meta[key] = val

    name = meta.get("name")
    if not name:
        return None

    # Parse tags from metadata block
    tags: List[str] = []
    tags_match = re.search(r'tags:\s*\[(.*?)\]', front)
    if tags_match:
        raw = tags_match.group(1)
        tags = [t.strip().strip('"').strip("'") for t in raw.split(",")]

    # Parse applicable_roles from metadata block
    roles: List[str] = []
    roles_match = re.search(r'applicable_roles:\s*\[(.*?)\]', front)
    if roles_match:
        raw = roles_match.group(1)
        roles = [r.strip().strip('"').strip("'") for r in raw.split(",")]

    return {
        "name": name,
        "display_name": meta.get("display_name", ""),
        "description": meta.get("description", ""),
        "layer": meta.get("layer", "L1"),
        "tags": tags,
        "applicable_roles": roles,
        "content": body,
        "git_path": str(path.relative_to(_SKILLS_ROOT.parent)),
    }


async def sync_skills_from_filesystem(session: AsyncSession) -> Dict[str, str]:
    """Scan skills/ directory and upsert into DB. Returns {name: action} map."""
    if not _SKILLS_ROOT.exists():
        logger.info("Skills directory not found at %s, skipping sync", _SKILLS_ROOT)
        return {}

    results: Dict[str, str] = {}

    all_roles = ["orchestrator", "spec", "coding", "test", "review", "smoke", "doc"]

    for role_dir in sorted(_SKILLS_ROOT.iterdir()):
        if not role_dir.is_dir():
            continue
        role = role_dir.name
        is_shared = role == "shared"

        for skill_dir in sorted(role_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            parsed = _parse_skill_md(skill_md)
            if not parsed:
                logger.warning("Failed to parse %s", skill_md)
                continue

            skill_name = parsed["name"]
            # Determine applicable roles: frontmatter > shared (all) > directory name
            applicable_roles = (
                parsed["applicable_roles"]
                if parsed["applicable_roles"]
                else all_roles if is_shared else [role]
            )
            display_name = (
                parsed["display_name"]
                or parsed["description"][:100]
                or skill_name
            )

            result = await session.execute(
                select(SkillModel).where(SkillModel.name == skill_name)
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                skill = SkillModel(
                    name=skill_name,
                    display_name=display_name,
                    description=parsed["description"],
                    layer=parsed["layer"],
                    tags=parsed["tags"],
                    applicable_roles=applicable_roles,
                    content=parsed["content"],
                    git_path=parsed["git_path"],
                    status="active",
                )
                session.add(skill)
                results[skill_name] = "created"
            else:
                changed = False
                if existing.content != parsed["content"]:
                    existing.content = parsed["content"]
                    changed = True
                if existing.display_name != display_name:
                    existing.display_name = display_name
                    changed = True
                if existing.description != parsed["description"]:
                    existing.description = parsed["description"]
                    changed = True
                if existing.layer != parsed["layer"]:
                    existing.layer = parsed["layer"]
                    changed = True
                if existing.applicable_roles != applicable_roles:
                    existing.applicable_roles = applicable_roles
                    changed = True
                if existing.git_path != parsed["git_path"]:
                    existing.git_path = parsed["git_path"]
                    changed = True
                results[skill_name] = "updated" if changed else "unchanged"

    await session.commit()
    created = sum(1 for v in results.values() if v == "created")
    updated = sum(1 for v in results.values() if v == "updated")
    if created or updated:
        logger.info("Skill sync: %d created, %d updated", created, updated)
    return results
