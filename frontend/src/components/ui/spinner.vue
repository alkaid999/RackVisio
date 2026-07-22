<script setup>
import { Loader2 } from 'lucide-vue-next'
import { cn } from '@/lib/utils'
const props = defineProps({ class: { type: null, required: false } })
</script>

<template>
  <Loader2 :class="cn('h-4 w-4 animate-spin', props.class)" />
</template>
