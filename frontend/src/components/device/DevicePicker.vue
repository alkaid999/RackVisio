<template>
  <div ref="triggerRef" class="relative w-full">
    <!-- 触发器：展示当前选中设备摘要 / 占位 -->
    <button
      type="button"
      :disabled="disabled"
      class="flex w-full items-center justify-between gap-2 rounded-md border border-border bg-background px-3 py-2 text-left text-sm transition-colors hover:border-primary/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
      @click="toggle"
    >
      <span v-if="selectedDevice" class="flex min-w-0 items-center gap-2">
        <span class="h-2 w-2 shrink-0 rounded-full" :style="{ backgroundColor: statusColorOf(selectedDevice) }"></span>
        <span class="truncate font-medium">{{ selectedDevice.name }}</span>
        <span class="shrink-0 text-xs text-muted-foreground">{{ typeLabel(selectedDevice.device_type) }}</span>
        <span v-if="selectedDevice.current_rack_name" class="shrink-0 text-xs text-slate-400">· {{ selectedDevice.current_rack_name }}</span>
      </span>
      <span v-else class="text-muted-foreground">{{ placeholder }}</span>
      <ChevronDown class="h-4 w-4 shrink-0 text-slate-400" :class="{ 'rotate-180': open }" />
    </button>

    <!-- 弹出层：Teleport 到 body，避免被弹窗 overflow 裁剪 -->
    <Teleport to="body">
      <div v-if="open" class="fixed inset-0 z-[69]" @click="close"></div>
      <div
        v-if="open"
        ref="popupRef"
        class="device-picker-popup fixed z-[70] flex w-[min(640px,92vw)] flex-col rounded-xl border border-border bg-card shadow-2xl"
        style="visibility:hidden"
      >
        <!-- 搜索 + 视图切换 -->
        <div class="flex items-center gap-2 border-b border-border p-2.5">
          <div class="relative flex-1">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              v-model="keyword"
              type="text"
              placeholder="搜索名称 / IP / 编号 / 机柜"
              class="w-full rounded-md border border-border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
            />
          </div>
          <div class="flex overflow-hidden rounded-md border border-border">
            <button
              type="button"
              class="px-2 py-1.5 text-slate-500 transition-colors"
              :class="viewMode === 'grid' ? 'bg-primary/10 text-primary' : 'hover:bg-muted'"
              title="网格"
              @click="viewMode = 'grid'"
            ><LayoutGrid class="h-4 w-4" /></button>
            <button
              type="button"
              class="px-2 py-1.5 text-slate-500 transition-colors"
              :class="viewMode === 'list' ? 'bg-primary/10 text-primary' : 'hover:bg-muted'"
              title="列表"
              @click="viewMode = 'list'"
            ><List class="h-4 w-4" /></button>
          </div>
        </div>

        <!-- 筛选维度 -->
        <div class="flex flex-wrap items-center gap-2 border-b border-border bg-muted/30 px-2.5 py-2">
          <Select v-model="fType">
            <SelectTrigger class="h-8 w-[104px] text-xs" placeholder="设备类型" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部类型</SelectItem>
              <SelectItem v-for="t in DEVICE_TYPE_OPTIONS" :key="t.value" :value="t.value">{{ t.label }}</SelectItem>
            </SelectContent>
          </Select>
          <Select v-model="fOnline">
            <SelectTrigger class="h-8 w-[96px] text-xs" placeholder="在线状态" />
            <SelectContent>
              <SelectItem :value="ONLINE_ALL">全部状态</SelectItem>
              <SelectItem :value="ONLINE_ON">在线（已上架）</SelectItem>
              <SelectItem :value="ONLINE_OFF">离线（其他）</SelectItem>
            </SelectContent>
          </Select>
          <Select v-model="fRoom" @update:model-value="onRoomChange">
            <SelectTrigger class="h-8 w-[120px] text-xs" placeholder="所属机房" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部机房</SelectItem>
              <SelectItem v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}</SelectItem>
            </SelectContent>
          </Select>
          <Select v-model="fRack" :disabled="!toFilterParam(fRoom)">
            <SelectTrigger class="h-8 w-[120px] text-xs" placeholder="所属机柜" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部机柜</SelectItem>
              <SelectItem v-for="r in racks" :key="r.id" :value="r.id">{{ r.name }}</SelectItem>
            </SelectContent>
          </Select>
          <Button v-if="hasActiveFilter" variant="ghost" size="sm" class="h-8 px-2 text-xs text-slate-500" @click="resetFilters">
            <RotateCcw class="h-3.5 w-3.5" />重置
          </Button>
        </div>

        <!-- 结果计数 -->
        <div class="px-3 pt-2 text-xs text-slate-400">
          共 {{ filtered.length }} 台设备
          <span v-if="reasonActive">（红字标注不可建链原因）</span>
        </div>

        <!-- 卡片 / 列表 -->
        <div class="min-h-0 flex-1 overflow-y-auto p-2.5">
          <div
            v-if="viewMode === 'grid'"
            class="grid grid-cols-1 gap-2 sm:grid-cols-2"
          >
            <button
              v-for="d in filtered"
              :key="d.id"
              type="button"
              :disabled="!isSelectable(d)"
              class="device-card group relative flex flex-col gap-1.5 rounded-lg border p-3 text-left transition-all"
              :class="[
                modelValue === d.id ? 'border-primary ring-2 ring-primary/40 bg-primary/5' : 'border-border hover:border-primary/40 hover:bg-muted/50',
                isSelectable(d) ? '' : 'cursor-not-allowed border-red-200 bg-red-50/60 hover:border-red-300 hover:bg-red-50',
              ]"
              @click="pick(d)"
            >
              <DeviceCardBody :device="d" :selected="modelValue === d.id" />
              <span v-if="reasonOf(d)" class="mt-0.5 inline-flex items-center gap-1 text-xs font-medium text-red-500">
                <Ban class="h-3 w-3" />{{ reasonOf(d) }}
              </span>
            </button>
          </div>
          <div v-else class="flex flex-col gap-1.5">
            <button
              v-for="d in filtered"
              :key="d.id"
              type="button"
              :disabled="!isSelectable(d)"
              class="device-card relative flex items-center gap-3 rounded-lg border p-2.5 text-left transition-all"
              :class="[
                modelValue === d.id ? 'border-primary ring-2 ring-primary/40 bg-primary/5' : 'border-border hover:border-primary/40 hover:bg-muted/50',
                isSelectable(d) ? '' : 'cursor-not-allowed border-red-200 bg-red-50/60 hover:border-red-300 hover:bg-red-50',
              ]"
              @click="pick(d)"
            >
              <DeviceCardBody :device="d" :selected="modelValue === d.id" :list="true" />
              <span v-if="reasonOf(d)" class="ml-auto inline-flex shrink-0 items-center gap-1 text-xs font-medium text-red-500">
                <Ban class="h-3 w-3" />{{ reasonOf(d) }}
              </span>
            </button>
          </div>

          <div v-if="!filtered.length" class="py-10 text-center text-sm text-slate-400">
            无匹配设备，请调整搜索或筛选条件
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { ChevronDown, Search, LayoutGrid, List, RotateCcw, Ban } from 'lucide-vue-next'
import { DEVICE_TYPE_OPTIONS, DEVICE_TYPE_LABELS, DEVICE_TYPE_COLORS, DEVICE_STATUS_COLORS, SELECT_ALL, toFilterParam } from '@/utils/constants'
import roomApi from '@/api/room'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Button from '@/components/ui/button.vue'
import DeviceCardBody from '@/components/device/DeviceCardBody.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  // 全量设备列表（由父级一次性加载，选择器内部做客户端模糊搜索 + 多维筛选）。
  devices: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '选择设备' },
  disabled: { type: Boolean, default: false },
  // 不可建链原因：函数返回字符串原因 → 该设备不可选并红字展示原因；返回空/假值 → 可选。
  // 如新建链路仅允许「已上架且含接口」且同机房，原因由父级给出（未上架/无可用接口/不在同一机房/不能选择自身）。
  selectableReason: { type: Function, default: null },
})
const emit = defineEmits(['update:modelValue', 'select'])

const triggerRef = ref(null)
const popupRef = ref(null)
const open = ref(false)
const keyword = ref('')
const fType = ref(SELECT_ALL)
const fOnline = ref('__all_online__')
const fRoom = ref(SELECT_ALL)
const fRack = ref(SELECT_ALL)
const viewMode = ref('grid')
const rooms = ref([])
const racks = ref([])

const ONLINE_ALL = '__all_online__'
const ONLINE_ON = 'online'
const ONLINE_OFF = 'offline'

const reasonActive = computed(() => !!props.selectableReason)
function isSelectable(d) {
  return props.selectableReason ? !props.selectableReason(d) : true
}
function reasonOf(d) {
  return props.selectableReason ? props.selectableReason(d) : ''
}
const selectedDevice = computed(() => props.devices.find((d) => d.id === props.modelValue) || null)

function typeLabel(t) {
  return DEVICE_TYPE_LABELS[t] || t || ''
}
function statusColorOf(d) {
  return DEVICE_STATUS_COLORS[d.status] || '#909399'
}
const hasActiveFilter = computed(
  () => !!(keyword.value || toFilterParam(fType.value) || fOnline.value !== ONLINE_ALL || toFilterParam(fRoom.value) || toFilterParam(fRack.value)),
)

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const type = toFilterParam(fType.value)
  const room = toFilterParam(fRoom.value)
  const rack = toFilterParam(fRack.value)
  const online = fOnline.value
  return props.devices.filter((d) => {
    if (type && d.device_type !== type) return false
    if (online === ONLINE_ON && d.status !== '已上架') return false
    if (online === ONLINE_OFF && d.status === '已上架') return false
    if (room && d.current_room_id !== room) return false
    if (rack && d.current_rack_id !== rack) return false
    if (kw) {
      const hay = [d.name, d.ip_address, d.device_code, d.current_rack_name]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

function resetFilters() {
  keyword.value = ''
  fType.value = SELECT_ALL
  fOnline.value = ONLINE_ALL
  fRoom.value = SELECT_ALL
  fRack.value = SELECT_ALL
  racks.value = []
}

async function onRoomChange() {
  fRack.value = SELECT_ALL
  racks.value = []
  const room = toFilterParam(fRoom.value)
  if (room) {
    try {
      racks.value = await roomApi.racks(room)
    } catch (e) {
      racks.value = []
    }
  }
}

function positionPopup() {
  const el = triggerRef.value
  const popup = popupRef.value
  if (!el || !popup) return
  const r = el.getBoundingClientRect()
  const vh = window.innerHeight
  const vw = window.innerWidth
  const margin = 12
  const w = Math.min(640, Math.max(360, r.width * 1.5))
  let left = r.left
  if (left + w > vw - margin) left = Math.max(margin, vw - w - margin)

  // 直接操作 DOM 同步定位：用「弹层当前高 − 内部滚动区可见高 + 内部滚动区内容高(scrollHeight)」推算自然高度，
  // 而不解除 maxHeight 钳制再去读 offsetHeight —— 否则 flex 子项不再溢出、浏览器会把内部 scrollTop 重置回顶部，
  // 表现为滚轮向下滚后被强制弹回顶部（本轮修复的滚动 bug：弹层内列表自身滚动被捕获监听触发重定位，测量时 maxHeight=none 把 scrollTop 清零）。
  popup.style.visibility = 'hidden'
  popup.style.width = w + 'px'
  popup.style.left = left + 'px'

  const inner = popup.querySelector('.overflow-y-auto')
  const innerNatural = inner ? inner.scrollHeight : 0
  const otherH = popup.offsetHeight - (inner ? inner.clientHeight : popup.offsetHeight)
  const naturalH = otherH + innerNatural
  const maxAllowed = vh - margin * 2
  const safeH = Math.min(naturalH + 16, maxAllowed) // 预留 16px 缓冲图标/字体晚到的微小增长
  const spaceBelow = vh - r.bottom - margin
  const spaceAbove = r.top - margin

  let top
  if (naturalH <= spaceBelow) top = r.bottom + 6 // 下方空间足够 → 向下展开
  else if (naturalH <= spaceAbove) top = r.top - 6 - naturalH // 上方空间足够 → 向上展开
  else if (maxAllowed <= spaceBelow) top = r.bottom + 6 // 内容偏高但 maxAllowed 可向下容纳
  else if (maxAllowed <= spaceAbove) top = r.top - 6 - maxAllowed // 或向上容纳
  else top = margin // 超高内容：贴顶 + 内部滚动

  // 终态钳制：用安全高度确保整个弹层（含内部滚动）完整在视口内，绝不溢出上下边界。
  top = Math.min(Math.max(top, margin), Math.max(margin, vh - safeH - margin))

  popup.style.top = top + 'px'
  popup.style.maxHeight = maxAllowed + 'px'
  popup.style.visibility = 'visible'
}

function toggle() {
  if (props.disabled) return
  if (open.value) close()
  else openPicker()
}
function onScrollCapture(e) {
  // 内部列表自身滚动不触发重定位：触发器未移动，且避免重排把 scrollTop 重置回顶部
  if (popupRef.value && e.target && popupRef.value.contains(e.target)) return
  positionPopup()
}
function openPicker() {
  open.value = true
  // 首帧定位 + rAF 再定位一次：捕获图标/字体/红标晚到导致的布局增长，避免初测高度偏小后溢出。
  nextTick(positionPopup)
  requestAnimationFrame(() => positionPopup())
  window.addEventListener('scroll', onScrollCapture, true)
  window.addEventListener('resize', positionPopup)
}
function close() {
  open.value = false
  window.removeEventListener('scroll', onScrollCapture, true)
  window.removeEventListener('resize', positionPopup)
}
function pick(d) {
  if (!isSelectable(d)) return
  emit('update:modelValue', d.id)
  emit('select', d)
  close()
}

// 父级传入 devices 后，懒加载机房/机柜筛选项一次。
watch(
  () => props.devices,
  async (list) => {
    if (rooms.value.length || !list || !list.length) return
    try {
      const d = await roomApi.list({ size: 200 })
      rooms.value = d.items || []
    } catch (e) {
      rooms.value = []
    }
  },
  { immediate: true },
)

watch(
  () => props.modelValue,
  () => {
    /* 选中变化由父级驱动，无需额外处理 */
  },
)

// 视图切换（网格↔列表）或筛选结果数量变化会改变弹层内容高度，若已展开需重新定位，
// 否则在列表模式下内容变高会导致弹层向下溢出屏幕（grid 模式定位后仍停留在原 top）。
watch(
  [viewMode, () => filtered.value.length],
  () => {
    if (open.value) {
      nextTick(positionPopup)
      requestAnimationFrame(() => positionPopup())
    }
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScrollCapture, true)
  window.removeEventListener('resize', positionPopup)
})
</script>

<style scoped>
.device-card:disabled {
  cursor: not-allowed;
}
</style>
