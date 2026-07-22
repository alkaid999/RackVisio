<template>
  <div class="device-detail">
    <div v-if="loading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <template v-else-if="device">
      <div class="page-head">
        <div>
          <h2 class="page-title flex items-center gap-2">
            {{ device.name }}
            <DeviceTypeTag :type="device.device_type" />
            <StatusBadge type="device" :value="device.status" />
          </h2>
          <p class="page-sub">
            {{ device.current_rack_id ? `位置：${device.current_start_u}U ~ ${device.current_start_u + (device.u_height || 0) - 1}U` : '位置：未上架（仅资产登记）' }} ·
            型号：{{ device.model || '—' }} · IP：{{ device.ip_address || '—' }}
          </p>
        </div>
        <div class="flex gap-2">
          <Button v-if="canEdit" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="openDeviceForm({ mode: 'edit', deviceId })"><Pencil class="h-4 w-4" /></Button>
          <Button v-if="canEdit" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="删除" title="删除" @click="onDelete"><Trash2 class="h-4 w-4" /></Button>
          <Button variant="outline" @click="goBack"><ChevronLeft class="h-4 w-4" />返回</Button>
        </div>
      </div>

      <!-- 基本信息 -->
      <Card class="mb-5">
        <template #header><span class="section-title flex items-center gap-1.5"><ClipboardList class="h-4 w-4" />基本信息</span></template>
        <div class="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <!-- 基础信息 -->
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Heading class="h-3.5 w-3.5" />设备名称</span><span>{{ device.name }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Component class="h-3.5 w-3.5" />设备类型</span><DeviceTypeTag :type="device.device_type" /></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Hash class="h-3.5 w-3.5" />设备编号</span><span class="font-mono">{{ device.device_code || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Cpu class="h-3.5 w-3.5" />设备型号</span><span>{{ device.model || '—' }}</span></div>
          <!-- 物理与位置 -->
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Ruler class="h-3.5 w-3.5" />设备 U 数</span><span>{{ device.u_height }}U</span></div>
          <!-- 网络与资产 -->
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Globe class="h-3.5 w-3.5" />IP 地址</span><span>{{ device.ip_address || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Barcode class="h-3.5 w-3.5" />序列号(SN)</span><span>{{ device.sn || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><CalendarClock class="h-3.5 w-3.5" />维保到期日</span><span>{{ device.warranty_expire || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Signal class="h-3.5 w-3.5" />设备状态</span><StatusBadge type="device" :value="device.status" /></div>
          <div class="flex gap-2">
            <span class="shrink-0 text-muted-foreground flex items-center gap-1"><Power class="h-3.5 w-3.5" />开关机</span>
            <span class="flex items-center gap-1.5">
              <span class="inline-block h-2.5 w-2.5 rounded-full" :style="{ background: DEVICE_POWER_COLORS[powerStatus] }"></span>
              <span class="font-medium" :style="{ color: DEVICE_POWER_COLORS[powerStatus] }">{{ powerStatus }}</span>
              <span v-if="isInStock" class="text-xs text-muted-foreground">（在库）</span>
            </span>
          </div>
          <!-- 备注 -->
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><StickyNote class="h-3.5 w-3.5" />备注</span><span>{{ device.remark || '—' }}</span></div>
          <!-- 关联位置 -->
          <div class="flex gap-2">
            <span class="shrink-0 text-muted-foreground flex items-center gap-1"><Boxes class="h-3.5 w-3.5" />所属机柜</span>
            <template v-if="device.current_rack_id">
              <button class="font-medium text-primary hover:underline" @click="goRack">{{ rackName || device.current_rack_id }}</button>
            </template>
            <span v-else>未上架</span>
          </div>
          <div class="flex gap-2">
            <span class="shrink-0 text-muted-foreground flex items-center gap-1"><Building2 class="h-3.5 w-3.5" />所属机房</span>
            <template v-if="device.current_room_id">
              <button class="font-medium text-primary hover:underline" @click="goRoom">{{ device.current_room_name || device.current_room_id }}</button>
            </template>
            <span v-else>—</span>
          </div>
          <div class="flex gap-2">
            <span class="shrink-0 text-muted-foreground flex items-center gap-1"><AlignStartVertical class="h-3.5 w-3.5" />U 位</span>
            <template v-if="device.current_rack_id">
              <span>{{ device.current_start_u }}U ~ {{ device.current_start_u + (device.u_height || 0) - 1 }}U（共 {{ device.u_height }}U）</span>
            </template>
            <span v-else>未上架</span>
          </div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Calendar class="h-3.5 w-3.5" />创建时间</span><span>{{ formatTime(device.created_at) }}</span></div>
        </div>
      </Card>

      <!-- 接口面板（自由排布 + 列表 双视图） -->
      <Card class="mb-5">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <span class="section-title flex items-center gap-1.5">
              <Network class="h-4 w-4" />接口面板（{{ interfaces.length }}）
            </span>
            <div class="flex items-center gap-2">
              <div class="inline-flex rounded-md border border-border p-0.5 text-xs">
                <button
                  type="button"
                  class="rounded px-3 py-1 transition"
                  :class="viewMode === 'panel' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'"
                  @click="viewMode = 'panel'"
                >
                  前面板
                </button>
                <button
                  type="button"
                  class="rounded px-3 py-1 transition"
                  :class="viewMode === 'list' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'"
                  @click="viewMode = 'list'"
                >
                  列表
                </button>
              </div>
              <Button v-if="canEdit" size="sm" @click="openAdd"><Plus class="h-4 w-4" />添加接口</Button>
            </div>
          </div>
        </template>

        <div v-if="panelLoading" class="flex justify-center py-10">
          <Spinner class="h-6 w-6 text-primary" />
        </div>
        <template v-else>
          <div v-show="viewMode === 'panel'" class="pt-1">
            <InterfaceFrontPanel
              :interfaces="interfaces"
              @select="onIfaceSelect"
            />
            <p class="mt-2 text-xs text-muted-foreground">
              点击接口查看详情、编辑或建链；颜色区分状态（绿=已连线 / 灰=未连线）。
            </p>
          </div>
          <div v-show="viewMode === 'list'">
            <InterfaceList
              :device-id="device.id"
              :can-edit="canEdit"
              @loaded="(n) => (portCount = n)"
              @view="onListView"
              @edit="onListEdit"
              @mutated="onInterfacesMutated"
              ref="listRef"
            />
          </div>
        </template>
      </Card>

      <!-- 添加 / 编辑接口弹窗 -->
      <InterfaceFormModal
        v-model="formOpen"
        :device-id="deviceId"
        :iface="formIface"
        :interfaces="interfaces"
        @saved="onFormSaved"
      />
      <!-- 接口详情钻取（含建链 / 断开） -->
      <InterfaceDetailDialog
        v-model="detailOpen"
        :iface="detailIface"
        :view-mode="detailViewMode"
        :can-edit="canEdit"
        :can-edit-link="canEditLink"
        @edit="onDetailEdit"
        @delete="onDetailDelete"
        @mutated="onInterfacesMutated"
      />

      <!-- 上下架记录：按类型分栏（上架 / 下架）展示 + 独立分页 -->
      <Card class="mb-5">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <span class="section-title flex items-center gap-1.5"><History class="h-4 w-4" />上下架记录</span>
            <div class="flex items-center gap-4 text-xs text-muted-foreground">
              <span class="flex items-center gap-1.5"><i class="hist-dot hist-dot--mount"></i>上架 {{ mountList.length }}</span>
              <span class="flex items-center gap-1.5"><i class="hist-dot hist-dot--unmount"></i>下架 {{ unmountList.length }}</span>
            </div>
          </div>
        </template>

        <div v-if="mountEvents.length" class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <section class="hist-col">
            <header class="hist-col__head">
              <span class="hist-col__title"><i class="hist-dot hist-dot--mount"></i>上架记录</span>
              <span class="hist-col__count">{{ mountList.length }} 条</span>
            </header>
            <ul v-if="mountPaged.length" class="hist-timeline">
              <li v-for="row in mountPaged" :key="'m-' + row.id" class="hist-row">
                <div class="hist-row__time">{{ formatTime(row.operated_at) }}</div>
                <div class="hist-row__meta">
                  <span>{{ row.room_name || '—' }} / {{ row.rack_name || '—' }}</span>
                  <span>{{ row.start_u }}U~{{ row.start_u + row.occupied_u - 1 }}U（{{ row.occupied_u }}U）</span>
                  <span>操作人：{{ row.operator || '—' }}</span>
                </div>
                <div class="hist-row__actions">
                  <Button v-if="canEdit" variant="ghost" size="icon-sm" @click.stop="openEditRecord(row)"><Pencil class="h-3.5 w-3.5" /></Button>
                  <Button v-if="canEdit" variant="ghost" size="icon-sm" class="text-destructive hover:text-destructive" @click.stop="onDeleteRecord(row)"><Trash2 class="h-3.5 w-3.5" /></Button>
                </div>
              </li>
            </ul>
            <EmptyState v-else title="暂无上架记录" class="py-10" />
            <div v-if="mountList.length" class="hist-pager">
              <Button variant="outline" size="icon-sm" :disabled="mountPage <= 1" @click="mountPage--">
                <ChevronLeft class="h-4 w-4" />
              </Button>
              <span class="hist-pager__text">第 {{ mountPage }} / {{ mountTotalPages }} 页</span>
              <Button variant="outline" size="icon-sm" :disabled="mountPage >= mountTotalPages" @click="mountPage++">
                <ChevronRight class="h-4 w-4" />
              </Button>
            </div>
          </section>

          <section class="hist-col">
            <header class="hist-col__head">
              <span class="hist-col__title"><i class="hist-dot hist-dot--unmount"></i>下架记录</span>
              <span class="hist-col__count">{{ unmountList.length }} 条</span>
            </header>
            <ul v-if="unmountPaged.length" class="hist-timeline">
              <li v-for="row in unmountPaged" :key="'u-' + row.id" class="hist-row">
                <div class="hist-row__time">{{ formatTime(row.operated_at) }}</div>
                <div class="hist-row__meta">
                  <span>{{ row.room_name || '—' }} / {{ row.rack_name || '—' }}</span>
                  <span>{{ row.start_u }}U~{{ row.start_u + row.occupied_u - 1 }}U（{{ row.occupied_u }}U）</span>
                  <span>操作人：{{ row.operator || '—' }}</span>
                </div>
                <div class="hist-row__actions">
                  <Button v-if="canEdit" variant="ghost" size="icon-sm" @click.stop="openEditRecord(row)"><Pencil class="h-3.5 w-3.5" /></Button>
                  <Button v-if="canEdit" variant="ghost" size="icon-sm" class="text-destructive hover:text-destructive" @click.stop="onDeleteRecord(row)"><Trash2 class="h-3.5 w-3.5" /></Button>
                </div>
              </li>
            </ul>
            <EmptyState v-else title="暂无下架记录" class="py-10" />
            <div v-if="unmountList.length" class="hist-pager">
              <Button variant="outline" size="icon-sm" :disabled="unmountPage <= 1" @click="unmountPage--">
                <ChevronLeft class="h-4 w-4" />
              </Button>
              <span class="hist-pager__text">第 {{ unmountPage }} / {{ unmountTotalPages }} 页</span>
              <Button variant="outline" size="icon-sm" :disabled="unmountPage >= unmountTotalPages" @click="unmountPage++">
                <ChevronRight class="h-4 w-4" />
              </Button>
            </div>
          </section>
        </div>
        <EmptyState v-else title="暂无上下架记录" />
      </Card>

      <!-- 编辑设备弹窗（open 由 openDeviceForm() 在编辑按钮手势内同步触发） -->
      <DeviceForm @saved="onDeviceSaved" />

      <!-- 编辑上架记录弹窗 -->
      <Dialog v-model="editRecordVisible" title="编辑上架记录" class="max-w-sm" @update:visible="(v) => (editRecordVisible = v)">
        <Form v-if="editRecordTarget" :model="editRecordForm" :rules="{}">
          <FormItem v-if="editRecordTarget.event_type === '上架'" label="上架人" name="mounted_by">
            <Input v-model="editRecordForm.mounted_by" placeholder="上架操作人" />
          </FormItem>
          <FormItem v-else label="下架人" name="unmounted_by">
            <Input v-model="editRecordForm.unmounted_by" placeholder="下架操作人" />
          </FormItem>
        </Form>
        <template #footer>
          <div class="flex justify-end gap-2">
            <Button variant="outline" @click="editRecordVisible = false">取消</Button>
            <Button :loading="editRecordSaving" @click="confirmEditRecord">保存</Button>
          </div>
        </template>
      </Dialog>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { openDeviceForm } from '@/composables/useDeviceFormState'
import { useDeviceStore } from '@/stores/device'
import { useAuthStore } from '@/stores/auth'
import deviceApi from '@/api/device'
import rackApi from '@/api/rack'
import interfaceApi from '@/api/interface'
import InterfaceList from '@/components/device/InterfaceList.vue'
import InterfaceFrontPanel from '@/components/device/InterfaceFrontPanel.vue'
import InterfaceFormModal from '@/components/device/InterfaceFormModal.vue'
import InterfaceDetailDialog from '@/components/device/InterfaceDetailDialog.vue'
import DeviceTypeTag from '@/components/device/DeviceTypeTag.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import DeviceForm from '@/views/device/DeviceForm.vue'
import { Network } from 'lucide-vue-next'
import {
  Pencil,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Heading,
  Component,
  Boxes,
  Signal,
  Hash,
  Barcode,
  Globe,
  AlignStartVertical,
  Calendar,
  History,
  Plus,
  Building2,
  Power,
  Ruler,
  CalendarClock,
  Cpu,
} from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import { DEVICE_POWER_COLORS } from '@/utils/constants'
import Card from '@/components/ui/card.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'

const route = useRoute()
const router = useRouter()
const store = useDeviceStore()
const auth = useAuthStore()
const deviceId = route.params.id
// 编辑 / 删除设备、添加接口、上下架记录写操作均需 device:edit；建链 / 编辑链路 / 断开需 link:edit。
const canEdit = computed(() => auth.hasPermission('device:edit'))
const canEditLink = computed(() => auth.hasPermission('link:edit'))

const { success } = useToast()
const { confirm } = useConfirm()

const device = computed(() => store.currentDevice)
const loading = computed(() => store.loading)
const portCount = ref(0)
const rackName = ref('')
// 开关机状态展示：在库设备未通电，恒为「关机」且不可修改；在架设备取实际 power_status。
const isInStock = computed(() => !device.value?.current_rack_id)
const powerStatus = computed(() => {
  if (isInStock.value) return '关机'
  return device.value?.power_status || '开机'
})

// 接口数据（自由排布前面板 + 列表均读取此数据）。
const interfaces = ref([])
const panelLoading = ref(false)
const viewMode = ref('panel') // panel | list
const listRef = ref(null)

// 添加 / 编辑接口弹窗状态。
const formOpen = ref(false)
const formIface = ref(null)
// 接口详情钻取弹窗状态。
const detailOpen = ref(false)
const detailIface = ref(null)
// 接口详情是否以「查看」模式打开（列表的「查看」按钮触发，纯只读）。
const detailViewMode = ref(false)
// 上下架操作流水（上架 / 下架事件，按时间倒序）。
const mountEvents = ref([])
// 按操作类型分栏 + 独立分页（每栏固定条数）。
const HISTORY_PAGE_SIZE = 4
const mountPage = ref(1)
const unmountPage = ref(1)
const mountList = computed(() =>
  mountEvents.value.filter((e) => e.event_type === '上架')
)
const unmountList = computed(() =>
  mountEvents.value.filter((e) => e.event_type === '下架')
)
const mountTotalPages = computed(() =>
  Math.max(1, Math.ceil(mountList.value.length / HISTORY_PAGE_SIZE))
)
const unmountTotalPages = computed(() =>
  Math.max(1, Math.ceil(unmountList.value.length / HISTORY_PAGE_SIZE))
)
const mountPaged = computed(() => {
  const start = (mountPage.value - 1) * HISTORY_PAGE_SIZE
  return mountList.value.slice(start, start + HISTORY_PAGE_SIZE)
})
const unmountPaged = computed(() => {
  const start = (unmountPage.value - 1) * HISTORY_PAGE_SIZE
  return unmountList.value.slice(start, start + HISTORY_PAGE_SIZE)
})
function formatTime(t) {
  return t ? new Date(t).toLocaleString() : '—'
}

function goRack() {
  router.push(`/racks/${device.value.current_rack_id}`)
}

function goRoom() {
  router.push(`/rooms/${device.value.current_room_id}`)
}

// —— 接口数据（自由排布，无模板）——
async function fetchInterfaces() {
  panelLoading.value = true
  try {
    interfaces.value = await interfaceApi.list(deviceId)
  } catch (e) {
    interfaces.value = []
  } finally {
    panelLoading.value = false
  }
}
function openAdd() {
  formIface.value = null
  formOpen.value = true
}
function onIfaceSelect(iface) {
  detailViewMode.value = false
  detailIface.value = iface
  detailOpen.value = true
}
function onListView(iface) {
  detailViewMode.value = true
  detailIface.value = iface
  detailOpen.value = true
}
function onFormSaved() {
  fetchInterfaces()
  listRef.value?.refresh?.()
}
function onInterfacesMutated() {
  fetchInterfaces()
  listRef.value?.refresh?.()
  portCount.value = interfaces.value.length
}
// 列表「编辑」与前面板点击保持一致：统一进入“接口详情页”（可编辑），
// 在详情页内通过「编辑接口」进入字段编辑，不再直接弹出编辑框。
function onListEdit(iface) {
  detailViewMode.value = false
  detailIface.value = iface
  detailOpen.value = true
}
function onDetailEdit(iface) {
  detailOpen.value = false
  formIface.value = iface
  formOpen.value = true
}
async function onDetailDelete(iface) {
  const ok = await confirm({
    title: '提示',
    description: `确认删除接口「${iface.name}」？若已建链将一并断开。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await interfaceApi.remove(iface.id)
    success('已删除')
    detailOpen.value = false
    onInterfacesMutated()
  } catch (e) {
    // 取消或失败
  }
}
// 编辑设备后刷新详情，并重新获取（可能变更的）所属机柜名称。
async function onDeviceSaved() {
  await store.fetchOne(deviceId)
  if (device.value.current_rack_id) {
    const rack = await rackApi.get(device.value.current_rack_id).catch(() => null)
    if (rack) rackName.value = `${rack.name}`
  } else {
    rackName.value = ''
  }
}
function goBack() {
  router.back()
}

// —— 上架记录编辑 / 删除 ——
async function reloadHistory() {
  try {
    const r = await deviceApi.mountHistory(deviceId)
    mountEvents.value = Array.isArray(r) ? r : []
    mountPage.value = 1
    unmountPage.value = 1
  } catch (e) {
    mountEvents.value = []
  }
}
const editRecordVisible = ref(false)
const editRecordSaving = ref(false)
const editRecordTarget = ref(null)
const editRecordForm = ref({ mounted_by: '', unmounted_by: '' })
function openEditRecord(row) {
  editRecordTarget.value = row
  editRecordForm.value = {
    mounted_by: row.event_type === '上架' ? row.operator || '' : '',
    unmounted_by: row.event_type === '下架' ? row.operator || '' : '',
  }
  editRecordVisible.value = true
}
async function confirmEditRecord() {
  if (!editRecordTarget.value) return
  editRecordSaving.value = true
  try {
    const payload = {}
    if (editRecordTarget.value.event_type === '上架') {
      payload.mounted_by = editRecordForm.value.mounted_by || undefined
    } else {
      payload.unmounted_by = editRecordForm.value.unmounted_by || undefined
    }
    await deviceApi.updateMountRecord(editRecordTarget.value.id, payload)
    success('已保存')
    editRecordVisible.value = false
    await reloadHistory()
  } catch (e) {
    // 拦截器提示
  } finally {
    editRecordSaving.value = false
  }
}
async function onDeleteRecord(row) {
  const ok = await confirm({
    title: '删除记录',
    description: `确认删除该条${row.event_type}记录？删除后不可恢复。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await deviceApi.deleteMountRecord(row.id)
    success('已删除')
    await reloadHistory()
  } catch (e) {
    // 拦截器提示
  }
}
async function onDelete() {
  const ok = await confirm({
    title: '提示',
    description: `确认删除设备「${device.value.name}」？删除后机柜容量将重算。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await deviceApi.remove(deviceId)
    success('删除成功')
    router.back()
  } catch (e) {
    // 取消或错误
  }
}

onMounted(async () => {
  // 上下架记录流水：独立请求，尽早并行拉取。
  deviceApi
    .mountHistory(deviceId)
    .then((r) => {
      mountEvents.value = Array.isArray(r) ? r : []
      mountPage.value = 1
      unmountPage.value = 1
    })
    .catch(() => {
      mountEvents.value = []
    })
  // 接口数据：并行拉取，不阻塞详情渲染。
  fetchInterfaces()
  await store.fetchOne(deviceId)
  // 拉取所属机柜名称（非上架设备无需拉取）。
  if (device.value.current_rack_id) {
    const rack = await rackApi.get(device.value.current_rack_id).catch(() => null)
    if (rack) rackName.value = `${rack.name}`
  }
})
</script>

<style scoped>
/* 分栏：上架(绿) / 下架(橙) 状态点 */
.hist-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  flex: none;
}
.hist-dot--mount {
  background-color: #67c23a;
}
.hist-dot--unmount {
  background-color: #e6a23c;
}

/* 单栏容器 */
.hist-col {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border, rgba(128, 128, 128, 0.2));
  border-radius: 12px;
  background: color-mix(in srgb, var(--muted, #f4f4f5) 40%, transparent);
  padding: 12px;
  min-height: 120px;
}
.hist-col__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.hist-col__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}
.hist-col__count {
  font-size: 12px;
  color: var(--muted-foreground, #71717a);
}

/* 时间线列表 */
.hist-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}
.hist-row {
  position: relative;
  border: 1px solid var(--border, rgba(128, 128, 128, 0.18));
  border-radius: 8px;
  background: var(--background, #fff);
  padding: 8px 10px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.hist-row__actions {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
}
.hist-row:hover {
  border-color: color-mix(in srgb, var(--primary, #3b82f6) 40%, transparent);
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
}
.hist-row__time {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
}
.hist-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 2px;
  padding-right: 56px;
  font-size: 12px;
  color: var(--muted-foreground, #71717a);
}

/* 分页器 */
.hist-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border, rgba(128, 128, 128, 0.18));
}
.hist-pager__text {
  font-size: 12px;
  color: var(--muted-foreground, #71717a);
}
</style>
