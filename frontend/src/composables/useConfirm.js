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

  function onConfirm() {
    if (state.loading) return
    state._resolve?.(true)
    state.open = false
  }

  function onCancel() {
    if (state.loading) return
    state._resolve?.(false)
    state.open = false
  }

  return { state, confirm, onConfirm, onCancel }
}
