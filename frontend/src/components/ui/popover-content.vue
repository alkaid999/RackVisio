<script setup>
import { PopoverPortal, PopoverContent } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  align: { type: String, default: 'center' },
  sideOffset: { type: Number, default: 6 },
})
</script>

<template>
  <PopoverPortal>
    <PopoverContent
      :align="align"
      :side-offset="sideOffset"
      :class="
        cn(
          'z-50 w-72 rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-card outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
          props.class
        )
      "
    >
      <slot />
    </PopoverContent>
  </PopoverPortal>
</template>
