<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Server, Network, Cable, CornerDownLeft, ArrowUp, ArrowDown, Loader2 } from 'lucide-vue-next'
import deviceApi from '@/api/device'
import interfaceApi from '@/api/interface'
import linkApi from '@/api/link'
import { useMetaStore } from '@/stores/meta'
import { LINK_MEDIUM_LABELS, INTERFACE_TYPE_LABELS } from '@/utils/constants'
import { cn } from '@/lib/utils'
import Badge from '@/components/ui/badge.vue'
import Kbd from '@/components/ui/kbd.vue'
import EmptyState from '@/components/ui/empty-state.vue'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue'])

const router = useRouter()
const meta = useMetaStore()

const query = ref('')
const loading = ref(false)
const devices = ref([])
const interfaces = ref([])
const links = ref([])
const activeIndex = ref(0)
const inputEl = ref(null)

function typeLabel(v) {
  if (!v) return ''
  const found = meta.deviceType.find((t) => t.value === v)
  return found ? found.label : v
}
function mediumLabel(v) {
  return LINK_MEDIUM_LABELS[v] || v || ''
}
function ifaceTypeLabel(v) {
  return INTERFACE_TYPE_LABELS[v] || v || ''
}

// 结果按类型分组（带扁平序号，供键盘导航高亮）。
const groups = computed(() => {
  let idx = 0
  const g = []
  const push = (key, label, icon, items) => {
    if (!items.length) return
    g.push({ key, label, icon, items: items.map((it) => ({ ...it, __idx: idx++ })) })
  }
  push(
    'device',
    '设备',
    Server,
    devices.value.map((d) => ({
      kind: 'device',
      id: d.id,
      to: `/devices/${d.id}`,
      title: d.name,
      subtitle: [d.device_code, d.ip_address].filter(Boolean).join('  ·  '),
      badge: typeLabel(d.device_type),
      badgeVariant: 'secondary',
    }))
  )
  push(
    'interface',
    '接口',
    Network,
    interfaces.value.map((i) => ({
      kind: 'interface',
      id: i.id,
      to: `/devices/${i.device_id}`,
      title: i.name,
      subtitle: i.device_name || '',
      badge: ifaceTypeLabel(i.interface_type),
      badgeVariant: 'outline',
    }))
  )
  push(
    'link',
    '链路',
    Cable,
    links.value.map((l) => {
      const peerName = l.target_device_name && l.target_device_name !== l.source_device_name ? l.target_device_name : ''
      const title = l.source_interface_name + (l.target_interface_name ? `  →  ${l.target_interface_name}` : peerName ? `  →  ${peerName}` : '')
      const subtitle = l.source_device_name + (peerName ? `  ↔  ${peerName}` : '')
      return {
        kind: 'link',
        id: l.id,
        to: `/devices/${l.source_device_id}`,
        title,
        subtitle,
        badge: mediumLabel(l.medium),
        badgeVariant: 'default',
      }
    })
  )
  return g
})

const flatItems = computed(() => groups.value.flatMap((g) => g.items))
const hasQuery = computed(() => query.value.trim().length > 0)
const totalResults = computed(() => flatItems.value.length)

let debounceTimer = null
function onInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(runSearch, 220)
}

async function runSearch() {
  const q = query.value.trim()
  if (!q) {
    devices.value = []
    interfaces.value = []
    links.value = []
    loading.value = false
    return
  }
  loading.value = true
  try {
    // 三类端点并行查询；单类无权限（403）不阻断其它类结果。
    const [dRes, iRes, lRes] = await Promise.allSettled([
      deviceApi.list({ keyword: q, size: 8, page: 1 }),
      interfaceApi.listAll({ keyword: q, size: 8, page: 1 }),
      linkApi.list({ keyword: q, size: 8, page: 1 }),
    ])
    devices.value = dRes.status === 'fulfilled' ? dRes.value.items || [] : []
    interfaces.value = iRes.status === 'fulfilled' ? iRes.value.items || [] : []
    links.value = lRes.status === 'fulfilled' ? lRes.value.items || [] : []
    activeIndex.value = 0
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
function activate(item) {
  if (!item) return
  close()
  router.push(item.to)
}
function onEnter() {
  activate(flatItems.value[activeIndex.value])
}
function onUp() {
  if (flatItems.value.length) activeIndex.value = (activeIndex.value - 1 + flatItems.value.length) % flatItems.value.length
}
function onDown() {
  if (flatItems.value.length) activeIndex.value = (activeIndex.value + 1) % flatItems.value.length
}

function onKeydown(e) {
  if (!props.modelValue) return
  if (e.key === 'Escape') {
    e.preventDefault()
    close()
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    onDown()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    onUp()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    onEnter()
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      nextTick(() => inputEl.value?.focus())
    } else {
      query.value = ''
      devices.value = []
      interfaces.value = []
      links.value = []
      activeIndex.value = 0
      if (typeof document !== 'undefined') document.body.style.overflow = ''
    }
  }
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  if (typeof document !== 'undefined') document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[12vh]"
      role="dialog"
      aria-modal="true"
    >
      <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="close" />

      <div
        class="relative z-10 flex max-h-[76vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-card"
      >
        <!-- 搜索输入 -->
        <div class="flex items-center gap-3 border-b border-border/60 px-4">
          <Search class="h-5 w-5 shrink-0 text-muted-foreground" />
          <input
            ref="inputEl"
            v-model="query"
            type="text"
            placeholder="搜索设备、接口、IP 或链路…"
            class="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            @input="onInput"
          />
          <Loader2 v-if="loading" class="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
        </div>

        <!-- 结果区 -->
        <div class="min-h-0 flex-1 overflow-y-auto scroll-thin">
          <template v-if="hasQuery">
              <EmptyState
                v-if="!loading && totalResults === 0"
                title="未找到匹配项"
                :icon="Search"
                class="py-12"
              />

            <div v-for="g in groups" :key="g.key" class="py-2">
              <div class="flex items-center gap-1.5 px-4 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <component :is="g.icon" class="h-3.5 w-3.5" />
                {{ g.label }}
                <span class="ml-1 text-muted-foreground/60">{{ g.items.length }}</span>
              </div>
              <button
                v-for="item in g.items"
                :key="g.key + ':' + item.id"
                type="button"
                :class="
                  cn(
                    'flex w-full items-center gap-3 px-4 py-2 text-left transition-colors',
                    item.__idx === activeIndex ? 'bg-accent' : 'hover:bg-accent/60'
                  )
                "
                @mousemove="activeIndex = item.__idx"
                @click="activate(item)"
              >
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-medium">{{ item.title }}</div>
                  <div v-if="item.subtitle" class="truncate text-xs text-muted-foreground">{{ item.subtitle }}</div>
                </div>
                <Badge v-if="item.badge" :variant="item.badgeVariant" class="shrink-0">{{ item.badge }}</Badge>
                <Kbd v-if="item.__idx === activeIndex" class="shrink-0">↵</Kbd>
              </button>
            </div>
          </template>

          <div v-else class="px-4 py-10 text-center text-sm text-muted-foreground">
            输入关键字以检索全站资产（设备 / 接口 / IP / 链路）
          </div>
        </div>

        <!-- 底部操作提示 -->
        <div class="flex items-center gap-4 border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
          <span class="flex items-center gap-1"><Kbd><ArrowUp class="h-3 w-3" /></Kbd><Kbd><ArrowDown class="h-3 w-3" /></Kbd>选择</span>
          <span class="flex items-center gap-1"><Kbd><CornerDownLeft class="h-3 w-3" /></Kbd>打开</span>
          <span class="flex items-center gap-1"><Kbd>Esc</Kbd>关闭</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>
