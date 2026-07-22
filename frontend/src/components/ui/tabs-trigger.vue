<script setup>
import { TabsTrigger } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps({
  value: { type: [String, Number], required: true },
  class: { type: null, required: false },
})
</script>

<template>
  <TabsTrigger
    :value="value"
    :class="
      cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-soft',
        props.class
      )
    "
  >
    <slot />
  </TabsTrigger>
</template>
