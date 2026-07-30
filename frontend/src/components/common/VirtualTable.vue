<template>
  <div class="virtual-table flex flex-col overflow-hidden rounded-xl border border-border/60 bg-card/40">
    <!-- 表头：与行共享 grid-template-columns，纵向不滚动、列宽始终对齐 -->
    <div
      class="vt-header grid shrink-0 border-b border-border/70 bg-muted/50 text-xs font-medium text-muted-foreground"
      :style="{ gridTemplateColumns }"
    >
      <div v-if="selectable" class="vt-cell flex items-center justify-center px-2 py-2.5">
        <Checkbox
          :model-value="allSelected"
          :indeterminate="indeterminate"
          aria-label="全选本页"
          @update:model-value="(v) => emit('toggle-all', v)"
        />
      </div>
      <div
        v-for="col in columns"
        :key="col.key"
        class="vt-cell px-3 py-2.5"
        :class="col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''"
      >
        {{ col.label }}
      </div>
    </div>

    <!-- 滚动容器：仅纵向滚动窗口化，行绝对定位 + transform 偏移 -->
    <div ref="scrollEl" class="vt-scroll scroll-thin overflow-y-auto overflow-x-hidden" :style="{ height: height + 'px' }">
      <!-- 加载态 -->
      <div v-if="loading" class="flex h-full items-center justify-center">
        <Spinner class="h-6 w-6 text-primary" />
      </div>
      <!-- 空态 -->
      <div v-else-if="!rows.length" class="flex h-full items-center justify-center">
        <EmptyState :title="emptyText" />
      </div>
      <!-- 虚拟行 -->
      <div v-else class="vt-inner relative w-full" :style="{ height: totalSize + 'px' }">
        <div
          v-for="vRow in virtualRows"
          :key="keyOf(rows[vRow.index])"
          :data-index="vRow.index"
          :ref="(el) => setRowRef(el, vRow.index)"
          class="vt-row group grid items-center border-b border-border/50 transition-colors hover:bg-accent/40"
          :class="rowClass ? rowClass(rows[vRow.index], vRow.index) : ''"
          :style="{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            transform: `translateY(${vRow.start}px)`,
            gridTemplateColumns,
          }"
        >
          <div v-if="selectable" class="vt-cell flex items-center justify-center px-2">
            <Checkbox
              :model-value="isSelected(rows[vRow.index])"
              aria-label="选择行"
              @update:model-value="() => emit('toggle-row', keyOf(rows[vRow.index]))"
            />
          </div>
          <slot name="row" :row="rows[vRow.index]" :index="vRow.index" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useVirtualizer } from '@tanstack/vue-virtual'
import Checkbox from '@/components/ui/checkbox.vue'
import Spinner from '@/components/ui/spinner.vue'
import EmptyState from '@/components/ui/empty-state.vue'

const props = defineProps({
  // 列定义：{ key, label, width?, align?: 'left'|'right'|'center' }
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  // 行高估计（动态测量会按需覆盖，故可为近似值）
  rowHeight: { type: Number, default: 52 },
  // 滚动容器高度（px）
  height: { type: Number, default: 560 },
  keyField: { type: String, default: 'id' },
  // 是否渲染选择列（表头全选 + 行勾选）
  selectable: { type: Boolean, default: false },
  selectedKeys: { type: Array, default: () => [] },
  allSelected: { type: Boolean, default: false },
  indeterminate: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无数据' },
  // 行容器附加 class 回调：(row, index) => string
  rowClass: { type: Function, default: null },
})

const emit = defineEmits(['toggle-row', 'toggle-all'])

const scrollEl = ref(null)

// 选择列 + 数据列的完整 grid 模板；列宽缺省 1fr。
const gridTemplateColumns = computed(() => {
  const base = props.columns.map((c) => c.width || '1fr').join(' ')
  return props.selectable ? `44px ${base}` : base
})

function keyOf(row) {
  return row?.[props.keyField]
}
function isSelected(row) {
  const k = keyOf(row)
  return props.selectedKeys.includes(k)
}

const virtualizer = useVirtualizer({
  count: computed(() => props.rows.length),
  getScrollElement: () => scrollEl.value,
  estimateSize: () => props.rowHeight,
  overscan: 10,
})

const virtualRows = computed(() => virtualizer.value.getVirtualItems())
const totalSize = computed(() => virtualizer.value.getTotalSize())

// 动态测量：把每个行元素交给 virtualizer 测量真实高度（支持变高行）。
function setRowRef(el) {
  if (el) virtualizer.value.measureElement(el)
}

// 数据量变化后强制重新测量，避免缓存旧高度导致错位。
watch(
  () => props.rows.length,
  () => {
    virtualizer.value.measure()
  }
)

onBeforeUnmount(() => {
  virtualizer.value?.destroy?.()
})
</script>

<style scoped>
.vt-cell {
  min-width: 0;
  overflow: hidden;
}
.vt-row > :deep(.vt-cell),
.vt-row > :deep(div) {
  min-width: 0;
}
</style>
