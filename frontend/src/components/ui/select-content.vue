<script setup>
import { SelectPortal, SelectContent, SelectViewport } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  position: { type: String, default: 'popper' },
})
</script>

<template>
  <SelectPortal>
    <SelectContent
      :position="position"
      :class="
        cn(
          'relative z-[90] max-h-96 min-w-[8rem] overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-card data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
          props.class
        )
      "
    >
      <SelectViewport class="p-1">
        <slot />
      </SelectViewport>
    </SelectContent>
  </SelectPortal>
</template>
