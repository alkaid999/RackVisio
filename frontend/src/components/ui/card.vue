<script setup>
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  hover: { type: Boolean, default: false },
})
</script>

<template>
  <div
    :class="
      cn(
        'rounded-xl border border-border bg-card text-card-foreground shadow-soft transition-all duration-300 ease-out',
        props.hover && 'hover:shadow-card-hover hover:-translate-y-0.5',
        props.class
      )
    "
  >
    <div
      v-if="title || description || $slots.header || $slots['header-actions']"
      class="flex items-start justify-between gap-3 p-5 pb-0"
    >
      <div class="space-y-1 min-w-0">
        <h3 v-if="title" class="text-base font-semibold leading-none tracking-tight">{{ title }}</h3>
        <p v-if="description" class="text-sm text-muted-foreground">{{ description }}</p>
        <slot name="header" />
      </div>
      <div v-if="$slots['header-actions']" class="shrink-0 flex items-center gap-1">
        <slot name="header-actions" />
      </div>
    </div>

    <div :class="cn('p-5', { 'pt-4': title || description || $slots.header })">
      <slot />
    </div>

    <div v-if="$slots.footer" class="p-5 pt-0">
      <slot name="footer" />
    </div>
  </div>
</template>
