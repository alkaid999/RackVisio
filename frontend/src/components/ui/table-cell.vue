<script setup>
import { cn } from '@/lib/utils'
const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <td :class="cn('p-3 align-middle', props.class)"><slot /></td>
</template>
