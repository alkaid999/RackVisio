<template>
  <div class="mx-auto max-w-[1400px] px-4 py-5">
    <!-- 顶栏：返回 / 机房名 / 操作 -->
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <button
        class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
        @click="router.back()"
      >
        <ArrowLeft class="h-4 w-4" /> 返回
      </button>
      <div class="min-w-0">
        <h1 class="truncate text-lg font-semibold text-foreground">机房平面图</h1>
        <p v-if="room" class="truncate text-xs text-muted-foreground">
          {{ room.name }}（{{ room.code }}）· 拖拽机柜调整位置，松手自动保存
        </p>
      </div>
      <div class="ml-auto flex items-center gap-2">
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
    </div>

    <div v-if="loading" class="py-20 text-center text-muted-foreground">加载中…</div>
    <div v-else-if="!racks.length" class="py-20 text-center text-muted-foreground">
      该机房暂无机柜，请先在机房详情中添加机柜。
    </div>

    <div v-else class="flex gap-3 overflow-x-auto pb-4">
      <!-- 左侧行标签（列编号） -->
      <div class="shrink-0 w-16 pt-2" :style="{ height: boardH + 'px' }">
        <div
          v-for="(label, r) in rowLabels"
          :key="'rl-' + r"
          class="flex items-center justify-end pr-2 text-[11px] font-medium text-muted-foreground"
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
      >
        <!-- 网格底纹 -->
        <div class="pointer-events-none absolute inset-0 opacity-[0.5]">
          <div
            v-for="r in bounds.rows"
            :key="'gr-' + r"
            class="absolute left-0 right-0 border-t border-border/40"
            :style="{ top: r * (CELL_H + GAP) - GAP / 2 + 'px' }"
          />
          <div
            v-for="c in bounds.cols"
            :key="'gc-' + c"
            class="absolute top-0 bottom-0 border-l border-border/40"
            :style="{ left: c * (CELL_W + GAP) - GAP / 2 + 'px' }"
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
          class="rack-tile absolute flex select-none flex-col rounded-xl border bg-card p-2.5 shadow-sm transition-shadow"
          :class="[
            drag.id === rack.id ? 'z-50 shadow-xl ring-2 ring-brand-400' : 'hover:shadow-md',
            tileBorder(rack),
          ]"
          :style="tileStyle(rack)"
          @pointerdown="onPointerDown($event, rack)"
        >
          <!-- 悬浮操作 -->
          <div class="absolute right-1.5 top-1.5 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100" data-action>
            <button
              class="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              title="查看"
              data-action
              @click.stop="goRack(rack)"
            ><Eye class="h-3.5 w-3.5" /></button>
            <button
              v-if="canEditRack"
              class="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              title="编辑"
              data-action
              @click.stop="openRackForm(rack)"
            ><Pencil class="h-3.5 w-3.5" /></button>
            <button
              v-if="canEditRack"
              class="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-red-50 hover:text-red-500"
              title="删除"
              data-action
              @click.stop="removeRack(rack)"
            ><Trash2 class="h-3.5 w-3.5" /></button>
          </div>

          <!-- 机柜外观：竖向 U 位条纹 -->
          <div class="rack-vis mb-2 mt-1 flex-1 rounded-md border border-border/60 bg-gradient-to-b from-muted/40 to-muted/10"
               :style="{ backgroundImage: 'repeating-linear-gradient(to bottom, rgba(100,116,139,.18) 0 1px, transparent 1px ' + (CELL_H * 0.42) + 'px)' }" />

          <div class="truncate text-sm font-semibold text-foreground">{{ rack.name }}</div>
          <div class="mt-0.5 flex items-center justify-between gap-1">
            <span class="truncate text-[11px] text-muted-foreground">{{ rack.column_code }} / {{ rack.code }}</span>
            <StatusBadge type="rack" :value="rack.status" />
          </div>
          <div class="mt-1.5 flex items-center gap-1 text-[11px] text-muted-foreground">
            <Ruler class="h-3 w-3" />{{ rack.used_u }}/{{ rack.total_u }}U
          </div>
          <div class="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div class="h-full rounded-full" :style="{ width: util(rack) + '%', backgroundColor: utilColor(rack) }" />
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑机柜：复用统一 RackForm 组件（与列表 / 详情页完全一致，消除重复内联表单） -->
    <RackForm
      v-model:visible="rackFormVisible"
      mode="edit"
      :rack-id="editRackId"
      :locked-room-id="roomId"
      @saved="onRackSaved"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Boxes, Eye, Pencil, RotateCcw, Ruler, Trash2 } from 'lucide-vue-next'
import StatusBadge from '@/components/common/StatusBadge.vue'
import Card from '@/components/ui/card.vue'
import RackForm from '@/views/rack/RackForm.vue'
import rackApi from '@/api/rack'
import roomApi from '@/api/room'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const roomId = route.params.id
// 机柜相关写操作（编辑 / 删除 / 拖拽改坐标 / 重置排列）均需 rack:edit；只读用户隐藏写按钮并禁止拖拽。
const canEditRack = computed(() => auth.hasPermission('rack:edit'))
const meta = useMetaStore()

const CELL_W = 128
const CELL_H = 156
const GAP = 16

const loading = ref(true)
const saving = ref(false)
const room = ref(null)
const racks = ref([])
const boardRef = ref(null)

const bounds = computed(() => {
  let maxR = 0
  let maxC = 0
  for (const r of racks.value) {
    if (r.grid_row != null) maxR = Math.max(maxR, r.grid_row)
    if (r.grid_col != null) maxC = Math.max(maxC, r.grid_col)
  }
  return { rows: Math.max(3, maxR + 2), cols: Math.max(4, maxC + 2) }
})
const boardW = computed(() => bounds.value.cols * (CELL_W + GAP))
const boardH = computed(() => bounds.value.rows * (CELL_H + GAP))

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
    left: c * (CELL_W + GAP) + 'px',
    top: r * (CELL_H + GAP) + 'px',
    width: CELL_W + 'px',
    height: CELL_H + 'px',
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
  if (rack.status === '维护中') return 'border-amber-300'
  if (rack.status === '空调柜' || rack.status === '电柜') return 'border-sky-300'
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
  if (e.target.closest('[data-action]')) return
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
  let c = Math.floor((e.clientX - rect.left) / (CELL_W + GAP))
  let r = Math.floor((e.clientY - rect.top) / (CELL_H + GAP))
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
  router.push('/3d?room=' + roomId)
}
function openRackForm(rack) {
  editRackId.value = rack.id
  rackFormVisible.value = true
}
async function onRackSaved() {
  // 编辑保存后刷新平面图机柜列表，使名称 / 状态等即时更新
  await loadRacks()
}
async function removeRack(rack) {
  if (!confirm(`确认删除机柜「${rack.name}」？`)) return
  saving.value = true
  try {
    await rackApi.remove(rack.id)
    racks.value = racks.value.filter((x) => x.id !== rack.id)
  } finally {
    saving.value = false
  }
}

const rackFormVisible = ref(false)
const editRackId = ref('')

async function loadRacks() {
  const data = await rackApi.list({ room_id: roomId, size: 500 })
  racks.value = (data.items || []).map((r) => ({
    ...r,
    grid_row: r.grid_row ?? 0,
    grid_col: r.grid_col ?? 0,
  }))
}
onMounted(async () => {
  loading.value = true
  try {
    room.value = await roomApi.get(roomId)
    await loadRacks()
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})
</script>
