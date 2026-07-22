<script setup>
import { DropdownMenuPortal, DropdownMenuContent } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  align: { type: String, default: 'center' },
  sideOffset: { type: Number, default: 6 },
})
</script>

<template>
  <DropdownMenuPortal>
    <DropdownMenuContent
      :align="align"
      :side-offset="sideOffset"
      :class="
        cn(
          'z-50 min-w-[10rem] overflow-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-card data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
          props.class
        )
      "
    >
      <slot />
    </DropdownMenuContent>
  </DropdownMenuPortal>
</template>
