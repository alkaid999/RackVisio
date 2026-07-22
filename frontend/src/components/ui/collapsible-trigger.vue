<script setup>
import { CollapsibleTrigger } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <CollapsibleTrigger :class="cn('cursor-pointer', props.class)">
    <slot />
  </CollapsibleTrigger>
</template>
