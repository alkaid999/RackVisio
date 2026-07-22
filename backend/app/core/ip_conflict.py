"""全局 IP 字面量唯一校验。

设备级 IP（``devices.ip_address``）与接口级 IP（``device_interfaces.ip_address``）
之间不允许重复：运维在同一个系统里把同一个 IP 配到两台设备 / 两个端口，通常是
配置错误（IP 冲突）。本系统已删除 IPAM、不管理网段，故仅做**字符串字面量**去重，
不做语义网段冲突检测。

设计为应用层软校验（非数据库 UNIQUE 约束）：
- 兼容空值（大量设备 / 接口未配置 IP）；
- 兼容跨网段、历史数据中字面相同的合理重复，不被底层约束锁死；
- 可逆、易调整。
"""

from __future__ import annotations

import ipaddress

from app.core.exceptions import ConflictError, ValidationError
from app.repositories.device_repo import DeviceRepository
from app.repositories.interface_repo import InterfaceRepository


async def assert_ip_unique(
    device_repo: DeviceRepository,
    interface_repo: InterfaceRepository,
    ip: str | None,
    *,
    exclude_device_id: str | None = None,
    exclude_interface_id: str | None = None,
) -> None:
    """校验 IP 在全局（设备 + 接口）范围内字面量唯一。

    Args:
        ip: 待校验的 IP（可能带 CIDR，如 ``10.0.0.1/24``）。空值直接放行。
        exclude_device_id: 更新设备时排除自身。
        exclude_interface_id: 更新接口时排除自身。

    Raises:
        ConflictError: 命中重复，HTTP 409。
    """
    if not ip:
        return
    ip = ip.strip()
    if not ip:
        return

    dev = await device_repo.get_by_ip_excluding(ip, exclude_device_id)
    if dev is not None:
        raise ConflictError(
            f"IP 地址「{ip}」已被设备「{dev.name}」"
            f"(编号 {dev.device_code or '—'}) 占用，请勿重复"
        )

    ifc = await interface_repo.get_by_ip_excluding(ip, exclude_interface_id)
    if ifc is not None:
        owner = await device_repo.get(ifc.device_id)
        owner_name = owner.name if owner else "未知设备"
        raise ConflictError(
            f"IP 地址「{ip}」已被设备「{owner_name}」的接口「{ifc.name}」占用，请勿重复"
        )


def assert_ip_cidr(ip: str | None) -> None:
    """校验 IP 必须带 CIDR 子网掩码前缀（如 ``192.168.1.1/24``）。

    仅做格式校验，不做网段语义分析（本系统无 IPAM、不管理网段）：

    - 缺失前缀（如 ``192.168.1.1``）或前缀非法（如 ``192.168.1.1/33``）
      抛出 ``ValidationError``(422)，提示用户补全子网掩码前缀。
    - 空值直接放行（IP 可空）。

    设计取舍：校验放在应用层而非数据库约束，兼容历史遗留的无前缀数据，
    且错误提示对用户友好。
    """
    if not ip:
        return
    ip = ip.strip()
    if not ip:
        return
    # 必须先显式检查是否带「/」前缀：ipaddress.ip_interface 对缺前缀的裸地址
    # （如 192.168.1.1）会默认按 /32 处理而不报错，无法借此拦截缺前缀的录入。
    if "/" not in ip:
        raise ValidationError(
            f"IP 地址「{ip}」需包含子网掩码前缀（CIDR），例如 192.168.1.1/24"
        )
    try:
        # 带前缀时再校验地址与前缀合法性（如 192.168.1.1/33 会抛 ValueError）。
        ipaddress.ip_interface(ip)
    except ValueError:
        raise ValidationError(
            f"IP 地址「{ip}」格式非法，需为带子网掩码前缀的 CIDR，例如 192.168.1.1/24"
        )
