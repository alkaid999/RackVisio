<template>
  <Card
    hover
    class="device-card group relative flex h-full cursor-pointer flex-col overflow-hidden transition-transform hover:-translate-y-0.5"
    @click="emit('view', device.id)"
  >
    <div class="flex items-start justify-between gap-2">
      <DeviceTypeTag :type="device.device_type" />
      <StatusBadge type="device" :value="device.status" />
    </div>
    <div class="mt-2 truncate text-base font-semibold text-foreground">{{ device.name }}</div>

    <!-- 固定信息区（始终渲染占位，保证底部分割线位置固定） -->
    <div class="mt-2 space-y-1.5 text-xs text-muted-foreground">
      <template v-if="isFacility">
        <div class="flex items-center gap-1">
          <ServerCog class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">基础设施（非资产）</span>
        </div>
        <div class="flex items-center gap-1">
          <Building2 class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">机房：{{ device.current_room_name || '—' }}</span>
        </div>
        <div class="flex items-center gap-1">
          <MapPin class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">
            {{ device.current_rack_id ? `${device.current_start_u}U ~ ${device.current_start_u + (device.u_height || 0) - 1}U` : '未上架' }}
          </span>
        </div>
      </template>
      <template v-else>
        <div class="flex items-center gap-1">
          <Tag class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">编号：{{ device.device_code || '—' }}</span>
        </div>
        <div class="flex items-center gap-1">
          <Cpu class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">型号：{{ device.model || '—' }}</span>
        </div>
        <div class="flex items-center gap-1">
          <Hash class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">SN：{{ device.sn || '—' }}</span>
        </div>
        <div class="flex items-center gap-1">
          <Globe class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">IP：{{ device.ip_address || '—' }}</span>
        </div>
        <div class="flex items-center gap-1">
          <Building2 class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">机房：{{ device.current_room_name || '—' }}</span>
        </div>
        <div class="flex items-center gap-1">
          <MapPin class="h-3.5 w-3.5 shrink-0" />
          <span class="truncate">
            {{ device.current_rack_id ? `${device.current_start_u}U ~ ${device.current_start_u + (device.u_height || 0) - 1}U` : '未上架' }}
          </span>
        </div>
      </template>
    </div>

    <!-- 底部操作：图标 + 文字，删除为红色（与「耗材列表」卡片一致；卡片可点击查看，故隐藏冗余「查看」） -->
    <div class="mt-2.5 flex justify-end gap-1 border-t border-border pt-2.5">
      <EntityActions
        variant="full"
        :show-view="false"
        :show-edit="canEdit"
        :show-delete="canEdit"
        @view="emit('view', device.id)"
        @edit="emit('edit', device)"
        @delete="emit('delete', device)"
      />
    </div>
  </Card>
</template>

<script setup>
import DeviceTypeTag from '@/components/device/DeviceTypeTag.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import { Cpu, Hash, Globe, MapPin, Tag, Building2, ServerCog } from 'lucide-vue-next'
import Card from '@/components/ui/card.vue'
import { isAssetDevice } from '@/utils/constants'

// DeviceOut: {id, device_code?, name, device_type, model?, sn?, ip_address?,
//             current_rack_id?, current_room_name?, current_start_u?, u_height?, ...}
const props = defineProps({
  device: { type: Object, required: true },
  // 是否允许编辑 / 删除（无 device:edit 权限时隐藏写操作）。
  canEdit: { type: Boolean, default: true },
})
const emit = defineEmits(['view', 'edit', 'delete'])
// 设施（非资产）：占 U 位但不进资产统计 / 不建接口。
const isFacility = !isAssetDevice(props.device)
</script>
