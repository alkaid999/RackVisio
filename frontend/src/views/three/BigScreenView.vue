<template>
  <!-- 大屏：全屏 3D 机房可视化场景（无冗余数据仪表盘 UI） -->
  <div class="fixed inset-0 z-[60] bg-background">
    <Room3DView :fullscreen="true" />
  </div>
</template>

<script setup>
import Room3DView from '@/views/three/Room3DView.vue'
</script>
