<script setup>
// RackVisio 品牌图标：机柜（服务器机柜）SVG，直观体现「机柜三维可视化」产品特性。
// 使用 currentColor，置于蓝色渐变徽章背景上时自动呈现白色，与品牌主色一致。
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
    class="block"
  >
    <!-- 机柜外壳 -->
    <rect
      x="5"
      y="2.5"
      width="14"
      height="19"
      rx="2.5"
      fill="currentColor"
      fill-opacity="0.18"
      stroke="currentColor"
      stroke-width="1.4"
    />
    <!-- 服务器单元（横向插槽） -->
    <rect x="8" y="5.5" width="9" height="2" rx="1" fill="currentColor" fill-opacity="0.92" />
    <rect x="8" y="9" width="9" height="2" rx="1" fill="currentColor" fill-opacity="0.55" />
    <rect x="8" y="12.5" width="9" height="2" rx="1" fill="currentColor" fill-opacity="0.55" />
    <rect x="8" y="16" width="9" height="2" rx="1" fill="currentColor" fill-opacity="0.55" />
    <!-- 状态指示灯（绿=正常 / 琥珀=告警） -->
    <circle cx="15.4" cy="6.5" r="0.6" fill="#34d399" />
    <circle cx="15.4" cy="10" r="0.6" fill="#fbbf24" />
    <circle cx="15.4" cy="13.5" r="0.6" fill="#34d399" />
    <circle cx="15.4" cy="17" r="0.6" fill="#fbbf24" />
  </svg>
</template>
