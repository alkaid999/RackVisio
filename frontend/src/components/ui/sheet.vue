<script setup>
import { DialogRoot, DialogPortal, DialogOverlay, DialogContent, DialogTitle, DialogClose } from 'reka-ui'
import { X } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  side: { type: String, default: 'right' },
  title: { type: String, default: '' },
  class: { type: null, required: false },
})
const emit = defineEmits(['update:modelValue'])

const sides = {
  top: 'inset-x-0 top-0 border-b data-[state=open]:slide-in-from-top',
  bottom: 'inset-x-0 bottom-0 border-t data-[state=open]:slide-in-from-bottom',
  left: 'inset-y-0 left-0 h-full w-3/4 border-r data-[state=open]:slide-in-from-left sm:max-w-sm',
  right: 'inset-y-0 right-0 h-full w-3/4 border-l data-[state=open]:slide-in-from-right sm:max-w-sm',
}
</script>

<template>
  <DialogRoot :open="modelValue" @update:open="(v) => emit('update:modelValue', v)">
    <DialogPortal>
      <DialogOverlay
        class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-fade-in data-[state=closed]:animate-fade-out"
      />
      <DialogContent
        :class="
          cn(
            'fixed z-50 flex flex-col gap-4 bg-card p-6 shadow-card transition ease-in-out data-[state=open]:duration-300 data-[state=closed]:duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out',
            sides[side],
            props.class
          )
        "
      >
        <div class="flex items-center justify-between">
          <DialogTitle v-if="title" class="text-lg font-semibold tracking-tight">{{ title }}</DialogTitle>
          <DialogTitle v-else class="sr-only">面板</DialogTitle>
          <DialogClose
            class="rounded-md p-1 text-muted-foreground opacity-70 transition hover:opacity-100 hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X class="h-4 w-4" />
            <span class="sr-only">关闭</span>
          </DialogClose>
        </div>
        <slot />
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
