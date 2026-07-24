"""集中定义的枚举（SQLite / PostgreSQL 通用）。

所有枚举值均为字符串；数据库模型中以 ``String`` 存储枚举值，应用层用 Python ``Enum``
进行校验，不映射到 PostgreSQL 原生 ENUM 类型（详见架构文档 §1.2）。
前端 ``frontend/src/utils/constants.js`` 需与本文件取值保持一致。
"""

from __future__ import annotations

from enum import Enum


class RoomStatus(str, Enum):
    """机房状态（软删除用 disabled）。"""

    ACTIVE = "active"
    DISABLED = "disabled"


class RackBizStatus(str, Enum):
    """机柜业务状态（用户维护，可扩展）。

    面向政企自建机房 / IDC 租用场景：可用、空闲、维护中、空调柜、电柜。
    新增状态只需在此追加枚举值，并同步前端 ``RACK_STATUS_OPTIONS`` 即可（枚举即配置）。
    """

    AVAILABLE = "可用"
    IDLE = "空闲"
    MAINTENANCE = "维护中"
    AC = "空调柜"
    POWER = "电柜"


class RackStatus(str, Enum):
    """机柜容量状态（后端按 used_u / total_u 自动计算，仅用于大屏利用率分布）。"""

    EMPTY = "empty"
    PARTIAL = "partial"
    FULL = "full"


class DeviceType(str, Enum):
    """设备类型（运维资产分类）。

    覆盖服务器 / 网络设备 / 安全设备等常见 IDC 资产。新增类型只需在此追加
    枚举值，并同步前端 ``DEVICE_TYPE_OPTIONS`` 即可（枚举即配置）。

    其中 ``PATCH`` / ``ODF`` / ``OTHER_FACILITY`` 为「基础设施（非资产）」：占用机柜 U 位，
    但不计入资产统计、不建物理接口、不显设备编码。其 ``is_asset`` 由后端在创建时
    强制为 ``False``（见 ``device_service.create_device``），前端通过 ``/meta`` 的
    ``facility_types`` 识别并差异化渲染。``OTHER`` 为普通资产类型「其他设备」，与
    基础设施区分。
    """

    SERVER = "server"
    SWITCH = "switch"
    ROUTER = "router"
    SECURITY = "security"
    OTHER = "other"  # 其他设备（资产）
    # —— 基础设施（非资产，占 U 位但不进资产统计）——
    PATCH = "patch"  # 配线架
    ODF = "odf"  # ODF配线架
    OTHER_FACILITY = "other_facility"  # 其他设施


class DeviceStatus(str, Enum):
    """设备状态（资产生命周期，与机柜 U 位解耦）。

    - 在库：仅登记资产，未上架（默认）；设备下架后状态也回到「在库」（退回资产池）。
    - 已上架：存在一条状态为「有效」的上架记录。
    - 已下架：历史遗留状态（曾有上架记录、现已下架）。下架操作只会把上架记录置为
      「已下架」并保留用于追溯，设备本身退回「在库」——因此「已下架」不再作为设备生命
      周期的终态，运行时不会再被赋值。保留此枚举值仅为兼容历史数据与统计分类。
    - 待报废：人工标记待报废（与上下架无关）。
    - 借出：资产借出（人为标记，与上下架流程无关）；以独立颜色区分展示。
    """

    IN_STOCK = "在库"
    MOUNTED = "已上架"
    UNMOUNTED = "已下架"  # 历史遗留；不再被赋值，仅用于兼容与统计分类。
    SCRAPPED = "待报废"
    LENT = "借出"


class DevicePowerStatus(str, Enum):
    """设备开关机状态（仅对「在架」设备有意义；在库设备不涉及开关机）。

    与资产生命周期状态（DeviceStatus）正交：
    - 在库设备无需记录开关机（退回资产池，未通电），前端/2D 视图统一用中性色表达；
    - 在架设备据此在 2D 机柜视图中以不同底色区分：开机（运行时）用非红非绿的中性蓝紫，
      关机用红色（红色专用于告警 / 关机），便于一眼识别停机设备。
    """

    ON = "开机"
    OFF = "关机"


class MountRecordStatus(str, Enum):
    """上架记录状态。

    - 有效：当前生效的上架记录（设备仍在该机柜）。
    - 已下架：该次上架已结束（设备已下架，记录保留用于追溯）。
    """

    ACTIVE = "有效"
    UNMOUNTED = "已下架"


class InterfaceType(str, Enum):
    """物理接口类型（前面板端口形态）。

    覆盖交换机/服务器常见端口：电口（RJ-45）、管理口（Console，含 RJ-45/DB9）、
    光模块插槽（SFP 兼容 1G/10G/25G、QSFP 兼容 40G/100G）、其他（自行备注）。
    旧值 ``electrical`` / ``optical`` 保留仅为兼容历史数据，运行时由迁移脚本
    统一转换为 ``rj45`` / ``sfp``；前端不再提供这两个旧值。
    """

    RJ45 = "rj45"  # 电口（所有 RJ-45 电口）
    CONSOLE = "console"  # 管理口（Console，RJ-45 / DB9）
    SFP = "sfp"  # 光模块插槽（兼容 1G / 10G / 25G 模块）
    QSFP = "qsfp"  # 光模块插槽（兼容 40G / 100G 模块）
    OTHER = "other"  # 其他（自行备注，如 USB / 专用口）
    # —— 历史兼容（迁移后不再新增）——
    ELECTRICAL = "electrical"
    OPTICAL = "optical"


class InterfaceSpeed(str, Enum):
    """接口速率。"""

    G1 = "1G"
    G10 = "10G"
    G25 = "25G"
    G40 = "40G"
    G100 = "100G"


class InterfaceStatus(str, Enum):
    """接口状态（up=已建链/启用，down=未接线/停用）。

    仅由链路事务维护：新增接口默认 ``down``；建链事务置 ``up``；删链事务回落 ``down``。
    """

    UP = "up"
    DOWN = "down"


class InterfaceRole(str, Enum):
    """接口角色（数据口/管理口）。

    与 ``interface_type``（物理介质）正交：管理口是功能角色，可叠加在电口/光口之上。
    """

    DATA = "data"
    MGMT = "mgmt"


class LinkMedium(str, Enum):
    """连接介质类型（细分物理介质）。

    用户可选范围严格限定为：单模光纤（smf）/ 多模光纤（mmf）/ 双绞线（tp）。
    较旧的 ``copper`` / ``fiber`` 仅保留用于兼容历史数据，迁移脚本会统一转换为
    ``tp`` / ``mmf``；``coax`` / ``dac`` / ``aoc`` 已不再提供（历史库如需展示仍按
    字符串读取）。前端 ``LINK_MEDIUM_OPTIONS`` 仅暴露 smf / mmf / tp。
    """

    SMF = "smf"  # 单模光纤
    MMF = "mmf"  # 多模光纤
    TP = "tp"  # 双绞线（网线，Cat5e/6/6a）
    # —— 历史兼容（迁移后不再新增）——
    COPPER = "copper"
    FIBER = "fiber"


class ConnectorType(str, Enum):
    """连接器类型（链路两端接头 / 线缆类别），按连接介质动态联动、均为必选。

    - 光纤（smf / mmf）：LC / FC / SC / ST 等光纤连接器组合，必选。
    - 双绞线（tp）：线缆类别 CAT5 / CAT5e / CAT6 / CAT6a，必选（双绞线本身即介质，
      连接器字段记录的是网线类别，而非 RJ-45 插头——RJ-45 是所有双绞线两端统一的物理插头）。
    - 其他：无法归类时备注。
    """

    # 光纤连接器（medium = smf / mmf）
    LC_LC = "lc-lc"
    LC_FC = "lc-fc"
    LC_SC = "lc-sc"
    SC_SC = "sc-sc"
    SC_FC = "sc-fc"
    ST_ST = "st-st"
    # 双绞线类别（medium = tp）：线缆类别，必选
    CAT5 = "cat5"
    CAT5E = "cat5e"
    CAT6 = "cat6"
    CAT6A = "cat6a"
    # 其他
    OTHER = "other"


class ConsumableOpType(str, Enum):
    """耗材库存变动操作类型。

    - IN（入库）：库存增加，``quantity`` 为入库数量（正）。
    - OUT（领用）：库存减少，``quantity`` 为领用数量（正，出库即消耗）。
    - SCRAP（报废）：库存减少，``quantity`` 为报废数量（正）。
    - CHECK（盘点）：以实盘数量校正库存，``quantity`` 即盘点后的实际结存，
      库存直接置为该值（盘盈/盘亏由前后差额体现）。

    前端 ``frontend/src/utils/constants.js`` 的 ``CONSUMABLE_OP_OPTIONS`` 需与本枚举一致。
    """

    IN = "入库"
    OUT = "领用"
    SCRAP = "报废"
    CHECK = "盘点"


def calculate_rack_status(used_u: int, total_u: int) -> RackStatus:
    """根据已用 U 位与总 U 位计算机柜容量状态。

    规则（架构文档 §8）：ratio < 0.3 为 ``empty``；0.3 <= ratio <= 0.8 为 ``partial``；
    ratio > 0.8 为 ``full``。仅用于大屏利用率分布，不影响机柜业务状态字段。
    """
    if total_u is None or total_u <= 0:
        return RackStatus.EMPTY
    ratio = used_u / total_u
    if ratio < 0.3:
        return RackStatus.EMPTY
    if ratio <= 0.8:
        return RackStatus.PARTIAL
    return RackStatus.FULL
