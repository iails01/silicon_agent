from __future__ import annotations

import io
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import SkillModel, SkillVersionModel
from app.schemas.skill import (
    SkillCreateRequest,
    SkillDetailResponse,
    SkillEffectivenessItem,
    SkillImportResponse,
    SkillListResponse,
    SkillStatsResponse,
    SkillUpdateRequest,
)
from app.services import skill_sync_service


class SkillImportError(ValueError):
    pass


def _sanitize_skill_dir_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip(".-")
    if not sanitized:
        raise SkillImportError("无法根据 skill name 生成有效目录名")
    return sanitized


class SkillService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _normalize_archive_path(self, raw_path: str) -> PurePosixPath:
        normalized = raw_path.replace("\\", "/").strip("/")
        path = PurePosixPath(normalized)
        if (
            not normalized
            or path.is_absolute()
            or ".." in path.parts
            or any(part in {"", "."} for part in path.parts)
        ):
            raise SkillImportError(f"导入包包含不安全路径: {raw_path}")
        return path

    def _resolve_import_role(self, skill_root: PurePosixPath) -> str:
        if skill_root.parts and skill_root.parts[0] in skill_sync_service.KNOWN_SKILL_ROLE_DIRS:
            return skill_root.parts[0]
        return "shared"

    async def _list_existing_skill_dirs(self, skill_name: str) -> list[Path]:
        paths: set[Path] = set()
        skills_root = skill_sync_service.get_skills_root()

        result = await self.session.execute(
            select(SkillModel).where(SkillModel.name == skill_name)
        )
        existing = result.scalar_one_or_none()
        if existing and existing.git_path:
            existing_path = (skills_root.parent / existing.git_path).resolve()
            if existing_path.name == "SKILL.md":
                paths.add(existing_path.parent)
            elif existing_path.is_dir():
                paths.add(existing_path)

        if skills_root.exists():
            for skill_md in skills_root.rglob("SKILL.md"):
                parsed = skill_sync_service.parse_skill_definition(skill_md)
                if parsed and parsed.get("name") == skill_name:
                    paths.add(skill_md.parent)

        return sorted(paths)

    async def import_skill_bundle(
        self,
        filename: Optional[str],
        content: bytes,
    ) -> SkillImportResponse:
        if not content:
            raise SkillImportError("导入包为空")

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                file_entries: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    archive_path = self._normalize_archive_path(info.filename)
                    mode = info.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise SkillImportError("导入包不能包含符号链接")
                    file_entries.append((info, archive_path))

                if not file_entries:
                    raise SkillImportError("导入包为空")

                skill_md_entries = [
                    archive_path
                    for _, archive_path in file_entries
                    if archive_path.name == "SKILL.md"
                ]
                if not skill_md_entries:
                    raise SkillImportError("导入包缺少 SKILL.md")
                if len(skill_md_entries) > 1:
                    raise SkillImportError("导入包只能包含一个 SKILL.md")

                skill_md_path = skill_md_entries[0]
                skill_root = skill_md_path.parent

                with tempfile.TemporaryDirectory(prefix="skill_import_") as temp_dir:
                    temp_root = Path(temp_dir)
                    archive.extractall(temp_root)

                    extracted_skill_root = temp_root
                    if skill_root.parts:
                        extracted_skill_root = temp_root.joinpath(*skill_root.parts)

                    skill_md_file = extracted_skill_root / "SKILL.md"
                    parsed = skill_sync_service.parse_skill_definition(skill_md_file)
                    if not parsed:
                        raise SkillImportError("SKILL.md 缺少有效 frontmatter，无法解析 skill name")

                    skill_name = str(parsed.get("name", "")).strip()
                    if not skill_name:
                        raise SkillImportError("SKILL.md 缺少有效的 name")

                    target_role = self._resolve_import_role(skill_root)
                    target_dir = (
                        skill_sync_service.get_skills_root()
                        / target_role
                        / _sanitize_skill_dir_name(skill_name)
                    )

                    for existing_dir in await self._list_existing_skill_dirs(skill_name):
                        if existing_dir.exists():
                            shutil.rmtree(existing_dir, ignore_errors=True)

                    if target_dir.exists():
                        shutil.rmtree(target_dir, ignore_errors=True)
                    target_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(extracted_skill_root, target_dir)

        except zipfile.BadZipFile as exc:
            bundle_name = filename or "skill.skill"
            raise SkillImportError(f"{bundle_name} 不是有效的 .skill 压缩包") from exc

        sync_result = await skill_sync_service.sync_skills_from_filesystem(self.session)
        imported = await self.get_skill(skill_name)
        if imported is None:
            raise SkillImportError("导入完成后未能在数据库中找到 skill 记录")

        return SkillImportResponse(
            name=imported.name,
            action=sync_result.get(imported.name, "unchanged"),
            git_path=imported.git_path or "",
            synced=len(sync_result),
            created=sum(1 for value in sync_result.values() if value == "created"),
            updated=sum(1 for value in sync_result.values() if value == "updated"),
        )

    async def list_skills(
        self,
        page: int = 1,
        page_size: int = 20,
        name: Optional[str] = None,
        layer: Optional[str] = None,
        tag: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> SkillListResponse:
        query = select(SkillModel)
        count_query = select(func.count()).select_from(SkillModel)

        if status:
            if status != "all":
                query = query.where(SkillModel.status == status)
                count_query = count_query.where(SkillModel.status == status)

        if name and name.strip():
            pattern = f"%{name.strip()}%"
            name_filter = (SkillModel.name.ilike(pattern) | SkillModel.display_name.ilike(pattern))
            query = query.where(name_filter)
            count_query = count_query.where(name_filter)

        if layer:
            query = query.where(SkillModel.layer == layer)
            count_query = count_query.where(SkillModel.layer == layer)

        if tag and tag.strip():
            # Tags are stored as JSON array; match token string conservatively.
            pattern = f'%"{tag.strip()}"%'
            tag_filter = cast(SkillModel.tags, String).ilike(pattern)
            query = query.where(tag_filter)
            count_query = count_query.where(tag_filter)

        if role and role.strip():
            pattern = f'%"{role.strip()}"%'
            role_filter = cast(SkillModel.applicable_roles, String).ilike(pattern)
            query = query.where(role_filter)
            count_query = count_query.where(role_filter)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(SkillModel.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(query)
        skills = result.scalars().all()

        return SkillListResponse(
            items=[SkillDetailResponse.model_validate(s) for s in skills],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_skill(self, request: SkillCreateRequest) -> SkillDetailResponse:
        skill = SkillModel(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            layer=request.layer,
            tags=request.tags,
            applicable_roles=request.applicable_roles,
            content=request.content,
            git_path=request.git_path,
        )
        self.session.add(skill)
        await self.session.commit()
        await self.session.refresh(skill)
        return SkillDetailResponse.model_validate(skill)

    async def get_skill(self, name: str) -> Optional[SkillDetailResponse]:
        result = await self.session.execute(
            select(SkillModel).where(SkillModel.name == name)
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            return None
        return SkillDetailResponse.model_validate(skill)

    async def update_skill(self, name: str, request: SkillUpdateRequest) -> Optional[SkillDetailResponse]:
        result = await self.session.execute(
            select(SkillModel).where(SkillModel.name == name)
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            return None

        # Snapshot current version before overwriting
        snapshot = SkillVersionModel(
            skill_id=skill.id,
            version=skill.version,
            content=skill.content,
            change_summary=f"Snapshot before update to {request.version or skill.version}",
        )
        self.session.add(snapshot)

        update_data = request.model_dump(exclude_unset=True)
        for fld, value in update_data.items():
            setattr(skill, fld, value)

        await self.session.commit()
        await self.session.refresh(skill)
        return SkillDetailResponse.model_validate(skill)

    async def archive_skill(self, name: str) -> Optional[SkillDetailResponse]:
        result = await self.session.execute(
            select(SkillModel).where(SkillModel.name == name)
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            return None
        skill.status = "archived"
        await self.session.commit()
        await self.session.refresh(skill)
        return SkillDetailResponse.model_validate(skill)

    async def get_versions(self, name: str) -> List[dict]:
        result = await self.session.execute(
            select(SkillModel).where(SkillModel.name == name)
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            return []

        # Current version + historical snapshots
        versions = [{"version": skill.version, "created_at": skill.updated_at.isoformat(), "current": True}]
        ver_result = await self.session.execute(
            select(SkillVersionModel)
            .where(SkillVersionModel.skill_id == skill.id)
            .order_by(SkillVersionModel.created_at.desc())
        )
        for v in ver_result.scalars().all():
            versions.append({
                "version": v.version,
                "created_at": v.created_at.isoformat(),
                "current": False,
                "change_summary": v.change_summary,
            })
        return versions

    async def rollback(self, name: str, version: str) -> Optional[SkillDetailResponse]:
        result = await self.session.execute(
            select(SkillModel).where(SkillModel.name == name)
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            return None

        # Find the requested version snapshot
        ver_result = await self.session.execute(
            select(SkillVersionModel).where(
                SkillVersionModel.skill_id == skill.id,
                SkillVersionModel.version == version,
            ).order_by(SkillVersionModel.created_at.desc()).limit(1)
        )
        target = ver_result.scalar_one_or_none()
        if target is None:
            return None

        # Snapshot current state before rollback
        snapshot = SkillVersionModel(
            skill_id=skill.id,
            version=skill.version,
            content=skill.content,
            change_summary=f"Snapshot before rollback to {version}",
        )
        self.session.add(snapshot)

        # Restore
        skill.version = target.version
        skill.content = target.content

        await self.session.commit()
        await self.session.refresh(skill)
        return SkillDetailResponse.model_validate(skill)

    async def get_stats(self) -> SkillStatsResponse:
        total_result = await self.session.execute(
            select(func.count()).select_from(SkillModel).where(SkillModel.status != "archived")
        )
        total = total_result.scalar() or 0

        by_layer: Dict[str, int] = {}
        for layer_val in ("L1", "L2", "L3"):
            count_result = await self.session.execute(
                select(func.count())
                .select_from(SkillModel)
                .where(SkillModel.layer == layer_val, SkillModel.status != "archived")
            )
            count = count_result.scalar() or 0
            if count > 0:
                by_layer[layer_val] = count

        by_status: Dict[str, int] = {}
        for status_val in ("active", "draft", "archived"):
            count_result = await self.session.execute(
                select(func.count())
                .select_from(SkillModel)
                .where(SkillModel.status == status_val)
            )
            count = count_result.scalar() or 0
            if count > 0:
                by_status[status_val] = count

        # Skill effectiveness from feedback aggregation
        from app.services.skill_feedback_service import get_skill_effectiveness
        effectiveness_data = await get_skill_effectiveness(self.session)
        effectiveness = [SkillEffectivenessItem(**item) for item in effectiveness_data]

        return SkillStatsResponse(
            total=total, by_layer=by_layer, by_status=by_status, effectiveness=effectiveness
        )
