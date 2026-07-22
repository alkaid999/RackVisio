<template>
  <div class="list-pager">
    <span class="list-pager__text">共 {{ total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
    <div class="flex items-center gap-2">
      <Button variant="outline" size="icon-sm" :disabled="page <= 1" @click="go(page - 1)">
        <ChevronLeft class="h-4 w-4" />
      </Button>
      <Button variant="outline" size="icon-sm" :disabled="page >= totalPages" @click="go(page + 1)">
        <ChevronRight class="h-4 w-4" />
      </Button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'

const props = defineProps({
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 },
})
const emit = defineEmits(['change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

// 翻页：先校验边界，再抛出 change 事件由父组件请求对应页数据。
function go(p) {
  if (p < 1 || p > totalPages.value) return
  emit('change', p)
}
</script>

<style scoped>
.list-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
}
.list-pager__text {
  font-size: 13px;
  color: #606266;
}
</style>
