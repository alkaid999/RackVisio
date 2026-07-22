<script setup>
import { TabsContent } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps({
  value: { type: [String, Number], required: true },
  class: { type: null, required: false },
})
</script>

<template>
  <TabsContent :value="value" :class="cn('mt-3 focus-visible:outline-none', props.class)">
    <slot />
  </TabsContent>
</template>
