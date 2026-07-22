<script setup>
import { DropdownMenuRoot, DropdownMenuTrigger } from 'reka-ui'
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger as-child>
      <slot name="trigger" />
    </DropdownMenuTrigger>
    <slot />
  </DropdownMenuRoot>
</template>
