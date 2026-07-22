<script setup>
import { SelectTrigger, SelectValue, SelectIcon } from 'reka-ui'
import { ChevronDown } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  placeholder: { type: String, default: '' },
})
</script>

<template>
  <SelectTrigger
    :class="
      cn(
        'flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 focus:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1 [&>span]:flex [&>span]:items-center',
        props.class
      )
    "
  >
    <SelectValue :placeholder="placeholder" />
    <SelectIcon>
      <ChevronDown class="h-4 w-4 opacity-60" />
    </SelectIcon>
  </SelectTrigger>
</template>
