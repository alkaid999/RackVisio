<template>
  <!-- 整体布局：无外框，靠留白与分层营造空间感；明暗主题平滑过渡 -->
  <TooltipProvider :delay-duration="200">
    <!-- 全屏独立页（如登录页）不套用侧边栏/顶栏布局 -->
    <router-view v-if="isFullscreen" />

    <div v-else class="flex h-screen overflow-hidden bg-background text-foreground">
      <!-- 侧边栏（桌面端，可折叠为图标轨） -->
      <aside
        class="relative z-40 hidden shrink-0 bg-card/60 backdrop-blur-sm transition-all duration-300 ease-out border-r border-border/60 lg:flex lg:flex-col"
        :class="collapsed ? 'w-16' : 'w-64'"
      >
        <div class="flex h-full w-full flex-col">
          <!-- 品牌 -->
          <div
            class="flex h-16 items-center gap-2.5 px-5"
            :class="collapsed ? 'justify-center px-0' : 'px-5'"
          >
            <div
              class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/70 text-white shadow-glow"
            >
              <RackLogo class="h-5 w-5" />
            </div>
            <span v-if="!collapsed" class="text-[15px] font-semibold tracking-wide">RackVisio</span>
          </div>

          <SidebarNav :collapsed="collapsed" class="flex-1 overflow-y-auto scroll-thin" @expand="collapsed = false" />

          <!-- 折叠 / 展开开关 -->
          <div class="border-t border-border/60 p-3">
            <Button
              variant="ghost"
              size="sm"
              class="w-full justify-start text-muted-foreground"
              :class="collapsed ? 'justify-center' : 'justify-start'"
              @click="collapsed = !collapsed"
            >
              <PanelLeftClose v-if="!collapsed" class="h-4 w-4" />
              <PanelLeft v-else class="h-4 w-4" />
              <span v-if="!collapsed" class="ml-1">收起侧栏</span>
            </Button>
          </div>
        </div>
      </aside>

      <!-- 主区 -->
      <div class="flex min-w-0 flex-1 flex-col">
        <!-- 顶栏 -->
        <header
          class="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border/60 bg-background/80 px-4 backdrop-blur sm:px-6"
        >
          <div class="flex min-w-0 items-center gap-2">
            <Button variant="ghost" size="icon" class="lg:hidden" aria-label="打开菜单" @click="mobileOpen = true">
              <Menu class="h-5 w-5" />
            </Button>
            <Breadcrumb />
          </div>

          <div class="flex shrink-0 items-center gap-1.5">
            <Button variant="ghost" size="icon" aria-label="刷新" @click="reload">
              <RefreshCw class="h-4 w-4" />
            </Button>
            <ThemeToggle />

            <!-- 用户菜单 -->
            <DropdownMenu>
              <template #trigger>
                <button
                  class="flex items-center gap-2 rounded-full p-0.5 pl-1 transition hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="用户菜单"
                >
                  <Avatar size="sm" class="font-semibold ring-2 ring-primary/20" :style="{ backgroundColor: avatarColor + '22', color: avatarColor }">{{ avatarText }}</Avatar>
                </button>
              </template>
              <DropdownMenuContent align="end" class="w-52">
                <DropdownMenuLabel>
                  <div class="flex flex-col">
                    <span class="text-sm font-medium">{{ auth.userName }}</span>
                    <span class="text-xs text-muted-foreground">{{ auth.user?.role_label || '—' }}</span>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                  @select="onLogout"
                >
                  <LogOut class="h-4 w-4" />退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <!-- 内容区 -->
        <main class="relative flex-1 overflow-y-auto overflow-x-hidden scroll-thin page-pad">
          <router-view v-slot="{ Component }">
            <Transition name="page">
              <component :is="Component" />
            </Transition>
          </router-view>
        </main>
      </div>
    </div>

    <!-- 移动端导航（抽屉） -->
    <Sheet v-model="mobileOpen" side="left" title="导航">
      <div class="flex h-full flex-col">
        <div class="mb-2 flex items-center gap-2.5 px-1">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/70 text-white">
            <RackLogo class="h-5 w-5" />
          </div>
          <span class="text-[15px] font-semibold">RackVisio</span>
        </div>
        <SidebarNav :collapsed="false" class="flex-1 overflow-y-auto scroll-thin" @expand="mobileOpen = false" />
      </div>
    </Sheet>

    <!-- 全局浮层 -->
    <Toaster />
    <ConfirmDialog />
  </TooltipProvider>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TooltipProvider } from 'reka-ui'
import { Menu, PanelLeftClose, PanelLeft, RefreshCw, LogOut } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import SidebarNav from '@/components/layout/sidebar-nav.vue'
import Breadcrumb from '@/components/common/Breadcrumb.vue'
import ThemeToggle from '@/components/ui/theme-toggle.vue'
import Button from '@/components/ui/button.vue'
import Avatar from '@/components/ui/avatar.vue'
import RackLogo from '@/components/RackLogo.vue'
import DropdownMenu from '@/components/ui/dropdown-menu.vue'
import DropdownMenuContent from '@/components/ui/dropdown-menu-content.vue'
import DropdownMenuItem from '@/components/ui/dropdown-menu-item.vue'
import DropdownMenuLabel from '@/components/ui/dropdown-menu-label.vue'
import DropdownMenuSeparator from '@/components/ui/dropdown-menu-separator.vue'
import Sheet from '@/components/ui/sheet.vue'
import Toaster from '@/components/ui/toaster.vue'
import ConfirmDialog from '@/components/ui/confirm-dialog.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const meta = useMetaStore()

// 应用启动后拉取界面元数据（标签 / 颜色 / 阈值），登录态变更时补全。
function ensureMeta() {
  if (auth.isLoggedIn && !meta.loaded) meta.load()
}
onMounted(ensureMeta)
watch(() => auth.isLoggedIn, ensureMeta)

// 全屏独立页（如 /login）：不渲染侧边栏与顶栏布局。
const isFullscreen = computed(() => !!route.meta.fullscreen)

const collapsed = ref(false)
const mobileOpen = ref(false)

// 字母头像：由姓名生成首字母（英文多词取前两个词首字母，中文取首字），并按姓名哈希取确定性配色。
const AVATAR_PALETTE = [
  '#2563eb', '#7c3aed', '#0ea5e9', '#16a34a', '#d97706',
  '#db2777', '#0891b2', '#ca8a04', '#4f46e5', '#dc2626',
]
function initialsOf(name) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return parts[0].charAt(0).toUpperCase()
}
const avatarText = computed(() => initialsOf(auth.userName || auth.user?.username || ''))
const avatarColor = computed(() => {
  const key = auth.userName || auth.user?.username || '?'
  let h = 0
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0
  return AVATAR_PALETTE[h % AVATAR_PALETTE.length]
})

function reload() {
  window.location.reload()
}

async function onLogout() {
  auth.logout()
  router.replace('/login')
}
</script>
