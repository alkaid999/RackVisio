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

from datetime import timedelta

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.security import hash_password
from app.models.consumable import ConsumableCategory, ConsumableType
from app.models.hardware import HardwareCategory, HardwareType
from app.models.user import User
from app.repositories.consumable_repo import (
    ConsumableCategoryRepository,
    ConsumableTypeRepository,
)
from app.repositories.hardware_repo import (
    HardwareCategoryRepository,
    HardwareTypeRepository,
)
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

    # —— devices：废弃「防火墙(firewall) / WAF(waf)」设备类型，合并入「安全设备(security)」 ——
    # 用户要求取消这两种独立类型；旧库若残留 firewall/waf 设备，统一改判为 security，
    # 避免其因 DeviceType 枚举已无对应值而在编辑/校验时 422，且保证设备类型仍合法。幂等。
    await session.execute(
        text("UPDATE devices SET device_type='security' WHERE device_type IN ('firewall','waf')")
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


async def _migrate_facility(session: AsyncSession) -> None:
    """设施支持迁移：devices 新增 is_asset 列并回填（方言无关）。

    旧库无此列时 ALTER 追加 BOOLEAN；存量设备（均为资产）统一回填为 True。
    SQLite 以 INTEGER(0/1) 存储、PostgreSQL 以 BOOLEAN 存储；回填用绑定参数传 Python
    bool（SQLAlchemy 据值推断为 Boolean 类型，PG 编译为 true、SQLite 编译为 1），避免硬编码
    整数 1 在 PostgreSQL 上触发 DatatypeMismatchError（与 _migrate_base 的方言无关原则一致）。
    """
    dcols = await _existing_columns(session, "devices")
    if "is_asset" not in dcols:
        await session.execute(text("ALTER TABLE devices ADD COLUMN is_asset BOOLEAN"))
    # 存量设备默认资产(True)；设施类型(patch/odf/other_facility)为新增枚举值，旧库无此类数据，无需改判。
    # 用绑定参数传 Python bool：SQLAlchemy 据值推断 Boolean 类型，PG 编译为 true / SQLite 编译为 1，
    # 避免硬编码整数 1 在 PostgreSQL 上触发 DatatypeMismatchError。
    await session.execute(
        text("UPDATE devices SET is_asset=:val WHERE is_asset IS NULL"),
        {"val": True},
    )
    await session.flush()


async def _migrate_power(session: AsyncSession) -> None:
    """功率字段迁移：racks 新增 design_power、devices 新增 rated_power（方言无关）。

    - ``design_power``：机柜额定功率上限（W），可空，无需回填（存量机柜留空）。
    - ``rated_power``：设备铭牌满载功率（W），可空，无需回填（存量设备留空）。
    列均允许 NULL，幂等 ALTER，SQLite / PostgreSQL 通吃（REAL 与 Float 等价）。
    """
    rcols = await _existing_columns(session, "racks")
    if "design_power" not in rcols:
        await session.execute(text("ALTER TABLE racks ADD COLUMN design_power REAL"))
    await session.flush()

    dcols = await _existing_columns(session, "devices")
    if "rated_power" not in dcols:
        await session.execute(text("ALTER TABLE devices ADD COLUMN rated_power REAL"))
    await session.flush()


async def _migrate_rack_status(session: AsyncSession) -> None:
    """机柜业务状态迁移：删除「空闲」状态，历史「空闲」机柜统一归并为「可用」。

    业务状态 ``status`` 为 VARCHAR 字符串列，无需加列；仅将存量 ``空闲`` 值
    UPDATE 为 ``可用``，使枚举取值收敛到当时的合法集合（可用/不可用/维护中/空调柜/电柜）。
    后续 ``0005_status_rename`` 进一步将「维护中」归并、「空调柜/电柜」重命名为现枚举
    （可用/不可用/制冷机柜/配电机柜）。新导入或新建的机柜不再可能出现「空闲」。
    """
    await session.execute(
        text("UPDATE racks SET status=:new WHERE status=:old"),
        {"old": "空闲", "new": "可用"},
    )
    await session.flush()


async def _migrate_status_rename(session: AsyncSession) -> None:
    """机柜业务状态重命名迁移（0005）：收敛历史枚举取值到新命名。

    - 已删除的「维护中」归并为「可用」（维护态不再作为独立枚举，避免存量机柜悬空）。
    - 「空调柜」重命名为「制冷机柜」。
    - 「电柜」重命名为「配电机柜」。
    ``status`` 为 VARCHAR 字符串列，无需加列；仅 UPDATE 存量取值以对齐新枚举
    （可用/不可用/制冷机柜/配电机柜）。幂等：重复执行对这些值无副作用。
    """
    await session.execute(
        text("UPDATE racks SET status=:new WHERE status=:old"),
        {"old": "维护中", "new": "可用"},
    )
    await session.execute(
        text("UPDATE racks SET status=:new WHERE status=:old"),
        {"old": "空调柜", "new": "制冷机柜"},
    )
    await session.execute(
        text("UPDATE racks SET status=:new WHERE status=:old"),
        {"old": "电柜", "new": "配电机柜"},
    )
    await session.flush()


async def _migrate_device_oob_ip(session: AsyncSession) -> None:
    """设备新增带外管理IP(oob_ip)列，并为 SN / 带外管理IP 建立部分唯一索引。

    - ``oob_ip``：设备级带外管理IP，可空，与业务IP(ip_address)区分。业务IP 与 带外管理IP
      是不同字段，同一设备内二者必须不同（R1）；跨设备间二者值空间也分离。带外管理IP 允许
      与本设备自身接口IP 相同（OOB IP 即配置在该设备某接口上），但不得与其他设备的接口IP
      重复；上述跨字段规则由应用层 ``assert_device_fields_unique`` / ``assert_ip_unique`` 保证。
    - ``sn``：需求要求全系统唯一；建唯一索引前先清理同表内重复 SN（保留一条，其余置 NULL）。
    - ``oob_ip``：同理清理重复后建部分唯一索引（仅非空生效）。
    列均允许 NULL，幂等 ALTER，SQLite / PostgreSQL 通吃。
    """
    dcols = await _existing_columns(session, "devices")
    if "oob_ip" not in dcols:
        await session.execute(text("ALTER TABLE devices ADD COLUMN oob_ip VARCHAR(64)"))
    await session.flush()

    # SN 去重（保留首条，其余置 NULL），避免唯一索引创建因重复行失败。
    sn_dups = (
        await session.execute(
            text(
                "SELECT sn, COUNT(*) c FROM devices "
                "WHERE sn IS NOT NULL AND sn <> '' GROUP BY sn HAVING COUNT(*) > 1"
            )
        )
    ).fetchall()
    for sn_val, _ in sn_dups:
        ids = (
            await session.execute(
                text("SELECT id FROM devices WHERE sn=:sn ORDER BY id"),
                {"sn": sn_val},
            )
        ).fetchall()
        for rid in ids[1:]:
            await session.execute(
                text("UPDATE devices SET sn=NULL WHERE id=:id"), {"id": rid[0]}
            )
    # 带外管理IP 去重（历史库一般无，防御性处理）。
    oob_dups = (
        await session.execute(
            text(
                "SELECT oob_ip, COUNT(*) c FROM devices "
                "WHERE oob_ip IS NOT NULL AND oob_ip <> '' GROUP BY oob_ip HAVING COUNT(*) > 1"
            )
        )
    ).fetchall()
    for oob_val, _ in oob_dups:
        ids = (
            await session.execute(
                text("SELECT id FROM devices WHERE oob_ip=:ip ORDER BY id"),
                {"ip": oob_val},
            )
        ).fetchall()
        for rid in ids[1:]:
            await session.execute(
                text("UPDATE devices SET oob_ip=NULL WHERE id=:id"), {"id": rid[0]}
            )
    await session.flush()

    # 部分唯一索引（仅非空生效），作为并发写入最后防线。
    await session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_device_sn "
            "ON devices(sn) WHERE sn IS NOT NULL AND sn <> ''"
        )
    )
    await session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_device_oob_ip "
            "ON devices(oob_ip) WHERE oob_ip IS NOT NULL AND oob_ip <> ''"
        )
    )
    await session.flush()


async def _migrate_hot_indexes(session: AsyncSession) -> None:
    """热点查询索引迁移：为高频过滤/聚合列补全 B-Tree 索引（方言无关）。

    这些列被统计聚合与列表过滤频繁使用（devices.status / is_asset /
    device_type、racks.status、rooms.status、mount_records.record_status），
    建索引可显著加速统计页与机柜/设备列表查询。纯 ``CREATE INDEX IF NOT EXISTS``
    （SQLite / PostgreSQL 通吃），重复执行幂等；不与模型 ``index=True`` 重复，
    避免全新库在 create_all 后再建同名索引造成冗余。
    """
    index_ddls = [
        "CREATE INDEX IF NOT EXISTS ix_mount_records_record_status "
        "ON mount_records(record_status)",
        "CREATE INDEX IF NOT EXISTS ix_devices_status ON devices(status)",
        "CREATE INDEX IF NOT EXISTS ix_devices_device_type ON devices(device_type)",
        "CREATE INDEX IF NOT EXISTS ix_devices_is_asset ON devices(is_asset)",
        "CREATE INDEX IF NOT EXISTS ix_racks_status ON racks(status)",
        "CREATE INDEX IF NOT EXISTS ix_rooms_status ON rooms(status)",
    ]
    for ddl in index_ddls:
        await session.execute(text(ddl))
    await session.flush()


async def _migrate_drop_audit_logs(session: AsyncSession) -> None:
    """删除旧审计表（0008）：审计功能重构为原生请求级日志。

    操作日志改由 HTTP 中间件写 ``operation_logs``、登录日志由认证端点写
    ``login_logs``（两表均由 create_all 自动创建）。旧 ``audit_logs`` 表
    及其 ORM 事件审计（audit_auto/audit_meta）已整体移除，历史数据一并清理。
    ``DROP TABLE IF EXISTS`` 幂等，SQLite / PostgreSQL 通吃。
    """
    await session.execute(text("DROP TABLE IF EXISTS audit_logs"))
    await session.flush()


async def _migrate_operation_log_detail(session: AsyncSession) -> None:
    """操作日志详情列（0009）：operation_logs 新增 detail（TEXT，可空）。

    存储中间件抓取到的请求体 JSON 与已解析的外键可读名称，使操作日志能回答
    「改了什么 / 上架到哪 / 链路两端 / 新增了什么耗材」等具体问题。方言无关
    ALTER，SQLite / PostgreSQL 通吃；列可空，旧数据保持 NULL，幂等。
    """
    ocols = await _existing_columns(session, "operation_logs")
    if "detail" not in ocols:
        await session.execute(text("ALTER TABLE operation_logs ADD COLUMN detail TEXT"))
    await session.flush()


async def _migrate_operation_log_resource(session: AsyncSession) -> None:
    """操作日志资源类型列（0010）：operation_logs 新增 resource（VARCHAR(32)，可空、索引）。

    归一化资源类型键（room/rack/device/interface/link/account/consumable/
    mount-record），由中间件落库，支撑「按资源类型筛选」操作日志。方言无关
    ALTER，SQLite / PostgreSQL 通吃；列可空，旧数据保持 NULL（旧日志仍可经
    「全部」查看，只是不参与具体资源类型过滤），幂等。
    """
    ocols = await _existing_columns(session, "operation_logs")
    if "resource" not in ocols:
        await session.execute(
            text("ALTER TABLE operation_logs ADD COLUMN resource VARCHAR(32)")
        )
    await session.flush()


async def _migrate_operation_log_action_target(session: AsyncSession) -> None:
    """操作日志动作 / 对象列（0011）：operation_logs 新增 action 与 target。

    - action（VARCHAR(16)，可空 + 索引）：操作动作归一化键 create/update/delete，
      让前端「操作」列只展示新增 / 更新 / 删除三态（PUT/PATCH 合并为更新）。
    - target（VARCHAR(255)，可空 + 索引）：操作对象可读名称（设备名 / 机柜名 /
      链路两端等），支撑新增「操作对象」列与按名称关键字搜索。
    方言无关 ALTER，SQLite / PostgreSQL 通吃；列可空，旧数据保持 NULL，幂等。
    """
    ocols = await _existing_columns(session, "operation_logs")
    if "action" not in ocols:
        await session.execute(
            text("ALTER TABLE operation_logs ADD COLUMN action VARCHAR(16)")
        )
    if "target" not in ocols:
        await session.execute(
            text("ALTER TABLE operation_logs ADD COLUMN target VARCHAR(255)")
        )
    await session.flush()


async def _migrate_user_must_change_password(session: AsyncSession) -> None:
    """强制改密标记（0012）：users 新增 must_change_password 列（方言无关）。

    初始管理员（seed 创建）置 True，首次登录后强制修改密码（S-02）；
    存量用户均为历史账号，统一回填 False，行为不变。
    ALTER ADD BOOLEAN（可空）→ UPDATE 用绑定参数传 Python bool 回填：
    SQLAlchemy 据值推断 Boolean 类型，PG 编译为 true / SQLite 编译为 1，
    避免硬编码整数在 PostgreSQL 上触发 DatatypeMismatchError（同 _migrate_facility）。
    """
    ucols = await _existing_columns(session, "users")
    if "must_change_password" not in ucols:
        await session.execute(
            text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN")
        )
    await session.execute(
        text("UPDATE users SET must_change_password=:val WHERE must_change_password IS NULL"),
        {"val": False},
    )
    await session.flush()


async def _migrate_user_created_at_datetime(session: AsyncSession) -> None:
    """users.created_at 类型统一（0013，R-01）：String → DateTime。

    对齐 login_logs / operation_logs 的 DateTime（naive UTC）语义：
    - PostgreSQL：``ALTER COLUMN TYPE TIMESTAMP USING created_at::timestamp``
      转换存量文本（列已是时间类型时跳过，幂等）。
    - SQLite：无 DDL 需要——SQLite 的 DATETIME 列本就以 ISO 文本存储，
      SQLAlchemy 的 DateTime 处理器可直接解析存量 "YYYY-MM-DD HH:MM:SS" 文本。
    """
    conn = await session.connection()
    if conn.dialect.name != "postgresql":
        return  # SQLite 直接跳过（模型列声明已改为 DateTime，读取自动解析）

    def _col_type(sync_conn):
        cols = {c["name"]: c["type"] for c in inspect(sync_conn).get_columns("users")}
        return cols.get("created_at")

    current = await conn.run_sync(_col_type)
    type_name = getattr(current, "name", None) or str(current).upper()
    if type_name in ("TIMESTAMP", "DATETIME"):
        return  # 已是时间类型，跳过（幂等）
    await session.execute(
        text(
            "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP "
            "USING created_at::timestamp"
        )
    )
    await session.flush()


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
            # 初始管理员首次登录必须改密（S-02）：无论 INITIAL_ADMIN_PASSWORD 强弱，
            # 一律强制管理员登录后立即替换为本人掌握的密码。
            must_change_password=True,
        )
        await session.flush()
        # lifespan 以 `async with session` 块退出即关闭会话，未提交事务会被回滚；
        # 必须显式 commit，否则 admin 账号不会写入数据库，登录恒报密码错误。
        await session.commit()

    # —— 默认耗材类型与分类（幂等，仅当库内无任何类型时创建）——
    # 让「创建耗材」下拉恒有可选项，避免用户因缺类型而提交失败（需求#1）。
    await seed_consumable_types(session)

    # —— 默认硬件类型与分类（幂等，仅当库内无任何类型时创建）——
    # 预置主板/CPU/内存/硬盘/阵列卡/网卡/电源 7 类（需求#3），让「创建硬件」下拉恒有可选项。
    await seed_hardware_types(session)





async def seed_consumable_types(session: AsyncSession) -> None:
    """种子默认耗材类型与分类（幂等）。

    仅当 ``consumable_types`` 表为空时创建，绝不覆盖用户已有数据。
    交付/生产库初始即带这些默认类型，确保用户创建耗材时类型/分类下拉恒有可选项，
    不会因「无类型」而提交失败（需求#1）。

    顺序：列表按 ``created_at DESC`` 排序（新增置顶，需求#3），故此处在倒序创建之外，
    显式指定 ``created_at`` 以保证默认类型的展示顺序确定：
    类型从上往下为 光纤 → 网线 → 光模块 → 电源线；每类下分类亦按定义顺序从上往下。
    """
    type_repo = ConsumableTypeRepository(session)
    if await type_repo.list():
        return  # 已有类型，跳过（幂等，不覆盖用户数据）

    cat_repo = ConsumableCategoryRepository(session)

    # (类型名, 说明, [分类名...])，按展示顺序（索引越小越靠上）。
    type_defs = [
        ("光纤", "光通信纤芯介质，用于长距离 / 高带宽传输", ["单模光纤", "多模光纤", "皮线光缆"]),
        ("网线", "铜缆双绞线，用于短距离以太网接入", ["超五类网线", "六类网线", "超六类网线"]),
        ("光模块", "光电转换模块，插于设备 SFP 插槽", ["1G SFP", "10G SFP+", "25G SFP28"]),
        ("电源线", "设备供电线缆，按制式区分", ["国标电源线", "美标电源线", "欧标电源线"]),
    ]
    base = utcnow()
    n_types = len(type_defs)
    for i, (tname, tdesc, cats) in enumerate(type_defs):
        # 展示序靠前的类型 → created_at 更晚（DESC 置顶）+ sort_order 更小（升序靠前，手动排序持久化）。
        t_created = base + timedelta(seconds=(n_types - 1 - i) * 10)
        t_obj = ConsumableType(
            name=tname, description=tdesc, created_at=t_created, updated_at=t_created,
            sort_order=i,
        )
        session.add(t_obj)
        await session.flush()  # 拿到 t_obj.id 供分类外键使用
        n_cats = len(cats)
        for j, cname in enumerate(cats):
            # 同类下首个分类 → created_at 更晚（DESC 置顶）+ sort_order 更小。
            c_created = t_created + timedelta(seconds=(n_cats - 1 - j) * 1)
            session.add(
                ConsumableCategory(
                    type_id=t_obj.id,
                    name=cname,
                    created_at=c_created,
                    updated_at=c_created,
                    sort_order=j,
                )
            )
        await session.flush()
    # 种子数据须显式提交（同 seed_data：async with session 块退出即关闭，未提交被回滚）。
    await session.commit()


async def seed_hardware_types(session: AsyncSession) -> None:
    """种子默认硬件类型与分类（幂等）。

    仅当 ``hardware_types`` 表为空时创建，绝不覆盖用户已有数据。
    预置 主板/CPU/内存/硬盘/阵列卡/网卡/电源 7 类（需求#3），确保用户创建硬件时
    类型/分类下拉恒有可选项（硬件管理入口与耗材一致）。

    顺序：列表按 ``created_at DESC`` 排序（新增置顶），显式指定 ``created_at``
    以保证默认类型的展示顺序确定：主板 → CPU → 内存 → 硬盘 → 阵列卡 → 网卡 → 电源。
    """
    type_repo = HardwareTypeRepository(session)
    if await type_repo.list():
        return  # 已有类型，跳过（幂等，不覆盖用户数据）

    cat_repo = HardwareCategoryRepository(session)

    # (类型名, 说明, [分类名...])，按展示顺序（索引越小越靠上）。
    type_defs = [
        ("主板", "服务器/PC 主板，决定整机平台与扩展能力", ["标准 ATX", "定制服务器板"]),
        ("CPU", "中央处理器", ["Intel Xeon", "Intel Core", "AMD EPYC", "海光"]),
        ("内存", "运行内存条", ["DDR4 ECC", "DDR4 非ECC", "DDR5 ECC", "DDR5 非ECC"]),
        ("硬盘", "存储介质（机械盘 / 固态盘 / NVMe）", ["SATA SSD", "NVMe SSD", "SAS 机械盘", "SATA 机械盘"]),
        ("阵列卡", "RAID 阵列卡 / HBA 卡", ["RAID 卡", "HBA 卡"]),
        ("网卡", "以太网适配器（含光口/电口）", ["1G 电口", "10G 光口", "25G 光口", "40G 光口"]),
        ("电源", "服务器电源模块（冗余）", ["550W", "800W", "1200W", "2000W"]),
    ]
    base = utcnow()
    n_types = len(type_defs)
    for i, (tname, tdesc, cats) in enumerate(type_defs):
        # 展示序靠前的类型 → created_at 更晚（DESC 置顶）+ sort_order 更小（升序靠前）。
        t_created = base + timedelta(seconds=(n_types - 1 - i) * 10)
        t_obj = HardwareType(
            name=tname, description=tdesc, created_at=t_created, updated_at=t_created,
            sort_order=i,
        )
        session.add(t_obj)
        await session.flush()  # 拿到 t_obj.id 供分类外键使用
        n_cats = len(cats)
        for j, cname in enumerate(cats):
            # 同类下首个分类 → created_at 更晚（DESC 置顶）+ sort_order 更小。
            c_created = t_created + timedelta(seconds=(n_cats - 1 - j) * 1)
            session.add(
                HardwareCategory(
                    type_id=t_obj.id,
                    name=cname,
                    created_at=c_created,
                    updated_at=c_created,
                    sort_order=j,
                )
            )
        await session.flush()
    # 种子数据须显式提交（同 seed_data：async with session 块退出即关闭，未提交被回滚）。
    await session.commit()


async def _migrate_type_sort_order(session: AsyncSession) -> None:
    """类型/分类手动排序列（0014，需求：类型管理页上移/下移持久化）。

    为 consumable_types / consumable_categories / hardware_types / hardware_categories
    四张表追加 ``sort_order``（Integer，越小越靠前）。存量数据统一归 0，
    再按现有展示顺序（created_at DESC）回填递增序号，保证迁移后顺序不变。
    """
    for table in ("consumable_types", "consumable_categories", "hardware_types", "hardware_categories"):
        cols = await _existing_columns(session, table)
        if "sort_order" not in cols:
            await session.execute(text(f"ALTER TABLE {table} ADD COLUMN sort_order INTEGER DEFAULT 0"))
    # 回填：按创建时间倒序（与现有展示一致）赋 0..N，使存量顺序平滑迁移。
    for table in ("consumable_types", "hardware_types"):
        rows = (
            await session.execute(
                text(f"SELECT id FROM {table} ORDER BY created_at DESC")
            )
        ).all()
        for i, (rid,) in enumerate(rows):
            await session.execute(
                text(f"UPDATE {table} SET sort_order = :o WHERE id = :i"),
                {"o": i, "i": rid},
            )
    # 分类按类型分组回填（同类型内 created_at DESC 赋 0..N）。
    for table in ("consumable_categories", "hardware_categories"):
        type_rows = (
            await session.execute(text(f"SELECT DISTINCT type_id FROM {table}"))
        ).all()
        for (tid,) in type_rows:
            cat_rows = (
                await session.execute(
                    text(f"SELECT id FROM {table} WHERE type_id = :t ORDER BY created_at DESC"),
                    {"t": tid},
                )
            ).all()
            for i, (rid,) in enumerate(cat_rows):
                await session.execute(
                    text(f"UPDATE {table} SET sort_order = :o WHERE id = :i"),
                    {"o": i, "i": rid},
                )
    await session.flush()


# 版本化迁移注册表：未来新增迁移追加于此即可，已应用版本自动跳过（见 migrate()）。
# 每项：(版本号, 迁移协程)。版本号建议用 4 位零填充递增（0001, 0002, ...）。
MIGRATIONS: list = [
    ("0001_base", _migrate_base),
    ("0002_facility", _migrate_facility),
    ("0003_power", _migrate_power),
    ("0004_rack_status", _migrate_rack_status),
    ("0005_status_rename", _migrate_status_rename),
    ("0006_device_oob_ip", _migrate_device_oob_ip),
    ("0007_hot_indexes", _migrate_hot_indexes),
    ("0008_drop_audit_logs", _migrate_drop_audit_logs),
    ("0009_op_log_detail", _migrate_operation_log_detail),
    ("0010_op_log_resource", _migrate_operation_log_resource),
    ("0011_op_log_action_target", _migrate_operation_log_action_target),
    ("0012_user_must_change_password", _migrate_user_must_change_password),
    ("0013_user_created_at_datetime", _migrate_user_created_at_datetime),
    ("0014_type_sort_order", _migrate_type_sort_order),
]
