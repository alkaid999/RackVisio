<template>
  <div>
    <!-- 操作栏：重置排列 / 3D 总览（拖拽保存逻辑的写操作受 rack:edit 门控） -->
    <div class="mb-3 flex items-center justify-end gap-2">
      <button
        v-if="canEditRack"
        class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
        :disabled="saving"
        @click="resetLayout"
      >
        <RotateCcw class="h-4 w-4" /> 重置排列
      </button>
      <button
        class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-500 px-3 text-sm font-medium text-white transition-colors hover:bg-brand-600"
        @click="go3D"
      >
        <Boxes class="h-4 w-4" /> 3D 总览
      </button>
    </div>

    <div v-if="loading" class="py-20 text-center text-muted-foreground">加载中…</div>
    <div v-else-if="!racks.length" class="py-20 text-center text-muted-foreground">
      该机房暂无机柜，请先在机房详情中添加机柜。
    </div>

    <div v-else ref="scrollRef" class="flex gap-2 overflow-x-auto p-2 sm:p-3">
      <!-- 左侧行标签（列编号） -->
      <div class="shrink-0 w-10 pt-[14px]" :style="{ height: boardH + 'px' }">
        <div
          v-for="(label, r) in rowLabels"
          :key="'rl-' + r"
          class="flex items-center justify-end pr-1 text-[10px] font-medium text-muted-foreground"
          :style="{ height: CELL_H + 'px', marginBottom: GAP + 'px' }"
        >
          {{ label }}
        </div>
      </div>

      <!-- 画板 -->
      <div
        ref="boardRef"
        class="relative shrink-0 rounded-2xl border border-dashed border-border/60 bg-muted/30"
        :style="{ width: boardW + 'px', height: boardH + 'px' }"
        @mouseenter="onEnter"
        @mouseleave="onLeave"
      >
        <!-- 网格底纹 -->
        <div class="pointer-events-none absolute inset-0 opacity-[0.5]">
          <div
            v-for="r in bounds.rows"
            :key="'gr-' + r"
            class="absolute left-0 right-0 border-t border-border/40"
            :style="{ top: PAD + r * (CELL_H + GAP) - GAP / 2 + 'px' }"
          />
          <div
            v-for="c in bounds.cols"
            :key="'gc-' + c"
            class="absolute top-0 bottom-0 border-l border-border/40"
            :style="{ left: PAD + c * (CELL_W + GAP) - GAP / 2 + 'px' }"
          />
        </div>

        <!-- 落点高亮 -->
        <div
          v-if="drag.over"
          class="pointer-events-none absolute rounded-xl border-2 border-brand-400 bg-brand-400/10"
          :style="cellBox(drag.over.r, drag.over.c)"
        />

        <!-- 机柜瓦片 -->
        <div
          v-for="rack in racks"
          :key="rack.id"
          class="rack-tile group absolute flex select-none flex-col rounded-xl border bg-card p-2.5 shadow-sm transition-shadow overflow-hidden"
          :class="[
            drag.id === rack.id ? 'z-50 shadow-xl ring-2 ring-brand-400' : 'hover:shadow-md',
            tileBorder(rack),
          ]"
          :style="tileStyle(rack)"
          @pointerdown="onPointerDown($event, rack)"
        >
          <!-- 机柜信息（去掉无意义的装饰框，仅保留关键字段；无悬浮操作图标） -->
          <div class="flex min-w-0 flex-1 flex-col">
            <div class="truncate text-sm font-semibold leading-tight text-foreground">{{ rack.name }}</div>
            <div class="mt-0.5 truncate text-[11px] text-muted-foreground">{{ rack.column_code }} / {{ rack.code }}</div>
            <div class="mt-auto flex flex-col items-start gap-1.5 pt-2">
              <StatusBadge type="rack" :value="rack.status" />
              <span class="inline-flex items-center gap-1 text-[11px] tabular-nums text-muted-foreground">
                <Ruler class="h-3 w-3" />{{ rack.used_u }}/{{ rack.total_u }}U
              </span>
            </div>
            <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div class="h-full rounded-full" :style="{ width: util(rack) + '%', backgroundColor: utilColor(rack) }" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Boxes, RotateCcw, Ruler } from 'lucide-vue-next'
import StatusBadge from '@/components/common/StatusBadge.vue'
import rackApi from '@/api/rack'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'

const props = defineProps({
  roomId: { type: [String, Number], required: true },
})
// 机柜位置/编辑变更后通知父级（如详情页）刷新容量统计，保持数据一致。
const emit = defineEmits(['updated'])

const router = useRouter()
const auth = useAuthStore()
const meta = useMetaStore()
// 机柜相关写操作（编辑 / 删除 / 拖拽改坐标 / 重置排列）均需 rack:edit；只读用户隐藏写按钮并禁止拖拽。
const canEditRack = computed(() => auth.hasPermission('rack:edit'))

const CELL_W = 132
const CELL_H = 140
const GAP = 16
const PAD = 14 // 画板内边距：瓦片与顶部/左侧留白，不贴虚线框

const loading = ref(true)
const saving = ref(false)
const racks = ref([])
const boardRef = ref(null)
const scrollRef = ref(null)

const bounds = computed(() => {
  let maxR = 0
  let maxC = 0
  for (const r of racks.value) {
    if (r.grid_row != null) maxR = Math.max(maxR, r.grid_row)
    if (r.grid_col != null) maxC = Math.max(maxC, r.grid_col)
  }
  return { rows: Math.max(3, maxR + 2), cols: Math.max(4, maxC + 2) }
})
const boardW = computed(() => PAD * 2 + bounds.value.cols * (CELL_W + GAP) - GAP)
const boardH = computed(() => PAD * 2 + bounds.value.rows * (CELL_H + GAP) - GAP)

const rowLabels = computed(() => {
  const labels = []
  for (let r = 0; r < bounds.value.rows; r++) {
    const cols = [...new Set(racks.value.filter((x) => x.grid_row === r).map((x) => x.column_code))]
    labels.push(cols.length ? cols.join(' · ') : '')
  }
  return labels
})
function cellBox(r, c) {
  return {
    left: PAD + c * (CELL_W + GAP) + 'px',
    top: PAD + r * (CELL_H + GAP) + 'px',
    width: CELL_W + 'px',
    height: CELL_H + 'px',
    minHeight: CELL_H + 'px',
    maxHeight: CELL_H + 'px',
  }
}
function tileStyle(rack) {
  const base = cellBox(rack.grid_row ?? 0, rack.grid_col ?? 0)
  if (drag.value.id === rack.id && (drag.value.dx || drag.value.dy)) {
    return {
      ...base,
      transform: `translate(${drag.value.dx}px, ${drag.value.dy}px)`,
      cursor: 'grabbing',
    }
  }
  return base
}
function util(rack) {
  return rack.total_u > 0 ? Math.min(100, Math.round((rack.used_u / rack.total_u) * 100)) : 0
}
function utilColor(rack) {
  const u = rack.total_u > 0 ? rack.used_u / rack.total_u : 0
  // 使用率配色统一走 meta.usageColor（审查报告#352）。
  return meta.usageColor(u)
}
function tileBorder(rack) {
  // P1：硬编码 red-400/sky-300 → 语义令牌（destructive=不可用、info 系=制冷/配电）。
  // 制冷/配电机柜用 brand 蓝（与机柜状态徽章 RACK_STATUS_COLORS 同源，避免任意色）。
  if (rack.status === '不可用') return 'border-destructive/50'
  if (rack.status === '制冷机柜' || rack.status === '配电机柜') return 'border-brand-400/60'
  return 'border-border'
}

// ---------------------------------------------------------------- 拖拽
const drag = ref({ id: null, dx: 0, dy: 0, over: null, startX: 0, startY: 0, moved: false })
const DRAG_THRESHOLD = 4

function occupantAt(r, c, excludeId) {
  return racks.value.find((x) => x.id !== excludeId && x.grid_row === r && x.grid_col === c)
}
function onPointerDown(e, rack) {
  if (!canEditRack.value) return
  drag.value = { id: rack.id, dx: 0, dy: 0, over: null, startX: e.clientX, startY: e.clientY, moved: false }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}
function onPointerMove(e) {
  const d = drag.value
  if (!d.id) return
  const dx = e.clientX - d.startX
  const dy = e.clientY - d.startY
  if (!d.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD) d.moved = true
  d.dx = dx
  d.dy = dy
  const rect = boardRef.value.getBoundingClientRect()
  let c = Math.floor((e.clientX - rect.left - PAD) / (CELL_W + GAP))
  let r = Math.floor((e.clientY - rect.top - PAD) / (CELL_H + GAP))
  r = Math.max(0, Math.min(bounds.value.rows - 1, r))
  c = Math.max(0, Math.min(bounds.value.cols - 1, c))
  d.over = { r, c }
}
async function onPointerUp() {
  const d = drag.value
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  if (!d.id) return
  const rack = racks.value.find((x) => x.id === d.id)
  if (rack && d.moved && d.over && (d.over.r !== rack.grid_row || d.over.c !== rack.grid_col)) {
    const updates = []
    const occ = occupantAt(d.over.r, d.over.c, rack.id)
    if (occ) {
      occ.grid_row = rack.grid_row
      occ.grid_col = rack.grid_col
      updates.push({ id: occ.id, grid_row: occ.grid_row, grid_col: occ.grid_col })
    }
    rack.grid_row = d.over.r
    rack.grid_col = d.over.c
    updates.push({ id: rack.id, grid_row: rack.grid_row, grid_col: rack.grid_col })
    await persist(updates)
  } else if (rack && !d.moved) {
    goRack(rack) // 点击 = 查看
  }
  drag.value = { id: null, dx: 0, dy: 0, over: null, startX: 0, startY: 0, moved: false }
}
async function persist(updates) {
  if (!updates.length) return
  saving.value = true
  try {
    await rackApi.updatePositions({ positions: updates })
    emit('updated')
  } catch (err) {
    // 失败回滚：重新拉取最新坐标
    await loadRacks()
  } finally {
    saving.value = false
  }
}

async function resetLayout() {
  const byCol = {}
  racks.value.forEach((r) => {
    ;(byCol[r.column_code] ||= []).push(r)
  })
  const colOrder = Object.keys(byCol).sort()
  const updates = []
  colOrder.forEach((col, ri) => {
    byCol[col]
      .sort((a, b) => String(a.code).localeCompare(String(b.code), undefined, { numeric: true }))
      .forEach((r, ci) => {
        r.grid_row = ri
        r.grid_col = ci
        updates.push({ id: r.id, grid_row: ri, grid_col: ci })
      })
  })
  await persist(updates)
}

// ---------------------------------------------------------------- 导航 / 操作
function goRack(rack) {
  router.push(`/racks/${rack.id}`)
}
function go3D() {
  router.push('/3d?room=' + props.roomId)
}

async function loadRacks() {
  const data = await rackApi.list({ room_id: props.roomId, size: 500 })
  racks.value = (data.items || []).map((r) => ({
    ...r,
    grid_row: r.grid_row ?? 0,
    grid_col: r.grid_col ?? 0,
  }))
}
// ---------------------------------------------------------------- 滚动：悬停平面图时滚轮转横向
// 机柜多时平面图横向溢出，默认滚轮为纵向滚动无法浏览。悬停背景区时将纵向 deltaY
// 转为横向 scrollLeft，移出后恢复浏览器默认纵向滚动（仅在确有横向溢出时拦截）。
function onWheel(e) {
  const el = scrollRef.value
  if (!el) return
  if (el.scrollWidth > el.clientWidth + 1) {
    const delta = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX
    el.scrollLeft += delta
    e.preventDefault()
  }
}
function onEnter() {
  const el = scrollRef.value
  if (!el || el._wheelBound) return
  el.addEventListener('wheel', onWheel, { passive: false })
  el._wheelBound = true
}
function onLeave() {
  const el = scrollRef.value
  if (!el || !el._wheelBound) return
  el.removeEventListener('wheel', onWheel)
  el._wheelBound = false
}

onMounted(async () => {
  loading.value = true
  try {
    await loadRacks()
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  const el = scrollRef.value
  if (el && el._wheelBound) {
    el.removeEventListener('wheel', onWheel)
    el._wheelBound = false
  }
})
</script>
