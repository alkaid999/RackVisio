import { ref } from 'vue'

// 全局单例 Toast 队列（替代 ElMessage）。
export const toasts = ref([])
let seq = 0

export function dismiss(id) {
  const i = toasts.value.findIndex((t) => t.id === id)
  if (i !== -1) toasts.value.splice(i, 1)
}

export function useToast() {
  function toast(opts = {}) {
    const item = {
      id: ++seq,
      title: '',
      description: '',
      variant: 'default', // default | success | error | warning | info | loading
      duration: 3200,
      ...opts,
    }
    toasts.value.push(item)
    if (item.duration > 0) {
      window.setTimeout(() => dismiss(item.id), item.duration)
    }
    return item.id
  }

  function dismiss(id) {
    const i = toasts.value.findIndex((t) => t.id === id)
    if (i !== -1) toasts.value.splice(i, 1)
  }

  const success = (title, opts = {}) => toast({ ...opts, title, variant: 'success' })
  const error = (title, opts = {}) => toast({ ...opts, title, variant: 'error' })
  const warning = (title, opts = {}) => toast({ ...opts, title, variant: 'warning' })
  const info = (title, opts = {}) => toast({ ...opts, title, variant: 'info' })

  return { toast, success, error, warning, info, dismiss }
}
