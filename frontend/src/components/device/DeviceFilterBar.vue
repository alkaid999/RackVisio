<script setup>
import { computed } from 'vue'
import Input from '@/components/ui/input.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Button from '@/components/ui/button.vue'
import { Search, Filter, RotateCcw } from 'lucide-vue-next'

// 统一筛选条：设备名称 / 设备类型。
// 通过 modelValue 对象与父级双向同步，多个使用处共享同一筛选状态即「统一筛选」。
// reka-ui 的 SelectItem 不接受空字符串值，故用 __ALL__ 哨兵代表「全部」。
const props = defineProps({
  modelValue: { type: Object, required: true },
  typeOptions: { type: Array, default: () => [] }, // [{value,label}]
})
const emit = defineEmits(['update:modelValue'])

const SENTINEL = '__ALL__'

const kw = computed({
  get: () => props.modelValue.keyword || '',
  set: (v) => patch({ keyword: v }),
})
const selType = computed({
  get: () => props.modelValue.type || SENTINEL,
  set: (v) => patch({ type: v === SENTINEL ? '' : v }),
})

function patch(p) {
  emit('update:modelValue', { ...props.modelValue, ...p })
}
function reset() {
  emit('update:modelValue', { keyword: '', type: '' })
}
const hasActive = computed(
  () => !!(props.modelValue.keyword || props.modelValue.type),
)
</script>

<template>
  <div class="device-filter-bar flex flex-wrap items-center gap-2 rounded-lg border border-border/70 bg-muted/30 px-2.5 py-2">
    <span class="flex items-center gap-1 text-xs font-medium text-slate-500">
      <Filter class="h-3.5 w-3.5" />筛选
    </span>
    <div class="relative">
      <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
      <Input v-model="kw" placeholder="设备名称" class="w-40 pl-8" />
    </div>
    <Select v-model="selType">
      <SelectTrigger class="w-32" placeholder="设备类型" />
      <SelectContent>
        <SelectItem :value="SENTINEL">全部类型</SelectItem>
        <SelectItem v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</SelectItem>
      </SelectContent>
    </Select>
    <Button v-if="hasActive" variant="ghost" size="sm" class="text-slate-500" @click="reset">
      <RotateCcw class="h-3.5 w-3.5" />重置
    </Button>
  </div>
</template>
