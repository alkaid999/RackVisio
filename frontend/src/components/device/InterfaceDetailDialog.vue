<template>
  <Dialog
    :model-value="modelValue"
    :title="readonly ? '查看接口' : '接口详情'"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <div v-if="iface" class="space-y-3">
      <div class="flex items-center gap-3">
        <div
          class="flex h-11 w-11 items-center justify-center rounded-xl text-lg font-bold"
          :style="{ background: hexA(statusColor(iface.status), 0.14), color: statusColor(iface.status) }"
        >
          #{{ iface.interface_no || '—' }}
        </div>
        <div>
          <div class="text-base font-semibold">{{ iface.name }}</div>
          <div class="text-xs text-muted-foreground">前面板序号 #{{ iface.interface_no || '—' }}</div>
        </div>
      </div>

      <dl class="grid grid-cols-2 gap-3 rounded-lg border border-border bg-muted/30 p-4 text-sm">
        <div>
          <dt class="text-xs text-muted-foreground">接口类型</dt>
          <dd class="font-medium">{{ INTERFACE_TYPE_LABELS[iface.interface_type] || iface.interface_type }}</dd>
        </div>
        <div>
          <dt class="text-xs text-muted-foreground">角色</dt>
          <dd class="font-medium">{{ INTERFACE_ROLE_LABELS[iface.role] || iface.role }}</dd>
        </div>
        <div>
          <dt class="text-xs text-muted-foreground">速率</dt>
          <dd class="font-medium">{{ iface.speed }}</dd>
        </div>
        <div>
          <dt class="text-xs text-muted-foreground">状态</dt>
          <dd class="font-medium flex items-center gap-1.5">
            <i class="h-2.5 w-2.5 rounded-full" :style="{ background: statusColor(iface.status) }"></i>
            {{ statusLabel('interface', iface.status) }}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-muted-foreground">IP 地址</dt>
          <dd class="font-medium font-mono text-xs truncate">{{ iface.ip_address || '—' }}</dd>
        </div>
        <div class="col-span-2">
          <dt class="text-xs text-muted-foreground">接口 ID</dt>
          <dd class="font-mono text-xs truncate">{{ iface.id }}</dd>
        </div>
      </dl>

      <!-- 链路信息（建链自动置「已连线」；无链路显示未连线） -->
      <div class="rounded-lg border border-border p-4">
        <div class="mb-2 flex items-center justify-between">
          <span class="text-sm font-semibold">链路信息</span>
          <span v-if="!link" class="text-xs text-muted-foreground">未建链</span>
        </div>

        <div v-if="link" class="space-y-2 text-sm">
          <div class="flex items-center gap-2 text-muted-foreground">
            <span class="flex-1 truncate">{{ link.source_device_name }} / {{ link.source_interface_name }}</span>
            <ArrowLeftRight class="h-4 w-4 shrink-0 text-primary" />
            <span class="flex-1 truncate text-right">
              <template v-if="link.target_interface_id">{{ link.target_device_name }} / {{ link.target_interface_name }}</template>
              <template v-else><span class="inline-flex items-center gap-1"><ExternalLink class="h-3.5 w-3.5" />{{ link.target_external || '外部' }}</span></template>
            </span>
          </div>
          <div class="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>介质：{{ LINK_MEDIUM_LABELS[link.medium] || link.medium }}</span>
            <span v-if="link.connector_type">连接器：{{ CONNECTOR_TYPE_LABELS[link.connector_type] || link.connector_type }}</span>
            <span v-if="link.cable_length">长度：{{ link.cable_length }}</span>
            <span v-if="link.remark" class="col-span-2">备注：{{ link.remark }}</span>
          </div>
        </div>

        <div v-if="canEditLink && !readonly" class="mt-3 flex items-center justify-end gap-2">
          <Button v-if="!link" variant="outline" size="sm" @click="linkOpen = true">建链</Button>
          <template v-else>
            <Button variant="outline" size="sm" @click="linkEditOpen = true">编辑链路</Button>
            <Button variant="outline" size="sm" class="text-destructive hover:text-destructive" @click="onUnlink">断开链路</Button>
          </template>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <!-- 接口操作（接口级：删除 / 编辑，仅保留在 footer） -->
        <Button v-if="canEdit && !readonly" variant="outline" size="sm" class="text-destructive hover:text-destructive" @click="onDelete">删除接口</Button>
        <Button v-if="canEdit && !readonly" variant="outline" size="sm" @click="onEdit">编辑接口</Button>
      </div>
    </template>

    <!-- 建链弹窗（本端预置为当前接口） -->
    <LinkFormDialog
      v-model:visible="linkOpen"
      mode="create"
      :source-interface="iface"
      @saved="onLinked"
    />
    <!-- 编辑链路弹窗（已有链路可修改介质/连接器/长度/备注/状态；本端朝向为当前接口所属设备） -->
    <LinkFormDialog
      v-model:visible="linkEditOpen"
      mode="edit"
      :link-id="link && link.id"
      :link="link"
      :context-device-id="iface && iface.device_id"
      @saved="onLinkEdited"
    />
  </Dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import interfaceApi from '@/api/interface'
import linkApi from '@/api/link'
import Dialog from '@/components/ui/dialog.vue'
import Button from '@/components/ui/button.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LinkFormDialog from '@/views/link/LinkFormDialog.vue'
import { ArrowLeftRight, ExternalLink } from 'lucide-vue-next'
import {
  INTERFACE_TYPE_LABELS,
  INTERFACE_ROLE_LABELS,
  LINK_MEDIUM_LABELS,
  CONNECTOR_TYPE_LABELS,
  statusColor,
  statusLabel,
} from '@/utils/constants'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  iface: { type: Object, default: null },
  // 是否以「查看」模式打开（列表的「查看」按钮触发，纯只读、隐藏所有操作）。
  viewMode: { type: Boolean, default: false },
  // 是否允许编辑 / 删除接口（无 device:edit 权限时隐藏）。
  canEdit: { type: Boolean, default: true },
  // 是否允许建链 / 编辑链路 / 断开（无 link:edit 权限时隐藏）。
  canEditLink: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'edit', 'delete', 'mutated'])

// 只读模式：列表「查看」进入时为真，隐藏所有写操作。
const readonly = computed(() => !!props.viewMode)

const { success } = useToast()
const { confirm } = useConfirm()

const link = ref(null)
const linkOpen = ref(false)
const linkEditOpen = ref(false)

async function fetchLink() {
  if (!props.iface) {
    link.value = null
    return
  }
  link.value = await interfaceApi.linkByInterface(props.iface.id)
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) fetchLink()
    else linkOpen.value = false
  }
)

function hexA(hex, a) {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}
function onEdit() {
  emit('edit', props.iface)
}
function onDelete() {
  emit('delete', props.iface)
}
// 建链成功后：刷新链路展示，并通知父组件同步面板/列表。
function onLinked() {
  linkOpen.value = false
  fetchLink()
  emit('mutated')
}
// 编辑链路成功后：刷新链路展示，并通知父组件同步面板/列表。
function onLinkEdited() {
  linkEditOpen.value = false
  fetchLink()
  emit('mutated')
}
async function onUnlink() {
  if (!link.value) return
  const ok = await confirm({
    title: '提示',
    description: '确认断开该链路？两端接口将回落为「未连线」。',
    variant: 'danger',
    confirmText: '断开',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await linkApi.remove(link.value.id)
    success('链路已断开')
    link.value = null
    emit('mutated')
  } catch (e) {
    // 取消或失败
  }
}
</script>
