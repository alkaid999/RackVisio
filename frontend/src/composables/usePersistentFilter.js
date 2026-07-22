import { reactive, watch, onMounted } from 'vue'

// 列表筛选状态持久化：按路由名存储到 sessionStorage。
// - 路由离开（组件卸载）不丢失，返回（重新挂载）时 onMounted 自动恢复。
// - 任意筛选字段变化（deep watch）即落盘。
// - 调用 clear() 重置当前路由筛选；clearAllPersistedFilters() 在退出登录时清空全部。
// 设计目标（业务需求）：设备/机房/机柜列表筛选在进入下级页再返回后仍保留，
// 直到用户点「重置」或退出登录。
const PREFIX = 'rv_filter_'

export function usePersistentFilter(routeName, factory, onRestore) {
  const filter = reactive(factory())
  const KEY = PREFIX + routeName

  function persist() {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ ...filter }))
    } catch (e) {
      // sessionStorage 不可用（隐私模式等）时静默降级为内存态
    }
  }

  function restore() {
    try {
      const raw = sessionStorage.getItem(KEY)
      if (!raw) return
      const saved = JSON.parse(raw)
      // 先铺默认值（保证后续新增筛选项有缺省），再覆盖已保存值。
      Object.assign(filter, factory(), saved)
      if (typeof onRestore === 'function') onRestore(filter)
    } catch (e) {
      // 解析失败则忽略，使用默认值
    }
  }

  function clear() {
    try {
      sessionStorage.removeItem(KEY)
    } catch (e) {
      // ignore
    }
    Object.assign(filter, factory())
  }

  onMounted(restore)
  // 任意筛选字段变化即落盘（deep 监听嵌套对象）。
  watch(filter, persist, { deep: true })

  return { filter, persist, restore, clear }
}

// 退出登录时清空全部持久化筛选。
export function clearAllPersistedFilters() {
  try {
    Object.keys(sessionStorage)
      .filter((k) => k.startsWith(PREFIX))
      .forEach((k) => sessionStorage.removeItem(k))
  } catch (e) {
    // ignore
  }
}
