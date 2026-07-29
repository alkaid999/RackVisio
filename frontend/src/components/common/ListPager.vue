<template>
  <div class="list-pager">
    <!-- 状态展示：当前页 / 总页数 / 总条数 -->
    <div class="list-pager__info">
      共 <b class="list-pager__num">{{ total }}</b> 条 · 第
      <b class="list-pager__num">{{ page }}</b> / {{ totalPages }} 页
    </div>

    <div class="list-pager__controls">
      <!-- 首页 -->
      <Button variant="outline" size="icon-sm" :disabled="page <= 1" title="首页" @click="go(1)">
        首
      </Button>
      <!-- 上一页 -->
      <Button variant="outline" size="icon-sm" :disabled="page <= 1" title="上一页" @click="go(page - 1)">
        <ChevronLeft class="h-4 w-4" />
      </Button>

      <!-- 页码按钮组（含省略号折叠） -->
      <template v-for="(p, i) in pageItems" :key="'p' + i">
        <span v-if="p === '...'" class="list-pager__ellipsis">…</span>
        <Button
          v-else
          :variant="p === page ? 'default' : 'outline'"
          size="icon-sm"
          :class="['list-pager__page', { 'is-active': p === page }]"
          @click="go(p)"
        >
          {{ p }}
        </Button>
      </template>

      <!-- 下一页 -->
      <Button
        variant="outline"
        size="icon-sm"
        :disabled="page >= totalPages"
        title="下一页"
        @click="go(page + 1)"
      >
        <ChevronRight class="h-4 w-4" />
      </Button>
      <!-- 尾页 -->
      <Button
        variant="outline"
        size="icon-sm"
        :disabled="page >= totalPages"
        title="尾页"
        @click="go(totalPages)"
      >
        尾
      </Button>

      <!-- 自定义页码跳转（带边界校验） -->
      <div class="list-pager__jump">
        <span class="list-pager__jump-label">跳至</span>
        <Input
          type="number"
          min="1"
          :max="totalPages"
          v-model="jumpModel"
          class="list-pager__jump-input"
          :class="{ 'is-invalid': jumpError }"
          @keyup.enter="submitJump"
          @blur="submitJump"
        />
        <span class="list-pager__jump-label">页</span>
        <Button variant="outline" size="sm" :disabled="!!jumpError" @click="submitJump">跳转</Button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'

const props = defineProps({
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 },
})
const emit = defineEmits(['change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

// 页码窗口：总数较小全部展示；较大时以当前页为中心、两侧各留 1 个，其余用省略号折叠。
const pageItems = computed(() => {
  const tp = totalPages.value
  const cur = props.page
  if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1)
  const items = [1]
  const left = Math.max(2, cur - 1)
  const right = Math.min(tp - 1, cur + 1)
  if (left > 2) items.push('...')
  for (let i = left; i <= right; i++) items.push(i)
  if (right < tp - 1) items.push('...')
  items.push(tp)
  return items
})

// 翻页：先校验边界，再抛出 change 事件由父组件请求对应页数据。
function go(p) {
  if (p < 1 || p > totalPages.value) return
  emit('change', p)
}

// —— 自定义跳转 ——
// 注意：Input(type=number) 的 v-model 会被强制转为数值，故 jumpModel 须为 number。
const jumpModel = ref(props.page)
const jumpError = ref(false)

// 父组件切换页码（如筛选/重置）时同步输入框，避免显示与实际不一致。
watch(
  () => props.page,
  (v) => {
    jumpModel.value = v
    jumpError.value = false
  },
)

function submitJump() {
  const n = jumpModel.value
  // 空值 / 非数字：恢复为当前页，不报错。
  if (n === '' || n === null || n === undefined || Number.isNaN(Number(n))) {
    jumpModel.value = props.page
    jumpError.value = false
    return
  }
  const num = Number(n)
  // 越界：标红提示，不抛出 change（输入框保留用户输入以便修正）。
  if (!Number.isInteger(num) || num < 1 || num > totalPages.value) {
    jumpError.value = true
    return
  }
  jumpError.value = false
  // 与当前页相同则仅同步输入框，无需请求。
  if (num !== props.page) emit('change', num)
  jumpModel.value = num
}
</script>

<style scoped>
.list-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding: 10px 14px;
  background: oklch(var(--card) / 0.8);
  border: 1px solid oklch(var(--border) / 0.6);
  border-radius: 10px;
  backdrop-filter: blur(8px);
}
.list-pager__info {
  font-size: 13px;
  color: oklch(var(--muted-foreground));
}
.list-pager__num {
  color: oklch(var(--foreground));
  font-weight: 600;
}
.list-pager__controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.list-pager__page {
  min-width: 32px;
  font-variant-numeric: tabular-nums;
}
.list-pager__page.is-active {
  cursor: default;
}
.list-pager__ellipsis {
  padding: 0 2px;
  color: oklch(var(--muted-foreground));
  user-select: none;
}
.list-pager__jump {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 4px;
}
.list-pager__jump-label {
  font-size: 13px;
  color: oklch(var(--muted-foreground));
}
.list-pager__jump-input {
  width: 56px;
  height: 32px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
/* 越界输入标红（class 直接落在 input 根元素上，无需 :deep） */
.list-pager__jump-input.is-invalid {
  border-color: oklch(var(--destructive));
}
</style>
