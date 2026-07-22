<script setup>
import { cn } from '@/lib/utils'
const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <kbd
    :class="
      cn(
        'pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground',
        props.class
      )
    "
  ><slot /></kbd>
</template>
