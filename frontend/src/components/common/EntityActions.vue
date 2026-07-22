<template>
  <div
    class="entity-actions flex items-center"
    :class="variant === 'full' ? 'flex-wrap justify-end gap-1' : 'gap-0.5'"
    @click.stop
  >
    <!-- 卡片模式：图标 + 文字（与「耗材列表」卡片一致，删除为红色） -->
    <template v-if="variant === 'full'">
      <Button v-if="showView" variant="ghost" size="sm" @click="$emit('view')">
        <Eye class="h-3.5 w-3.5" />查看
      </Button>
      <Button v-if="showEdit" variant="ghost" size="sm" @click="$emit('edit')">
        <Pencil class="h-3.5 w-3.5" />编辑
      </Button>
      <Button
        v-if="showDelete"
        variant="ghost"
        size="sm"
        class="text-destructive hover:bg-destructive/10"
        @click="$emit('delete')"
      >
        <Trash2 class="h-3.5 w-3.5" />删除
      </Button>
    </template>

    <!-- 表格模式：图标 + tooltip（紧凑，与「耗材列表」表格一致） -->
    <template v-else>
      <Tooltip v-if="showView" side="top">
        <template #trigger>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            @click="$emit('view')"
          ><Eye class="h-3.5 w-3.5" /></button>
        </template>
        查看
      </Tooltip>
      <Tooltip v-if="showEdit" side="top">
        <template #trigger>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            @click="$emit('edit')"
          ><Pencil class="h-3.5 w-3.5" /></button>
        </template>
        编辑
      </Tooltip>
      <Tooltip v-if="showDelete" side="top">
        <template #trigger>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-500"
            @click="$emit('delete')"
          ><Trash2 class="h-3.5 w-3.5" /></button>
        </template>
        删除
      </Tooltip>
      <!-- 扩展动作（如耗材的「历史/变动」），复用同一套紧凑图标按钮样式，保证与各列表表格一致 -->
      <Tooltip v-for="act in visibleExtra" :key="act.key" side="top">
        <template #trigger>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            @click="act.onClick"
          ><component :is="act.icon" class="h-3.5 w-3.5" /></button>
        </template>
        {{ act.label }}
      </Tooltip>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Eye, Pencil, Trash2 } from 'lucide-vue-next'
import Tooltip from '@/components/ui/tooltip.vue'
import Button from '@/components/ui/button.vue'

const props = defineProps({
  showView: { type: Boolean, default: true },
  showEdit: { type: Boolean, default: true },
  showDelete: { type: Boolean, default: true },
  // 'compact' = 图标 + tooltip（表格视图，紧凑）；'full' = 图标 + 文字（卡片视图，与耗材列表一致，删除为红色）
  variant: { type: String, default: 'compact' },
  // 扩展动作：[{ key, label, icon(组件), onClick(), show?(默认 true) }]，表格模式追加渲染，样式与编辑/删除一致
  extraActions: { type: Array, default: () => [] },
})
defineEmits(['view', 'edit', 'delete'])

const visibleExtra = computed(() => (props.extraActions || []).filter((a) => a.show !== false))
</script>
