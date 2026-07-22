<script setup>
import { reactive, computed, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  LayoutDashboard,
  Building2,
  Cpu,
  Share2,
  ChevronRight,
  Server,
  Boxes,
  Rows3,
  Box,
  Settings,
  UserCog,
  Package,
  History,
} from 'lucide-vue-next'

const props = defineProps({ collapsed: { type: Boolean, default: false } })
const emit = defineEmits(['expand'])

const route = useRoute()
const auth = useAuthStore()

// 导航定义。带 `permission` 的项仅在当前用户具备该权限时显示；
// 分组的子项全部不可见时，该分组整体隐藏。
const nav = [
  { to: '/dashboard', label: '仪表盘', icon: LayoutDashboard },
  {
    label: '基础设施',
    icon: Building2,
    children: [
      { to: '/rooms', label: '机房列表', icon: Server, permission: 'room:view' },
      { to: '/racks', label: '机柜列表', icon: Boxes, permission: 'rack:view' },
      { to: '/rack-view', label: '机柜 2D 视图', icon: Rows3, permission: 'rack:view' },
      { to: '/3d', label: '机房 3D 总览', icon: Box, permission: 'room:view' },
    ],
  },
  {
    label: '设备管理',
    icon: Cpu,
    children: [
      { to: '/devices', label: '设备列表', icon: Cpu, permission: 'device:view' },
      { to: '/mount-records', label: '上下架记录', icon: History, permission: 'device:view' },
      { to: '/links', label: '链路管理', icon: Share2, permission: 'link:view' },
      { to: '/consumables', label: '耗材列表', icon: Package, permission: 'consumable:view' },
    ],
  },
  {
    label: '系统管理',
    icon: Settings,
    children: [
      { to: '/accounts', label: '账号管理', icon: UserCog, permission: 'account:view' },
    ],
  },
]

// 按权限过滤后的可见导航（计算属性，随登录用户变化自动更新）。
const visibleNav = computed(() =>
  nav
    .map((item) => {
      if (item.children) {
        const kids = item.children.filter((c) => !c.permission || auth.hasPermission(c.permission))
        return kids.length ? { ...item, children: kids } : null
      }
      return !item.permission || auth.hasPermission(item.permission) ? item : null
    })
    .filter(Boolean)
)

const open = reactive({})
function syncOpen() {
  visibleNav.value.forEach((g) => {
    if (g.children) open[g.label] = g.children.some((c) => route.path.startsWith(c.to))
  })
}
syncOpen()
watch(() => route.fullPath, syncOpen)

const childActive = (c) => route.path.startsWith(c.to)
const groupActive = (g) => !!g.children?.some(childActive)

function onGroupClick(g) {
  if (props.collapsed) {
    emit('expand')
    open[g.label] = true
  } else {
    open[g.label] = !open[g.label]
  }
}

/* —— 收起态悬浮玻璃面板（teleport 到 body，避开 overflow 裁剪）—— */
const flyout = reactive({ item: null, x: 0, y: 0 })
let hideTimer = null

function clearHideTimer() {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}
function showFlyout(item, el) {
  clearHideTimer()
  const r = el.getBoundingClientRect()
  const cy = Math.max(96, Math.min(window.innerHeight - 96, r.top + r.height / 2))
  flyout.item = item
  flyout.x = r.right + 10
  flyout.y = cy
}
function onRailEnter(item, e) {
  if (props.collapsed) showFlyout(item, e.currentTarget)
}
function onFlyoutEnter() {
  clearHideTimer()
}
function scheduleHide() {
  clearHideTimer()
  hideTimer = setTimeout(() => {
    flyout.item = null
  }, 130)
}

const flyoutStyle = computed(() => ({
  left: `${flyout.x}px`,
  top: `${flyout.y}px`,
}))

onBeforeUnmount(clearHideTimer)
</script>

<template>
  <nav class="flex flex-col gap-1 px-3 py-4">
    <!-- 展开态：分组 + 内联子菜单 -->
    <template v-if="!collapsed">
      <template v-for="item in visibleNav" :key="item.label">
        <!-- 顶级单页 -->
        <RouterLink
          v-if="!item.children"
          :to="item.to"
          class="group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 hover:bg-accent"
          :class="route.path === item.to ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'"
          active-class="!"
        >
          <component :is="item.icon" class="h-5 w-5 shrink-0 transition-transform duration-200 group-hover:scale-110" />
          <span class="truncate">{{ item.label }}</span>
          <span
            v-if="route.path === item.to"
            class="absolute left-0 top-1/4 bottom-1/4 w-[3px] rounded-full bg-primary"
          />
        </RouterLink>

        <!-- 分组 -->
        <div v-else>
          <button
            type="button"
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 hover:bg-accent"
            :class="groupActive(item) ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'"
            @click="onGroupClick(item)"
          >
            <component :is="item.icon" class="h-5 w-5 shrink-0 transition-transform duration-200 group-hover:scale-110" />
            <span class="flex-1 text-left truncate">{{ item.label }}</span>
            <ChevronRight
              class="h-4 w-4 shrink-0 transition-transform duration-300"
              :class="open[item.label] ? 'rotate-90' : ''"
            />
          </button>

          <!-- 子项 -->
          <div
            v-show="open[item.label]"
            class="ml-[26px] mt-0.5 space-y-0.5 border-l border-border pl-3 overflow-hidden"
          >
            <RouterLink
              v-for="c in item.children"
              :key="c.to"
              :to="c.to"
              class="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-all duration-200 hover:bg-accent"
              :class="childActive(c) ? 'bg-primary/10 font-medium text-primary' : 'text-muted-foreground hover:text-foreground'"
            >
              <component :is="c.icon" class="h-4 w-4 shrink-0 opacity-80" />
              <span class="truncate">{{ c.label }}</span>
            </RouterLink>
          </div>
        </div>
      </template>
    </template>

    <!-- 收起态（图标轨） -->
    <template v-else>
      <div
        v-for="item in visibleNav"
        :key="item.label"
        class="rail-item relative flex justify-center py-1"
        @mouseenter="onRailEnter(item, $event)"
        @mouseleave="scheduleHide"
      >
        <!-- 单页：图标直跳 -->
        <RouterLink
          v-if="!item.children"
          :to="item.to"
          class="group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all duration-200 hover:bg-accent"
          :class="route.path === item.to ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'"
          active-class="!"
        >
          <component :is="item.icon" class="h-5 w-5 shrink-0" />
          <span v-if="route.path === item.to" class="sel-bar" />
        </RouterLink>

        <!-- 分组：图标点击展开侧栏，悬停显示悬浮子菜单 -->
        <button
          v-else
          type="button"
          class="group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all duration-200 hover:bg-accent"
          :class="groupActive(item) ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground'"
          @click="onGroupClick(item)"
        >
          <component :is="item.icon" class="h-5 w-5 shrink-0" />
          <span v-if="groupActive(item)" class="sel-bar" />
        </button>
      </div>

      <!-- 悬浮玻璃面板：teleport 到 body，固定定位，彻底避开侧栏 overflow 裁剪 -->
      <Teleport to="body">
        <div
          v-if="collapsed && flyout.item"
          class="rail-flyout-glass"
          :style="flyoutStyle"
          @mouseenter="onFlyoutEnter"
          @mouseleave="scheduleHide"
        >
          <div class="flyout-head">
            <component :is="flyout.item.icon" class="h-4 w-4 text-primary" />
            <span>{{ flyout.item.label }}</span>
          </div>

          <template v-if="flyout.item.children">
            <RouterLink
              v-for="c in flyout.item.children"
              :key="c.to"
              :to="c.to"
              class="flyout-item"
              :class="childActive(c) ? 'flyout-item--active' : ''"
              @click="flyout.item = null"
            >
              <component :is="c.icon" class="h-4 w-4 shrink-0 opacity-80" />
              <span class="truncate">{{ c.label }}</span>
            </RouterLink>
          </template>

          <RouterLink
            v-else
            :to="flyout.item.to"
            class="flyout-item"
            :class="route.path === flyout.item.to ? 'flyout-item--active' : ''"
            @click="flyout.item = null"
          >
            <span class="truncate">{{ flyout.item.label }}</span>
          </RouterLink>
        </div>
      </Teleport>
    </template>
  </nav>
</template>

<style scoped>
/* 收起态选中指示条：与展开态左侧色条风格一致，简洁不喧宾夺主 */
.sel-bar {
  position: absolute;
  left: -6px;
  top: 25%;
  bottom: 25%;
  width: 3px;
  border-radius: 9999px;
  background: hsl(var(--primary));
}

/* 悬浮玻璃面板（teleport 到 body，固定定位） */
.rail-flyout-glass {
  position: fixed;
  width: 224px;
  padding: 8px;
  border-radius: 14px;
  background: hsl(var(--popover) / 0.82);
  backdrop-filter: blur(14px) saturate(150%);
  -webkit-backdrop-filter: blur(14px) saturate(150%);
  border: 1px solid hsl(var(--border));
  box-shadow: 0 20px 50px -16px rgba(15, 23, 42, 0.38);
  z-index: 80;
  transform: translateY(-50%);
  animation: flyout-in 0.16s ease;
}
@keyframes flyout-in {
  from {
    opacity: 0;
    transform: translateY(-50%) translateX(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(-50%) translateX(0);
  }
}
.flyout-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px 8px;
  font-size: 13px;
  font-weight: 600;
  color: hsl(var(--foreground));
  border-bottom: 1px solid hsl(var(--border));
  margin-bottom: 6px;
}
.flyout-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: 9px;
  font-size: 13px;
  color: hsl(var(--muted-foreground));
  transition: background 0.15s ease, color 0.15s ease;
}
.flyout-item:hover {
  background: hsl(var(--accent));
  color: hsl(var(--foreground));
}
.flyout-item--active {
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
  font-weight: 600;
}
</style>
