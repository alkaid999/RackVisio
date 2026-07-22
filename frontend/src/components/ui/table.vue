<script setup>
import { cn } from '@/lib/utils'
const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <div class="relative w-full overflow-x-auto scroll-thin">
    <table :class="cn('w-full caption-bottom text-sm', props.class)"><slot /></table>
  </div>
</template>
