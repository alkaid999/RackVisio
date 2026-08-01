// 列表「末页回退」页码计算（M-04）：收敛各列表页重复的
// 「当前页被删空时回退到有效页」逻辑。此前在 DeviceList/RoomList/RackList/
// ConsumableList/MountRecordList/OperationLog 各写一份，行为易漂移。
//
// 用法：
//   const data = await loader(page.value)
//   if (data.items.length === 0 && page.value > 1 && data.total > 0) {
//     page.value = backToValidPage(page.value, data.total, pageSize.value)
//     const again = await loader(page.value) // 回退后重新加载
//     ...
//   }
//
// 返回值：回退后的有效页码（>=1，不高于按 total/pageSize 算出的最大页）。
export function backToValidPage(currentPage, total, pageSize) {
  const maxPage = Math.max(1, Math.ceil((total || 0) / (pageSize || 20)))
  return Math.min(currentPage, maxPage)
}
