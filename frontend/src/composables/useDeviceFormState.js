import { reactive } from 'vue'

// 设备表单弹窗状态（模块级单例）。
// 与 useConfirm 同款机制：open 必须由 openDeviceForm() 在「用户手势处理函数内」同步置 true，
// 避免依赖 watch 异步置 true 导致时序问题。
// 仅个别路由会挂载 DeviceForm，故单例安全；组件卸载时重置 open 避免残留。
const state = reactive({
  open: false,
  mode: 'create', // 'create' | 'edit'
  deviceId: '',
  presetRackId: '',
  presetStartU: '',
})

export function useDeviceFormState() {
  return state
}

export function openDeviceForm(opts = {}) {
  state.mode = opts.mode || 'create'
  state.deviceId = opts.deviceId ?? ''
  state.presetRackId = opts.presetRackId ?? ''
  state.presetStartU = opts.presetStartU ?? ''
  state.open = true
}
