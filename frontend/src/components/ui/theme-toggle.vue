<script setup>
import { useTheme } from '@/composables/useTheme'
import { Sun, Moon, Monitor, Check } from 'lucide-vue-next'
import DropdownMenu from './dropdown-menu.vue'
import DropdownMenuContent from './dropdown-menu-content.vue'
import DropdownMenuItem from './dropdown-menu-item.vue'
import DropdownMenuLabel from './dropdown-menu-label.vue'
import DropdownMenuSeparator from './dropdown-menu-separator.vue'
import Button from './button.vue'

const { theme, isDark, setTheme } = useTheme()
const modes = [
  { value: 'light', label: '浅色', icon: Sun },
  { value: 'dark', label: '深色', icon: Moon },
  { value: 'system', label: '跟随系统', icon: Monitor },
]
</script>

<template>
  <DropdownMenu>
    <template #trigger>
      <Button variant="ghost" size="icon" :aria-label="isDark ? '切换为浅色' : '切换为深色'">
        <Sun v-if="!isDark" class="h-5 w-5 transition-transform duration-300" />
        <Moon v-else class="h-5 w-5 transition-transform duration-300" />
      </Button>
    </template>
    <DropdownMenuContent align="end" class="w-44">
      <DropdownMenuLabel>外观模式</DropdownMenuLabel>
      <DropdownMenuSeparator />
      <DropdownMenuItem v-for="m in modes" :key="m.value" @click="setTheme(m.value)" class="justify-between">
        <span class="flex items-center gap-2">
          <component :is="m.icon" class="h-4 w-4" />
          {{ m.label }}
        </span>
        <Check v-if="theme === m.value" class="h-4 w-4 text-primary" />
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
