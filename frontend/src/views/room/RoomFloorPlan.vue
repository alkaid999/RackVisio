<template>
  <div class="mx-auto max-w-[1400px] px-4 py-5">
    <!-- 顶栏：返回 / 机房名 -->
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <button
        class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
        @click="router.back()"
      >
        <ArrowLeft class="h-4 w-4" /> 返回
      </button>
      <div class="min-w-0">
        <h1 class="truncate text-lg font-semibold text-foreground">机房平面图</h1>
        <p v-if="room" class="truncate text-xs text-muted-foreground">
          {{ room.name }}（{{ room.code }}）· 拖拽机柜调整位置，松手自动保存
        </p>
      </div>
    </div>

    <!-- 复用地图板组件：详情页与独立路由页共用，拖拽逻辑自包含 -->
    <FloorPlanBoard :room-id="roomId" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import FloorPlanBoard from '@/components/room/FloorPlanBoard.vue'
import roomApi from '@/api/room'

const route = useRoute()
const router = useRouter()
const roomId = route.params.id
const room = ref(null)

onMounted(async () => {
  try {
    room.value = await roomApi.get(roomId)
  } catch {
    room.value = null
  }
})
</script>
