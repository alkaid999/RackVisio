import { ref, computed, watch } from 'vue'

// 全局单例主题状态：light / dark / system（跟随系统）。
// 柔和暗黑模式通过切换 <html class="dark"> 实现整站换肤，令牌在 index.css 中定义。
const THEME_KEY = 'theme'
const theme = ref(localStorage.getItem(THEME_KEY) || 'system')
const mql = window.matchMedia('(prefers-color-scheme: dark)')
const systemDark = ref(mql.matches)
mql.addEventListener('change', (e) => {
  systemDark.value = e.matches
})

const isDark = computed(() => theme.value === 'dark' || (theme.value === 'system' && systemDark.value))

let first = true
function applyTheme() {
  const html = document.documentElement
  if (first) {
    // 首帧不播过渡，避免加载闪烁（index.html 内联脚本已先置好 class）
    html.classList.toggle('dark', isDark.value)
    first = false
    return
  }
  // 用 View Transitions API 做整页交叉淡入：仅一次合成层变换（GPU 合成），
  // 不再给全页每个元素挂 0.4s 过渡，彻底消除逐节点重绘掉帧的卡顿。
  // 不支持的浏览器直接切换 class：瞬时完成、零延迟、无掉帧。
  const swap = () => html.classList.toggle('dark', isDark.value)
  if (typeof document.startViewTransition === 'function') {
    document.startViewTransition(swap)
  } else {
    swap()
  }
}
watch(isDark, applyTheme)

export function useTheme() {
  function setTheme(value) {
    theme.value = value
    try {
      localStorage.setItem(THEME_KEY, value)
    } catch (e) {
      /* ignore */
    }
  }
  function toggle() {
    setTheme(isDark.value ? 'light' : 'dark')
  }
  return { theme, isDark, setTheme, toggle }
}
