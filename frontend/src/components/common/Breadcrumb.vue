<template>
  <nav class="flex items-center gap-1.5 text-sm min-w-0 leading-none" aria-label="breadcrumb">
    <router-link
      to="/dashboard"
      class="flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors shrink-0"
      aria-label="首页"
    >
      <Home class="w-4 h-4 block" />
    </router-link>
    <template v-for="(c, i) in crumbs" :key="c.to">
      <ChevronRight class="w-3.5 h-3.5 text-slate-300 shrink-0" />
      <router-link
        v-if="i < crumbs.length - 1"
        :to="c.to"
        class="text-slate-500 hover:text-brand-600 transition-colors truncate"
      >{{ c.label }}</router-link>
      <span v-else class="text-slate-800 font-medium truncate">{{ c.label }}</span>
    </template>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Home, ChevronRight } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

// 路由为扁平结构（无嵌套 children），route.matched 在详情页只能拿到叶子路由，
// 因此这里基于「当前路径逐段前缀」去全量路由表中匹配标题，重建出可点击的层级面包屑。
// 例：/rooms/5 → [机房管理(/rooms), 机房详情(/rooms/5)]；/devices/5/edit → [设备列表, 设备详情, 编辑设备]
const crumbs = computed(() => {
  const segments = route.path.split('/').filter(Boolean)
  const allRoutes = router.getRoutes()
  const result = []
  let acc = ''
  for (const seg of segments) {
    acc += '/' + seg
    const matched = allRoutes.find((r) => {
      if (!r.meta?.title) return false
      return resolveRoutePath(r.path, route.params) === acc
    })
    if (matched) result.push({ label: matched.meta.title, to: acc })
  }
  return result
})

function resolveRoutePath(pattern, params) {
  let p = pattern
  for (const key in params) {
    p = p.replace(`:${key}`, params[key])
  }
  return p
}
</script>
