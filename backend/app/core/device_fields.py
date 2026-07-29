"""设备级字段全局唯一校验（SN / 业务IP / 带外管理IP）。

与 IPAM 无关，仅做应用层软校验（字符串字面量）：
- 每个字段在其自身列内全局唯一（空值跳过）；
- 跨字段规则：同一设备允许「带外管理IP」==「业务IP地址」，但不同设备间二者不可相同。

设计为软校验，配合 DB 部分唯一索引（uq_device_sn / uq_device_oob_ip）兜底并发竞态。
"""

from __future__ import annotations

from app.core.exceptions import ConflictError
from app.repositories.device_repo import DeviceRepository


async def assert_device_fields_unique(
    device_repo: DeviceRepository,
    *,
    sn: str | None = None,
    ip_address: str | None = None,
    oob_ip: str | None = None,
    exclude_device_id: str | None = None,
) -> None:
    """校验设备字段唯一性（含跨字段放行规则）。

    Args:
        sn: 序列号，非空时全系统唯一。
        ip_address: 业务IP地址，列内唯一由 ``assert_ip_unique`` 保证（设备+接口），
            此处仅校验「与其他设备的带外管理IP 不重复」。
        oob_ip: 带外管理IP，列内唯一 + 跨字段（与其他设备的业务IP 不重复）。
        exclude_device_id: 更新设备时排除自身（使同一设备的 oob_ip==业务IP 放行）。

    Raises:
        ConflictError: 命中重复，HTTP 409。
    """
    # SN 号：设备表内全局唯一（忽略空值）。
    if sn:
        dev = await device_repo.get_by_sn_excluding(sn, exclude_device_id)
        if dev is not None:
            raise ConflictError(
                f"SN 号「{sn}」已被设备「{dev.name}」"
                f"(编号 {dev.device_code or '—'}) 占用，请勿重复"
            )

    # 业务IP地址：跨字段——不得与其他设备的「带外管理IP」相同（同一设备两者可相同）。
    if ip_address:
        other = await device_repo.get_by_oob_ip_excluding(ip_address, exclude_device_id)
        if other is not None:
            raise ConflictError(
                f"业务IP地址「{ip_address}」已被设备「{other.name}」的"
                f"「带外管理IP」占用，请勿重复（同一设备允许两者相同）"
            )

    # 带外管理IP：列内唯一 + 跨字段（与其他设备的业务IP 不重复）。
    if oob_ip:
        dev = await device_repo.get_by_oob_ip_excluding(oob_ip, exclude_device_id)
        if dev is not None:
            raise ConflictError(
                f"带外管理IP「{oob_ip}」已被设备「{dev.name}」"
                f"(编号 {dev.device_code or '—'}) 占用，请勿重复"
            )
        other = await device_repo.get_by_ip_excluding(oob_ip, exclude_device_id)
        if other is not None:
            raise ConflictError(
                f"带外管理IP「{oob_ip}」已被设备「{other.name}」的"
                f"「业务IP地址」占用，请勿重复（同一设备允许两者相同）"
            )
