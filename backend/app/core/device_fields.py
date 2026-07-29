"""设备级字段全局唯一校验（SN / 业务IP / 带外管理IP）。

与 IPAM 无关，仅做应用层软校验（字符串字面量）：
- 每个字段在其自身列内全局唯一（空值跳过）；
- 业务IP地址 与 带外管理IP 是不同概念字段，二者值空间分离：
  * 同一设备内 业务IP 与 带外管理IP 必须不同（R1）；
  * 不同设备之间，业务IP 与 带外管理IP 也不可相同（值空间分离）。
- 带外管理IP 允许与本设备自身的「接口IP」相同：带外管理IP 物理上就配置在
  设备的某个网络接口上，因此「设备 带外管理IP == 该设备某接口 接口IP」是合理情形，
  不应报冲突；但不得与其他设备的接口IP 重复（全局 IP 冲突仍由 ``assert_ip_unique`` 保证）。

设计为软校验，配合 DB 部分唯一索引（uq_device_sn / uq_device_oob_ip）兜底并发竞态。
"""

from __future__ import annotations

from app.core.exceptions import ConflictError
from app.repositories.device_repo import DeviceRepository
from app.repositories.interface_repo import InterfaceRepository


async def assert_device_fields_unique(
    device_repo: DeviceRepository,
    interface_repo: InterfaceRepository,
    *,
    sn: str | None = None,
    ip_address: str | None = None,
    oob_ip: str | None = None,
    exclude_device_id: str | None = None,
    device_id: str | None = None,
) -> None:
    """校验设备字段唯一性（含跨字段放行规则）。

    Args:
        sn: 序列号，非空时全系统唯一。
        ip_address: 业务IP地址，列内唯一由 ``assert_ip_unique`` 保证（设备+接口），
            此处仅校验「与其他设备的带外管理IP 不重复」（值空间分离）。
        oob_ip: 带外管理IP，列内唯一 + 与业务IP 值空间分离 + 允许与本设备接口IP 相同。
        exclude_device_id: 更新设备时排除自身（列内唯一自比跳过）。
        device_id: 当前设备 id（更新时传入），用于：
            (1) 允许 oob_ip 等于本设备自身接口IP；
            (2) R1 取设备另一侧字段做「业务IP≠带外管理IP」比较（部分更新时补齐对侧值）。

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

    # 业务IP地址：跨字段——不得与其他设备的「带外管理IP」相同（值空间分离）。
    if ip_address:
        other = await device_repo.get_by_oob_ip_excluding(ip_address, exclude_device_id)
        if other is not None:
            raise ConflictError(
                f"业务IP地址「{ip_address}」已被设备「{other.name}」的"
                f"「带外管理IP」占用，请勿重复"
            )

    # 带外管理IP：列内唯一 + 跨字段（与其他设备的业务IP 不重复）+ 允许等于本设备接口IP。
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
                f"「业务IP地址」占用，请勿重复"
            )
        # 允许与本设备自身接口IP 相同（带外管理IP 即配置在该设备的某接口上）；
        # 不得与其他设备的接口IP 重复。
        ifc = await interface_repo.get_by_ip_other_device(oob_ip, device_id)
        if ifc is not None:
            owner = await device_repo.get(ifc.device_id)
            owner_name = owner.name if owner else "未知设备"
            raise ConflictError(
                f"带外管理IP「{oob_ip}」已被设备「{owner_name}」的"
                f"接口「{ifc.name}」占用，请勿重复"
            )

    # R1：同一设备内 带外管理IP 与 业务IP地址 必须不同（二者是不同概念字段）。
    # 部分更新（只提交一侧）时，从库中补齐另一侧字段后再比较。
    if ip_address is not None or oob_ip is not None:
        eff_business = ip_address if ip_address is not None else None
        eff_oob = oob_ip if oob_ip is not None else None
        if device_id is not None and (ip_address is None or oob_ip is None):
            existing = await device_repo.get(device_id)
            if existing is not None:
                if eff_business is None:
                    eff_business = existing.ip_address
                if eff_oob is None:
                    eff_oob = existing.oob_ip
        if eff_business and eff_oob and eff_business == eff_oob:
            raise ConflictError(
                f"带外管理IP 与 业务IP地址 不能相同（均为「{eff_business}」）。"
                f"二者是不同字段；带外管理IP 配置在接口时请填写该接口的实际 IP"
            )
