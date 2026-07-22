<script setup>
import { CollapsibleContent } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <CollapsibleContent
    :class="
      cn(
        'overflow-hidden transition-all data-[state=open]:animate-accordion-down data-[state=closed]:animate-accordion-up',
        props.class
      )
    "
  >
    <slot />
  </CollapsibleContent>
</template>
