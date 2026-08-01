<template>
  <div class="room-detail">
    <div v-if="loading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <template v-else-if="room">
      <!-- 标题栏 -->
      <div class="page-head">
        <div>
          <h2 class="page-title">
            {{ room.name }}
            <small class="text-muted-foreground font-normal">（{{ room.code }}）</small>
          </h2>
          <p class="page-sub">
            编号：{{ room.code }} · 状态：
            <Badge :variant="room.status === 'active' ? 'success' : 'secondary'">
              {{ room.status === 'active' ? '启用' : '停用' }}
            </Badge>
          </p>
        </div>
        <div class="flex gap-2">
          <Button v-if="canEditRoom" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="roomFormVisible = true"><Pencil class="h-4 w-4" /></Button>
          <Button v-if="canEditRoom" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="删除" title="删除" @click="onDeleteRoom"><Trash2 class="h-4 w-4" /></Button>
          <Button variant="outline" @click="goBack"><ChevronLeft class="h-4 w-4" />返回</Button>
        </div>
      </div>

      <!-- 基本信息 -->
      <Card class="mb-5">
        <template #header><span class="section-title flex items-center gap-1.5"><ClipboardList class="h-4 w-4" />基本信息</span></template>
        <div class="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Heading class="h-3.5 w-3.5" />名称</span><span>{{ room.name }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Hash class="h-3.5 w-3.5" />编号</span><span class="font-mono">{{ room.code }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Tag class="h-3.5 w-3.5" />别名</span><span>{{ room.alias || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><MapPin class="h-3.5 w-3.5" />区域</span><span>{{ room.area || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Building2 class="h-3.5 w-3.5" />所属楼宇</span><span>{{ room.building || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Layers class="h-3.5 w-3.5" />所在楼层</span><span>{{ room.floor || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Map class="h-3.5 w-3.5" />机房地址</span><span>{{ room.address || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Signal class="h-3.5 w-3.5" />状态</span><Badge :variant="room.status === 'active' ? 'success' : 'secondary'">{{ room.status === 'active' ? '启用' : '停用' }}</Badge></div>
        </div>
      </Card>

      <!-- 容量统计（含机柜概览）：完整增删改 / 批量新增 / 导入 / 导出只在全局「机柜列表」体现一次 -->
      <Card class="mb-5">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="section-title flex items-center gap-1.5"><BarChart3 class="h-4 w-4" />容量统计</span>
            <Button variant="ghost" size="sm" class="text-muted-foreground hover:text-foreground" title="在机柜列表中查看该机房下全部机柜" @click="goAllRacks">
              查看全部机柜<ArrowRight class="ml-1 h-3.5 w-3.5" />
            </Button>
          </div>
        </template>
        <StatsPanel v-if="stats" :stats="stats" />
      </Card>

      <!-- 机房平面图：直接内嵌卡片，支持拖拽调整机柜位置（松手自动保存），无需跳转 -->
      <Card class="mb-5">
        <template #header><span class="section-title flex items-center gap-1.5"><LayoutGrid class="h-4 w-4" />机房平面图</span></template>
        <FloorPlanBoard :room-id="roomId" @updated="onPlanUpdated" />
      </Card>
    </template>

    <!-- 编辑机房弹窗 -->
    <RoomForm v-model:visible="roomFormVisible" mode="edit" :room-id="roomId" @saved="onRoomSaved" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Map, MapPin, ArrowRight, Pencil, Trash2, ChevronLeft, Heading, Hash, Tag, Building2, Layers, Signal, ClipboardList, BarChart3, LayoutGrid } from 'lucide-vue-next'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import StatsPanel from '@/components/room/StatsPanel.vue'
import FloorPlanBoard from '@/components/room/FloorPlanBoard.vue'
import RoomForm from '@/views/room/RoomForm.vue'
import Button from '@/components/ui/button.vue'
import Card from '@/components/ui/card.vue'
import Badge from '@/components/ui/badge.vue'
import Spinner from '@/components/ui/spinner.vue'

const route = useRoute()
const router = useRouter()
const store = useRoomStore()
const { success } = useToast()
const { confirm } = useConfirm()
const roomId = route.params.id
const auth = useAuthStore()
// 编辑机房需 room:edit。机柜的增删改由全局「机柜列表」按 rack:edit 自行判断，本页不再内嵌机柜操作。
const canEditRoom = computed(() => auth.hasPermission('room:edit'))

const room = computed(() => store.currentRoom)
const stats = computed(() => store.stats)
// 本地加载态：编辑机房时 RoomForm 内部 fetchOne 会翻转 store.loading，
// 若 loading 直接绑定 store.loading 将触发本页内容区卸载/重挂循环导致预填失效（同机柜详情陷阱）。
const loading = ref(true)
const roomFormVisible = ref(false)

// 从机房详情跳转到全局机柜列表，并携带 ?room=<id> 自动预筛该机房
function goAllRacks() {
  router.push({ path: '/racks', query: { room: room.value?.id } })
}
function goBack() {
  router.back()
}
// 平面图内机柜位置 / 状态变更后，刷新本页容量统计，保持数据一致
function onPlanUpdated() {
  store.fetchStats(roomId)
}
// 机房信息变更后刷新详情与统计
async function onRoomSaved() {
  await Promise.all([store.fetchOne(roomId), store.fetchStats(roomId)])
}
// 删除机房：物理删除，需 room:edit 权限。删除前后端均校验机房内不得有已上架设备（有设备则拦截，需先下架）；空机柜随机房一并删除。
async function onDeleteRoom() {
  const ok = await confirm({
    title: '删除机房',
    description: `确认删除机房「${room.value?.name}」？将永久删除该机房及其下空机柜。若机房内仍有已上架设备则无法删除（需先下架）。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.remove(roomId)
    success('删除成功')
    router.push('/rooms')
  } catch (e) {
    // 拦截器提示（如仍有未下架设备等）
  }
}

onMounted(async () => {
  try {
    await store.fetchOne(roomId)
    await Promise.all([store.fetchStats(roomId)])
  } finally {
    loading.value = false
  }
})
</script>
