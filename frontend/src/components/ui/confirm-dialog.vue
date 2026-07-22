<script setup>
import { useConfirm } from '@/composables/useConfirm'
import { AlertTriangle, AlertOctagon, Info } from 'lucide-vue-next'
import { cn } from '@/lib/utils'
import Dialog from './dialog.vue'
import Button from './button.vue'
import Spinner from './spinner.vue'

const { state, onConfirm, onCancel } = useConfirm()

const iconMap = {
  warning: { icon: AlertTriangle, cls: 'bg-warning/15 text-warning' },
  danger: { icon: AlertOctagon, cls: 'bg-destructive/15 text-destructive' },
  default: { icon: Info, cls: 'bg-primary/15 text-primary' },
}
</script>

<template>
  <Dialog v-model="state.open" :title="state.title" z-index="z-[60]">
    <div class="flex items-start gap-3">
      <span :class="cn('mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full', (iconMap[state.variant] || iconMap.default).cls)">
        <component :is="(iconMap[state.variant] || iconMap.default).icon" class="h-5 w-5" />
      </span>
      <p class="text-sm leading-relaxed text-muted-foreground">{{ state.description }}</p>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button variant="outline" :disabled="state.loading" @click="onCancel">{{ state.cancelText }}</Button>
        <Button :variant="state.variant === 'danger' ? 'destructive' : 'default'" :disabled="state.loading" @click="onConfirm">
          <Spinner v-if="state.loading" />
          {{ state.confirmText }}
        </Button>
      </div>
    </template>
  </Dialog>
</template>
