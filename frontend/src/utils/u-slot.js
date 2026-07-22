// 前端实时 U 位冲突检测：镜像后端 DeviceService.check_u_conflict 逻辑。
// 用于 DeviceForm 提交前的本地预校验；后端 /racks/{id}/check-u 做二次校验。

/**
 * 检测新设备上架是否与其他设备 U 位冲突。
 * @param {Object} rack 机柜对象，需含 total_u（总 U 位）
 * @param {Array} devices 机柜现有设备列表，每项含 {id, name, current_start_u, u_height}
 * @param {number} startU 新设备起始 U 位（≥1）
 * @param {number} sizeU 新设备占用 U 位数（≥1）
 * @param {string|null} excludeDeviceId 编辑设备时排除自身
 * @returns {{conflict: boolean, conflictU?: number[], conflictDevice?: string, error?: string}}
 */
export function checkUConflict(rack, devices = [], startU, sizeU, excludeDeviceId = null) {
  // 参数合法性校验。
  if (startU < 1 || sizeU < 1) {
    return { conflict: true, error: '起始 U 位必须 ≥1 且占用 U 位数 ≥1' }
  }
  const totalU = rack && rack.total_u ? rack.total_u : 0
  // 目标占用区间（左闭右开）。
  const targetRange = rangeSet(startU, startU + sizeU)

  for (const device of devices) {
    if (excludeDeviceId && device.id === excludeDeviceId) continue
    const existingRange = rangeSet(device.current_start_u, device.current_start_u + device.u_height)
    const overlap = [...targetRange].filter((u) => existingRange.has(u))
    if (overlap.length > 0) {
      return {
        conflict: true,
        conflictU: overlap.sort((a, b) => a - b),
        conflictDevice: device.name,
      }
    }
  }

  // 越界检测。
  if (startU + sizeU - 1 > totalU) {
    return { conflict: true, error: `超出机柜 U 位范围（1~${totalU}）` }
  }

  return { conflict: false }
}

// 生成 [start, end) 的整数集合。
function rangeSet(start, end) {
  const set = new Set()
  for (let u = start; u < end; u++) set.add(u)
  return set
}

/**
 * 计算机柜容量状态（镜像后端 calculate_rack_status）。
 * ratio < 0.3 -> empty；0.3~0.8 -> partial；> 0.8 -> full。
 */
export function computeRackStatus(usedU, totalU) {
  if (!totalU || totalU <= 0) return 'empty'
  const ratio = usedU / totalU
  if (ratio < 0.3) return 'empty'
  if (ratio <= 0.8) return 'partial'
  return 'full'
}

/**
 * 将设备列表合成为机柜 U 位占用图（自底向上，U=1 在最底部）。
 * 返回 slots 数组（索引 0 对应 U=1）。
 */
export function buildUMap(totalU, devices = []) {
  const slotMap = new Map()
  for (const d of devices) {
    for (let u = d.current_start_u; u < d.current_start_u + d.u_height; u++) {
      slotMap.set(u, { deviceId: d.id, deviceName: d.name, deviceType: d.device_type })
    }
  }
  const slots = []
  for (let u = 1; u <= totalU; u++) {
    const occupied = slotMap.get(u)
    slots.push({
      u,
      deviceId: occupied ? occupied.deviceId : null,
      deviceName: occupied ? occupied.deviceName : null,
      deviceType: occupied ? occupied.deviceType : null,
    })
  }
  return slots
}
