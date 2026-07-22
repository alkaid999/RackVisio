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
function apply() {
  const html = document.documentElement
  if (first) {
    // 首帧不播过渡，避免加载闪烁（index.html 内联脚本已先置好 class）
    html.classList.toggle('dark', isDark.value)
    first = false
    return
  }
  html.classList.add('theme-transition')
  html.classList.toggle('dark', isDark.value)
  window.setTimeout(() => html.classList.remove('theme-transition'), 420)
}
watch(isDark, apply)

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
