import { reactive } from 'vue'

// 全局单例确认对话框状态（替代 ElMessageBox.confirm）。
// 调用 confirm() 返回 Promise<boolean>，ConfirmDialog 组件消费同一 state。
const state = reactive({
  open: false,
  title: '提示',
  description: '',
  variant: 'warning', // warning | danger | default
  confirmText: '确定',
  cancelText: '取消',
  loading: false,
  _resolve: null,
})

export function useConfirm() {
  function confirm(opts = {}) {
    // M-08：若上一个对话框尚未响应（如双击触发新 confirm），先以 false 释放旧 Promise，
    // 避免调用方永久 await（悬挂）。
    state._resolve?.(false)
    return new Promise((resolve) => {
      state.title = opts.title || '提示'
      state.description = opts.description || ''
      state.variant = opts.variant || 'warning'
      state.confirmText = opts.confirmText || '确定'
      state.cancelText = opts.cancelText || '取消'
      state.loading = false
      state._resolve = resolve
      state.open = true
    })
  }

  function settle(result) {
    const r = state._resolve
    state._resolve = null // resolve 后清引用，避免重复 settle
    if (r) r(result)
    state.open = false
  }

  function onConfirm() {
    if (state.loading) return
    settle(true)
  }

  function onCancel() {
    if (state.loading) return
    settle(false)
  }

  return { state, confirm, onConfirm, onCancel }
}
