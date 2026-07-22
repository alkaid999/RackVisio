"""用户账号仓储（SQLAlchemy async）。"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """用户查询与持久化。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_username(self, username: str) -> User | None:
        res = await self.session.execute(select(User).where(User.username == username))
        return res.scalar_one_or_none()

    async def get(self, user_id: str) -> User | None:
        res = await self.session.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    async def list(
        self, *, keyword: str | None = None, page: int = 1, size: int = 20
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(User.username.like(like), User.display_name.like(like)))
        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        total = total or 0
        rows = (
            await self.session.execute(
                stmt.order_by(User.created_at.desc(), User.username.asc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).scalars().all()
        return list(rows), total

    async def create(
        self,
        *,
        username: str,
        password_hash: str,
        salt: str,
        role: str,
        display_name: str | None,
        permissions: dict | None = None,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            salt=salt,
            role=role,
            display_name=display_name,
            permissions=permissions,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def count_admins(self) -> int:
        return await self.session.scalar(
            select(func.count()).where(User.role == "admin", User.disabled.is_(False))
        ) or 0

    async def count_all(self) -> int:
        """账号总数（含禁用，用于仪表盘规模统计）。"""
        return await self.session.scalar(select(func.count()).select_from(User)) or 0

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.flush()
