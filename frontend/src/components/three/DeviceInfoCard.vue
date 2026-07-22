<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-2">
      <div class="min-w-0">
        <div class="text-base font-semibold text-slate-100 truncate">{{ device.name }}</div>
        <div class="text-xs text-slate-400 mt-0.5">{{ device.model || '—' }}</div>
      </div>
      <StatusBadge type="device" :value="device.status" />
    </div>

    <div class="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 text-sm">
      <span class="text-muted-foreground">设备类型</span>
      <span><DeviceTypeTag :type="device.device_type" /></span>
      <span class="text-muted-foreground">型号</span>
      <span class="truncate">{{ device.model || '—' }}</span>
      <span class="text-muted-foreground">IP 地址</span>
      <span>{{ device.ip_address || '—' }}</span>
      <span class="text-muted-foreground">序列号(SN)</span>
      <span>{{ device.sn || '—' }}</span>
      <template v-if="rack">
        <span class="text-muted-foreground">所属机柜</span>
        <span>{{ rack.code }} {{ rack.name }}</span>
      </template>
      <template v-if="device.current_rack_id && device.current_start_u">
        <span class="text-muted-foreground">U 位</span>
        <span>{{ device.current_start_u }}U ~ {{ device.current_start_u + (device.u_height || 0) - 1 }}U（共 {{ device.u_height }}U）</span>
      </template>
      <template v-else>
        <span class="text-muted-foreground">U 位</span>
        <span class="text-slate-400">未上架</span>
      </template>
    </div>
  </div>
</template>

<script setup>
import StatusBadge from '@/components/common/StatusBadge.vue'
import DeviceTypeTag from '@/components/device/DeviceTypeTag.vue'

defineProps({
  device: { type: Object, required: true },
  rack: { type: Object, default: null },
})
</script>
