<template>
  <RackListPanel :initial-room-id="prefillRoom" />
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RackListPanel from '@/components/rack/RackListPanel.vue'

// 从机房详情「查看全部机柜 →」跳转携带 ?room=<id>：
// 在 setup 阶段同步读取并预筛该机房（不锁定，下拉仍可选），随后清掉 URL 参数，
// 使筛选态成为单一真相源（避免返回/刷新重复套用）。
const route = useRoute()
const router = useRouter()
const prefillRoom = ref('')
const q = route.query.room
if (q) {
  prefillRoom.value = String(q)
  router.replace({ query: { ...route.query, room: undefined } })
}
</script>
