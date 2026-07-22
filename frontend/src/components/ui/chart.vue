<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useTheme } from '@/composables/useTheme'
import { chartTheme } from '@/utils/echarts-theme'
import { cn } from '@/lib/utils'

const props = defineProps({
  option: { type: Object, required: true },
  class: { type: null, required: false },
  loading: { type: Boolean, default: false },
})

const el = ref(null)
let chart = null
const { isDark } = useTheme()

function render() {
  if (!chart) return
  const t = chartTheme(isDark.value)
  const merged = {
    color: t.palette,
    backgroundColor: 'transparent',
    textStyle: { color: t.text, fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif' },
    ...props.option,
  }
  // 主题化的 tooltip 作为底层，option 中的 tooltip 局部覆盖（但不破坏明暗底色）
  merged.tooltip = {
    backgroundColor: t.tooltipBg,
    borderColor: t.border,
    textStyle: { color: t.tooltipText },
    extraCssText: 'border-radius:10px;box-shadow:0 10px 30px -10px rgba(0,0,0,.25);padding:8px 12px;',
    ...(props.option.tooltip || {}),
  }
  chart.setOption(merged, true)
}

function resize() {
  chart && chart.resize()
}

onMounted(async () => {
  await nextTick()
  chart = echarts.init(el.value, null, { renderer: 'canvas' })
  render()
  window.addEventListener('resize', resize)
})

watch(() => props.option, render, { deep: true })
watch(isDark, render)
watch(
  () => props.loading,
  (v) => {
    if (!chart) return
    v
      ? chart.showLoading('default', { text: '', color: chartTheme(isDark.value).palette[0], maskColor: 'rgba(127,127,127,0.04)' })
      : chart.hideLoading()
  }
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
})
</script>

<template>
  <div ref="el" :class="cn('h-full w-full', props.class)" />
</template>
