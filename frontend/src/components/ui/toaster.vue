<script setup>
import { toasts, dismiss } from '@/composables/useToast'
import { CheckCircle2, XCircle, AlertTriangle, Info, Loader2, X } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

const meta = {
  success: { icon: CheckCircle2, cls: 'text-success' },
  error: { icon: XCircle, cls: 'text-destructive' },
  warning: { icon: AlertTriangle, cls: 'text-warning' },
  info: { icon: Info, cls: 'text-primary' },
  default: { icon: Info, cls: 'text-primary' },
  loading: { icon: Loader2, cls: 'text-primary animate-spin' },
}
</script>

<template>
  <div class="pointer-events-none fixed top-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
    <TransitionGroup name="toast" tag="div" class="flex flex-col gap-2">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="pointer-events-auto flex items-start gap-3 rounded-xl border border-border bg-card/95 p-4 shadow-card backdrop-blur animate-slide-in-right"
      >
        <component
          :is="(meta[t.variant] || meta.default).icon"
          :class="cn('mt-0.5 h-5 w-5 shrink-0', (meta[t.variant] || meta.default).cls)"
        />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-foreground">{{ t.title }}</p>
          <p v-if="t.description" class="mt-0.5 text-sm text-muted-foreground">{{ t.description }}</p>
        </div>
        <button
          class="shrink-0 rounded-md p-0.5 text-muted-foreground transition hover:bg-accent hover:text-foreground"
          @click="dismiss(t.id)"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(24px);
}
.toast-move {
  transition: transform 0.25s ease;
}
</style>
