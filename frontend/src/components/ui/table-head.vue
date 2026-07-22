<script setup>
import { cn } from '@/lib/utils'
const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <th :class="cn('h-10 px-3 text-left align-middle font-medium text-muted-foreground whitespace-nowrap', props.class)">
    <slot />
  </th>
</template>
