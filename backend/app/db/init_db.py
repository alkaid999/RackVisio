"""启动建表与种子数据。

- ``init_models``：创建全部表（本期省略 Alembic，见架构文档 §5 S2）。
- ``seed_data``：仅创建默认管理员账号，确保可登录。不预置任何演示业务数据（机房/机柜/设备/耗材等），
  交付/生产数据库初始为空。幂等。

设计说明（设备 ↔ 上架记录解耦）：
- 设备表 (devices) 仅含固有属性，无位置字段；
- 设备当前位置由 mount_records 中状态为「有效」的记录推导；
- 上架演示数据通过写入 mount_records 体现，并同步设备状态为「已上架」。

接口与链路语义：
- 接口新增默认 ``down``（未接线）；建链事务（LinkService）在同一事务里把本端 +
  对端接口置为 ``up``，演示数据通过 LinkService.create_link 建立，状态自动一致。
"""

from __future__ import annotations

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository


async def _existing_columns(session: AsyncSession, table_name: str) -> set[str]:
    """方言无关地获取表的列名集合（兼容 SQLite 的 PRAGMA 与 PostgreSQL 的 information_schema）。

    迁移脚本原先用 ``PRAGMA table_info(<t>)`` 探测列存在性，仅在 SQLite 生效；
    PostgreSQL 无 PRAGMA 语法会直接报 ProgrammingError，导致 lifespan 启动失败。
    改用 SQLAlchemy inspector 反射，两种库通吃。
    """
    conn = await session.connection()

    def _cols(sync_conn):
        return {c["name"] for c in inspect(sync_conn).get_columns(table_name)}

    return await conn.run_sync(_cols)


async def migrate(session: AsyncSession) -> None:
    """轻量 online 迁移：按版本执行，已应用版本跳过。

    设计目标（审查报告#346）：避免每次启动无条件重跑全部 DDL（旧库列已存在时
    ALTER 需 PRAGMA 探活、唯一索引重建竞争），并为未来迁移提供可扩展、可追踪的
    版本门控。多实例同时启动仅首个实例会执行某版本，其余读到已记录版本后跳过，
    降低 SQLITE_BUSY 概率。
    """
    # 版本表（记录已应用的迁移版本），幂等建表。
    await session.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
    )
    await session.flush()
    applied = {
        row[0]
        for row in (
            await session.execute(text("SELECT version FROM schema_migrations"))
        ).fetchall()
    }
    for version, fn in MIGRATIONS:
        if version in applied:
            continue
        await fn(session)
        await session.commit()
        await session.execute(
            text(
                "INSERT INTO schema_migrations(version, applied_at) VALUES(:v, :t)"
            ),
            {"v": version, "t": utcnow().isoformat()},
        )
        await session.commit()


async def _migrate_base(session: AsyncSession) -> None:
    """基础迁移：为已存在的 racks / device_interfaces 表补齐列并回填。

    ``create_all`` 只会为新表建列、不会给旧表追加列，故在此用 ALTER 补齐；
    同时对坐标缺失的机柜按「同列编号归一行、行内按编号排序」规则回填，
    与 ``RackService._assign_grid`` 的默认排列保持一致；并为缺 ``interface_no``
    的接口按名称顺序回填 1 基序号（兼容旧数据）。
    """
    # —— racks 网格列 ——
    rcols = await _existing_columns(session, "racks")
    for col in ("grid_row", "grid_col"):
        if col not in rcols:
            await session.execute(text(f"ALTER TABLE racks ADD COLUMN {col} INTEGER"))

    # —— device_interfaces.interface_no ——
    icols = await _existing_columns(session, "device_interfaces")
    if "interface_no" not in icols:
        await session.execute(
            text("ALTER TABLE device_interfaces ADD COLUMN interface_no INTEGER")
        )
    # 端口级 IP 地址（可空，无需回填）。区别于设备级 ip_address，属接口自有属性。
    if "ip_address" not in icols:
        await session.execute(
            text("ALTER TABLE device_interfaces ADD COLUMN ip_address VARCHAR(45)")
        )

    await session.flush()

    # 机柜坐标回填
    rows = (
        await session.execute(
            text(
                "SELECT id, room_id, column_code, code FROM racks "
                "WHERE grid_row IS NULL OR grid_col IS NULL"
            )
        )
    ).fetchall()
    if rows:
        by_room: dict[str, list] = {}
        for r in rows:
            by_room.setdefault(r[1], []).append(r)
        for _room_id, racks in by_room.items():
            col_codes = sorted({r[2] for r in racks})
            col_to_row = {c: i for i, c in enumerate(col_codes)}
            for c in col_codes:
                members = sorted([r for r in racks if r[2] == c], key=lambda x: x[3])
                for j, m in enumerate(members):
                    await session.execute(
                        text(
                            "UPDATE racks SET grid_row=:gr, grid_col=:gc WHERE id=:id"
                        ),
                        {"gr": col_to_row[c], "gc": j, "id": m[0]},
                    )

    # 接口 interface_no 规整为设备内唯一（1 基）：处理 NULL/0 及同设备内重复值，
    # 为后续 (device_id, interface_no) 唯一约束打底。
    ifaces = (
        await session.execute(
            text(
                "SELECT id, device_id FROM device_interfaces "
                "ORDER BY device_id, (interface_no IS NULL OR interface_no = 0), "
                "interface_no, name"
            )
        )
    ).fetchall()
    by_dev: dict[str, list] = {}
    for r in ifaces:
        by_dev.setdefault(r[1], []).append(r[0])
    for _dev_id, ids in by_dev.items():
        for idx, iid in enumerate(ids, start=1):
            await session.execute(
                text("UPDATE device_interfaces SET interface_no=:no WHERE id=:id"),
                {"no": idx, "id": iid},
            )
    await session.flush()
    # 建立设备内唯一索引（幂等）。
    await session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_device_interface_no "
            "ON device_interfaces(device_id, interface_no)"
        )
    )

    # —— devices 列信息（用于幂等新增列判断）——
    dcols = await _existing_columns(session, "devices")
    # 注：business / location / department / tags 等历史列已由一次性迁移脚本
    # backend/migrate_drop_device_fields.py 删除，此处不再维护其新增逻辑。
    await session.flush()

    # —— devices：新增「开关机状态(power_status)」列（仅对在架设备有意义）——
    if "power_status" not in dcols:
        await session.execute(
            text("ALTER TABLE devices ADD COLUMN power_status VARCHAR(8)")
        )
        # 旧库无此列，已存在设备统一回填为「开机」（历史数据默认运行态）。
        await session.execute(
            text("UPDATE devices SET power_status='开机' WHERE power_status IS NULL")
        )
    await session.flush()

    # —— devices：废弃「存储(storage)」设备类型 ——
    # 前端已移除「存储」选项；旧库若残留 storage 设备，统一改判为「其他(other)」，
    # 避免其因 DeviceType 枚举已无 STORAGE 而在编辑时 422，且保证设备类型仍合法。幂等。
    await session.execute(
        text("UPDATE devices SET device_type='other' WHERE device_type='storage'")
    )
    await session.flush()

    # —— device_links：废弃「链路类型(link_type)」，替换为「备注(remark)」 ——
    # 旧库可能仍含 link_type 列且缺 remark 列；新库（create_all 已建 remark）则跳过。
    lcols = await _existing_columns(session, "device_links")
    if "remark" not in lcols:
        await session.execute(
            text("ALTER TABLE device_links ADD COLUMN remark VARCHAR(255)")
        )
    if "link_type" in lcols:
        # SQLite 3.35+ 支持 DROP COLUMN；本环境 Python 3.10 自带 SQLite 满足。
        await session.execute(text("ALTER TABLE device_links DROP COLUMN link_type"))
    # —— device_links：废弃「链路状态(status)」列 ——
    # 链路恒为可用状态（一接口一链路，由唯一约束 + 建链/删链事务保证），不再需要
    # 独立的 active/inactive 状态。直接 DROP，避免遗留「停用」链路长期占用接口、
    # 导致无法在同一接口上重新建链的问题。
    if "status" in lcols:
        await session.execute(text("ALTER TABLE device_links DROP COLUMN status"))
    await session.flush()

    # —— device_links：新增「连接器类型(connector_type)」，并迁移旧介质取值 ——
    if "connector_type" not in lcols:
        await session.execute(
            text("ALTER TABLE device_links ADD COLUMN connector_type VARCHAR(16)")
        )
    # 旧库可能仍含历史介质取值 copper/fiber；统一转换为细分介质 tp/mmf（幂等）。
    await session.execute(
        text("UPDATE device_links SET medium='tp' WHERE medium='copper'")
    )
    await session.execute(
        text("UPDATE device_links SET medium='mmf' WHERE medium='fiber'")
    )
    await session.flush()

    # —— device_links：连接器类型回收 ——
    # 双绞线(tp)的连接器类型记录的是「线缆类别」，合法值为 cat5/cat5e/cat6/cat6a。
    # Round15 曾错误地把双绞线连接器统一收敛为 rj45（rj45 现已不再是合法连接器值），
    # 需将其回退为 cat5e（千兆双绞线，最常见的网线类别）。光纤连接器(lc-*/sc-*/st-*)
    # 与旧值 cat5e/cat6/cat6a 均保持不变。此转换幂等，仅影响历史 tp 链路。
    await session.execute(
        text(
            "UPDATE device_links SET connector_type='cat5e' "
            "WHERE connector_type='rj45'"
        )
    )
    await session.flush()

    # —— device_interfaces：迁移旧接口类型 electrical/optical ——
    # electrical → rj45（电口），optical → sfp（光模块插槽）；幂等。
    await session.execute(
        text("UPDATE device_interfaces SET interface_type='rj45' WHERE interface_type='electrical'")
    )
    await session.execute(
        text("UPDATE device_interfaces SET interface_type='sfp' WHERE interface_type='optical'")
    )
    await session.flush()

    # —— users：新增「细粒度权限映射(permissions)」列 ——
    # 普通用户逐用户独立配置查看/编辑权限；管理员恒为全权限，该列保持 NULL。
    # 旧库已有普通用户无此列时统一回填为「全模块只读」（view=True, edit=False）。
    ucols = await _existing_columns(session, "users")
    if "permissions" not in ucols:
        await session.execute(
            text("ALTER TABLE users ADD COLUMN permissions TEXT")
        )
        # SQLite JSON 列用 TEXT 存储；回填存量普通用户为只读映射。
        from app.core.rbac import default_permissions

        default_map = default_permissions()
        existing = (
            await session.execute(select(User).where(User.role != "admin"))
        ).scalars().all()
        for u in existing:
            # 仅当当前列为 NULL 时回填（幂等）。
            if u.permissions is None:
                u.permissions = default_map
    await session.flush()

    # —— IP 字面量唯一性：DB 兜底约束（P1：缓解应用层 TOCTOU 竞态）——
    # 建唯一索引前先清理同表内重复 IP（保留一条，其余置 NULL），避免索引创建因
    # 已有重复行而失败导致启动崩溃。跨表（设备↔接口）唯一仍由应用层 assert_ip_unique 保证。
    for tbl in ("devices", "device_interfaces"):
        dups = (
            await session.execute(
                text(
                    f"SELECT ip_address, COUNT(*) c FROM {tbl} "
                    f"WHERE ip_address IS NOT NULL GROUP BY ip_address HAVING COUNT(*) > 1"
                )
            )
        ).fetchall()
        for ip, _ in dups:
            ids = (
                await session.execute(
                    text(f"SELECT id FROM {tbl} WHERE ip_address=:ip ORDER BY id"),
                    {"ip": ip},
                )
            ).fetchall()
            for rid in ids[1:]:
                await session.execute(
                    text(f"UPDATE {tbl} SET ip_address=NULL WHERE id=:id"),
                    {"id": rid[0]},
                )
    await session.flush()
    # 部分唯一索引：仅对非空 IP 生效（SQLite 允许多个 NULL），作为并发写入的最后防线。
    await session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_device_ip "
            "ON devices(ip_address) WHERE ip_address IS NOT NULL"
        )
    )
    await session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_interface_ip "
            "ON device_interfaces(ip_address) WHERE ip_address IS NOT NULL"
        )
    )
    await session.flush()

    await session.commit()


async def seed_data(session: AsyncSession) -> None:
    """初始化种子数据（幂等）。

    仅创建默认管理员账号（确保任何已初始化库都有可登录的管理员）。
    不预置任何演示业务数据，交付/生产数据库初始为空。
    """
    # —— 默认管理员账号（独立于演示数据，确保任何已初始化库都有可登录的管理员）——
    # 仅在 users 表为空时创建；用户名 admin，密码由 INITIAL_ADMIN_PASSWORD 决定（默认 admin123）。
    user_repo = UserRepository(session)
    existing_admin = await session.execute(select(User).limit(1))
    if existing_admin.scalar_one_or_none() is None:
        pw_hash, salt = hash_password(settings.INITIAL_ADMIN_PASSWORD)
        await user_repo.create(
            username="admin",
            password_hash=pw_hash,
            salt=salt,
            role="admin",
            display_name="系统管理员",
        )
        await session.flush()





# 版本化迁移注册表：未来新增迁移追加于此即可，已应用版本自动跳过（见 migrate()）。
# 每项：(版本号, 迁移协程)。版本号建议用 4 位零填充递增（0001, 0002, ...）。
MIGRATIONS: list = [
    ("0001_base", _migrate_base),
]
