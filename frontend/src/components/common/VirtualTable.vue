<template>
  <div class="virtual-table flex flex-col overflow-hidden rounded-xl border border-border/60 bg-card/40" role="table" :aria-rowcount="rows.length">
    <!-- 表头：与行共享 grid-template-columns，纵向不滚动、列宽始终对齐 -->
    <!-- L-06：虚拟表格非语义化的最小补救——表头给 columnheader 角色、行给 row -->
    <div
      class="vt-header grid shrink-0 border-b border-border/70 bg-muted/50 text-xs font-medium text-muted-foreground"
      :style="{ gridTemplateColumns }"
      role="row"
    >
      <div v-if="selectable" class="vt-cell flex items-center justify-center px-2 py-2.5" role="columnheader">
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
        role="columnheader"
      >
        {{ col.label }}
      </div>
    </div>

    <!-- 滚动容器：虚拟化模式限高 + 内部滚动；非虚拟化模式高度自适应、整页滚动无独立滚动条 -->
    <div ref="scrollEl" class="vt-scroll scroll-thin" :class="scrollClass" :style="scrollStyle">
      <!-- 加载态 -->
      <div v-if="loading" class="flex h-full items-center justify-center">
        <Spinner class="h-6 w-6 text-primary" />
      </div>
      <!-- 空态 -->
      <div v-else-if="!rows.length" class="flex h-full items-center justify-center">
        <EmptyState :title="emptyText" />
      </div>
      <!-- 行（虚拟化 / 非虚拟化统一列表） -->
      <div v-else class="vt-inner relative w-full" :style="{ height: props.virtual ? totalSize + 'px' : 'auto' }">
        <div
          v-for="item in displayItems"
          :key="keyOf(item.row)"
          :data-index="item.index"
          :ref="props.virtual ? (el) => setRowRef(el, item.index) : undefined"
          class="vt-row group grid items-center border-b border-border/50 transition-colors hover:bg-accent/40"
          :class="rowClass ? rowClass(item.row, item.index) : ''"
          role="row"
          :style="props.virtual ? {
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            transform: `translateY(${item.start}px)`,
            gridTemplateColumns,
          } : { position: 'relative', gridTemplateColumns }"
        >
          <div v-if="selectable" class="vt-cell flex items-center justify-center px-2">
            <Checkbox
              :model-value="isSelected(item.row)"
              aria-label="选择行"
              @update:model-value="() => emit('toggle-row', keyOf(item.row))"
            />
          </div>
          <slot name="row" :row="item.row" :index="item.index" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
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
  // 是否启用虚拟滚动（窗口化）。false 时直接渲染全部行、容器随内容撑开，
  // 整页跟随浏览器滚动，无内部独立滚动条（适合已分页、单页行数可控的场景）。
  virtual: { type: Boolean, default: true },
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

// 关键：整个 options 必须包进 computed（而非只给 count 包 computed / 直接写 props.rows.length）。
// 原因：@tanstack/vue-virtual 内部用 watch(() => unref(options), ...) 来感知变化并 setOptions。
//  - 若只写 count: computed(() => props.rows.length)：展开 options 时拿的是 ref 对象本身，
//    virtual-core 读 this.options.count 不会 unref，ref-1=NaN → defaultRangeExtractor 里
//    new Array(NaN) 抛 RangeError（被 ErrorBoundary 吞掉 → 整片表格空白）。
//  - 若写 count: props.rows.length：对象字面量在 setup 时只快照了初始值 0，行数变化后
//    watch 不触发，virtualizer 的 count 永远是 0 → 不渲染任何行。
// 把整个 options 包成 computed，unref(options) 每次都会重新读取 props.rows.length，
// 从而正确追踪响应式并在数据到达后更新 count。
const virtualizer = useVirtualizer(
  computed(() => ({
    count: props.rows.length,
    getScrollElement: () => scrollEl.value,
    estimateSize: () => props.rowHeight,
    overscan: 10,
  }))
)

const virtualRows = computed(() => virtualizer.value.getVirtualItems())
const totalSize = computed(() => virtualizer.value.getTotalSize())

// 虚拟化 / 非虚拟化统一渲染列表：
// - 虚拟化：取虚拟窗口内的可见行，带 start 偏移用于绝对定位。
// - 非虚拟化：直接展开全部行、start=0，容器高度自适应，整页滚动无独立滚动条。
const displayItems = computed(() => {
  if (props.virtual) {
    return virtualRows.value.map((vr) => ({ row: props.rows[vr.index], index: vr.index, start: vr.start }))
  }
  return props.rows.map((row, index) => ({ row, index, start: 0 }))
})
const scrollStyle = computed(() =>
  props.virtual ? { height: props.height + 'px' } : {}
)
const scrollClass = computed(() =>
  props.virtual ? 'overflow-y-auto overflow-x-hidden' : 'overflow-visible'
)

// 动态测量：把每个行元素交给 virtualizer 测量真实高度（支持变高行）。
function setRowRef(el) {
  if (el) virtualizer.value.measureElement(el)
}

onBeforeUnmount(() => {
  virtualizer.value?.destroy?.()
})
</script>

<style scoped>
.vt-cell {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.vt-row > :deep(.vt-cell),
.vt-row > :deep(div) {
  min-width: 0;
}
</style>
