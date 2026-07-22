<template>
  <div class="rack-detail">
    <div v-if="loading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <template v-else-if="rack">
      <div class="page-head">
        <div>
          <h2 class="page-title">
            {{ rack.name }}
            <small class="text-slate-400 font-normal">（{{ rack.column_code }} / {{ rack.code }}）</small>
          </h2>
          <p class="page-sub">
            坐标：{{ rack.column_code }} / {{ rack.code }} ·
            容量：{{ rack.used_u }} / {{ rack.total_u }}U ·
            <StatusBadge type="rack" :value="rack.status" />
          </p>
        </div>
        <div class="flex gap-2">
          <Button v-if="canEdit" @click="openMount()"><PackagePlus class="h-4 w-4" />上架设备</Button>
          <Button v-if="canEdit" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="rackFormVisible = true"><Pencil class="h-4 w-4" /></Button>
          <Button v-if="canEdit" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="删除" title="删除" @click="onDelete"><Trash2 class="h-4 w-4" /></Button>
          <Button variant="outline" @click="goBack"><ChevronLeft class="h-4 w-4" />返回</Button>
        </div>
      </div>

      <!-- U 位图 + 架下设备（双栏：左 U 位图，右可拖拽的架下设备） -->
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Card class="lg:col-span-3">
          <template #header>
            <span class="section-title flex items-center gap-1.5">
              <Grid3x3 class="h-4 w-4" />U 位占用图
            </span>
          </template>
          <p class="mb-2 text-xs text-slate-500">
            <template v-if="canEdit">拖拽右侧设备至空闲位即可上架 · </template>点击空闲位批量上架 · 悬停设备查看详情 · 悬停已上架设备可下架 · 点击设备进入详情
          </p>
          <div class="u-map-scroll max-h-[640px] overflow-y-auto pr-1">
            <USlotMap
              :u-map="uMap"
              :devices="devices"
              @add-device="onAddAtU"
              @select-device="goDevice"
              @unmount-device="onUnmountId"
              @mount-device="onDropMount"
            />
          </div>
          <div class="mt-3 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3">
            <span v-for="t in DEVICE_TYPE_OPTIONS" :key="t.value" class="flex items-center gap-1.5 text-xs text-slate-500">
              <span class="h-3 w-3 rounded" :style="{ background: DEVICE_TYPE_COLORS[t.value] }"></span>
              {{ t.label }}
            </span>
          </div>
        </Card>

        <!-- 架下设备：已下架 + 在库（统一逻辑），可拖拽上架 -->
        <Card class="lg:col-span-2">
          <template #header>
            <span class="section-title flex items-center gap-1.5">
              <PackageX class="h-4 w-4" />架下设备（{{ filteredCandidates.length }}）
            </span>
          </template>
          <DeviceFilterBar
            :model-value="filter"
            :type-options="DEVICE_TYPE_OPTIONS"
            @update:model-value="onFilterChange"
            class="mb-3"
          />
          <div class="offrack-scroll max-h-[520px] overflow-y-auto pr-1">
            <div
              v-for="d in filteredCandidates"
              :key="d.id"
              class="offrack-item"
              :draggable="canEdit"
              @dragstart="onDragStart($event, d)"
              @dblclick="quickMount(d)"
            >
              <div class="flex items-center gap-2">
                <span class="h-2.5 w-2.5 rounded-full" :style="{ background: DEVICE_TYPE_COLORS[d.device_type] || '#909399' }"></span>
                <span class="offrack-name truncate">{{ d.name }}</span>
              </div>
              <div class="mt-1 flex items-center justify-between text-xs text-slate-500">
                <DeviceTypeTag :type="d.device_type" />
                <span>{{ d.u_height }}U</span>
              </div>
              <div class="mt-1 flex items-center justify-between">
                <StatusBadge type="device" :value="d.status" />
                <span v-if="canEdit" class="text-[11px] text-slate-400">拖拽上架</span>
              </div>
            </div>
            <EmptyState v-if="!candidates.length" title="暂无架下设备" class="py-8" />
          </div>
        </Card>
      </div>

      <!-- 设备列表（精简） -->
      <Card class="mb-5 mt-4">
        <template #header><span class="section-title flex items-center gap-1.5"><ListOrdered class="h-4 w-4" />机柜内设备（{{ devices.length }}）</span></template>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead class="w-28">类型</TableHead>
              <TableHead class="w-32">位置</TableHead>
              <TableHead class="w-32">IP</TableHead>
              <TableHead class="w-24">状态</TableHead>
              <TableHead class="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in devices" :key="row.id">
              <TableCell>{{ row.name }}</TableCell>
              <TableCell><DeviceTypeTag :type="row.device_type" /></TableCell>
              <TableCell>
                <template v-if="row.current_start_u != null">{{ row.current_start_u }}U ~ {{ row.current_start_u + row.u_height - 1 }}U</template>
                <span v-else class="text-slate-400">未上架</span>
              </TableCell>
              <TableCell>{{ row.ip_address }}</TableCell>
              <TableCell><StatusBadge type="device" :value="row.status" /></TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-1">
                  <Button variant="ghost" size="sm" @click="goDevice(row.id)"><Eye class="h-4 w-4" />查看</Button>
                  <Button v-if="canEdit" variant="ghost" size="sm" class="text-destructive hover:text-destructive" @click="onUnmountId(row.id)">下架</Button>
                </div>
              </TableCell>
            </TableRow>
            <EmptyState v-if="!devices.length" title="该机柜暂无上架设备" class="col-span-full" />
          </TableBody>
        </Table>
      </Card>

      <!-- 上架设备弹窗：从候选设备池（仓库 / 空闲 / 下架设备）中选择 -->
      <Dialog v-model="mountVisible" title="上架设备" class="max-w-lg" @update:visible="(v) => (mountVisible = v)">
        <div v-if="!candidates.length" class="py-6 text-center text-sm text-slate-500">
          暂无可上架设备（仓库 / 空闲 / 下架设备池为空）。
        </div>
        <Form v-else :model="mountForm" :rules="mountRules">
          <DeviceFilterBar
            :model-value="filter"
            :type-options="DEVICE_TYPE_OPTIONS"
            @update:model-value="onFilterChange"
            class="mb-3"
          />
          <p v-if="!filteredCandidates.length" class="mb-3 text-center text-sm text-slate-500">
            无匹配「{{ filter.keyword || '' }}」的设备，请调整筛选条件。
          </p>
          <FormItem label="选择设备" name="device_id">
            <Select v-model="mountForm.device_id">
              <SelectTrigger placeholder="从候选设备中选择" />
              <SelectContent>
                <SelectItem v-for="d in filteredCandidates" :key="d.id" :value="d.id">
                  {{ d.name }}（{{ DEVICE_TYPE_LABELS[d.device_type] || d.device_type }}）
                </SelectItem>
              </SelectContent>
            </Select>
          </FormItem>
          <FormItem label="起始 U 位" name="start_u">
            <Input type="number" :min="1" :max="rack.total_u" v-model="mountForm.start_u" />
            <p class="text-xs text-slate-400 mt-1">机柜共 {{ rack.total_u }}U，自底向上计数。</p>
          </FormItem>
        </Form>
        <template #footer>
          <div class="flex justify-end gap-2">
            <Button variant="outline" @click="mountVisible = false">取消</Button>
            <Button :loading="mounting" :disabled="!candidates.length" @click="confirmMount">上架</Button>
          </div>
        </template>
      </Dialog>

      <!-- 编辑机柜弹窗 -->
      <RackForm v-model:visible="rackFormVisible" mode="edit" :rack-id="rackId" @saved="onRackSaved" />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRackStore } from '@/stores/rack'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import USlotMap from '@/components/rack/USlotMap.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import DeviceTypeTag from '@/components/device/DeviceTypeTag.vue'
import DeviceFilterBar from '@/components/device/DeviceFilterBar.vue'
import RackForm from '@/views/rack/RackForm.vue'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Button from '@/components/ui/button.vue'
import Card from '@/components/ui/card.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import { DEVICE_TYPE_OPTIONS, DEVICE_TYPE_COLORS, DEVICE_TYPE_LABELS } from '@/utils/constants'
import { PackagePlus, Pencil, ChevronLeft, Grid3x3, ListOrdered, Eye, Trash2, PackageX } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const store = useRackStore()
const auth = useAuthStore()
const { success, error } = useToast()
const { confirm } = useConfirm()
const rackId = route.params.id
// 机柜相关写操作（上架 / 编辑 / 删除 / 下架）均需 rack:edit；只读用户隐藏全部写按钮与拖拽上架交互。
const canEdit = computed(() => auth.hasPermission('rack:edit'))

const rack = computed(() => store.currentRack)
const devices = computed(() => store.devices)
const candidates = computed(() => store.candidates)
const uMap = computed(() => store.uMap)
// 页面级加载门控必须用【本地】loading，切勿绑定 store.loading。
// 原因：RackForm 预填时会调 store.fetchOne（内部会翻转 store.loading），若本页 loading 依赖
// store.loading，点击编辑会触发「store.loading=true→本页 v-if=loading 命中→含 RackForm 的内容区
// 被卸载→fetchOne 完 store.loading=false→又重挂 RackForm」的无限循环，导致表单永远停在空默认态、预填失效。
// 平面图（RoomFloorPlan）用本地 loading 所以正常；本页须与之一致。
const loading = ref(true)

const rackFormVisible = ref(false)
const mountVisible = ref(false)
const mounting = ref(false)
const mountForm = ref({ device_id: '', start_u: '' })
const mountRules = {
  device_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  start_u: [{ required: true, type: 'number', min: 1, message: '请输入起始 U 位', trigger: 'change' }],
}

// —— 统一筛选（上架设备弹窗 与 架下设备列表 共享同一 filter 状态）——
// 按设备名称、设备类型实时过滤候选设备池。
const filter = ref({ keyword: '', type: '' })
const filteredCandidates = computed(() => {
  let list = candidates.value
  const f = filter.value
  const kw = (f.keyword || '').trim().toLowerCase()
  if (kw) list = list.filter((d) => (d.name || '').toLowerCase().includes(kw))
  if (f.type) list = list.filter((d) => d.device_type === f.type)
  // 保留已选设备：筛选过程中不被移出，满足「保留当前已选中的设备状态」
  if (mountForm.value.device_id) {
    const sel = candidates.value.find((d) => d.id === mountForm.value.device_id)
    if (sel && !list.some((d) => d.id === sel.id)) list = [sel, ...list]
  }
  return list
})
function onFilterChange(v) {
  Object.assign(filter.value, v)
}

// 点击空闲 U 位或「上架设备」按钮：打开候选设备选择弹窗（预填起始 U 位）。
function openMount(u) {
  if (!canEdit.value) return
  mountForm.value = { device_id: '', start_u: u ? String(u) : '' }
  mountVisible.value = true
}
function onAddAtU(u) {
  openMount(u)
}
async function confirmMount() {
  if (!mountForm.value.device_id || !mountForm.value.start_u) {
    error('请选择设备并填写起始 U 位')
    return
  }
  mounting.value = true
  try {
    await store.mount(rackId, { device_id: mountForm.value.device_id, start_u: Number(mountForm.value.start_u) })
    success('上架成功')
    mountVisible.value = false
    await refreshAll()
  } catch (e) {
    // 冲突 / 校验错误已由统一拦截器提示
  } finally {
    mounting.value = false
  }
}
// 拖拽上架：拖放体落在某 U 位时触发（start_u 由 USlotMap 按设备高度换算）。
async function onDropMount({ device_id, start_u }) {
  if (!canEdit.value) return
  const dev = candidates.value.find((d) => d.id === device_id)
  mounting.value = true
  try {
    await store.mount(rackId, { device_id, start_u })
    success(`已将「${dev?.name || '设备'}」上架到 ${start_u}U`)
    await refreshAll()
  } catch (e) {
    // 冲突由拦截器提示
  } finally {
    mounting.value = false
  }
}
// 双击架下设备快速上架到首个空闲位（start_u=1，后端校验冲突）。
async function quickMount(dev) {
  if (!canEdit.value) return
  mounting.value = true
  try {
    await store.mount(rackId, { device_id: dev.id, start_u: 1 })
    success(`已将「${dev.name}」上架到 U1`)
    await refreshAll()
  } catch (e) {
    // 冲突由拦截器提示
  } finally {
    mounting.value = false
  }
}
// 下架设备：释放 U 位并同步设备状态。支持直接传 id（图内下架按钮 / 列表按钮）。
async function onUnmountId(id) {
  if (!canEdit.value) return
  const dev = devices.value.find((d) => d.id === id) || candidates.value.find((d) => d.id === id)
  const ok = await confirm({
    title: '下架设备',
    description: `确认将设备「${dev?.name || '该设备'}」从机柜下架？`,
    variant: 'danger',
    confirmText: '下架',
  })
  if (!ok) return
  try {
    await store.unmount(rackId, { device_id: id })
    success('下架成功')
    await refreshAll()
  } catch (e) {
    // 拦截器提示
  }
}
function onDragStart(e, d) {
  // 无编辑权限时直接拒绝拖拽（与平面图一致：拖拽动作根本不触发）。
  if (!canEdit.value) {
    e.preventDefault()
    return
  }
  e.dataTransfer.setData('text/plain', d.id)
  e.dataTransfer.effectAllowed = 'move'
}
function goDevice(id) {
  router.push(`/devices/${id}`)
}
function goBack() {
  router.back()
}
async function refreshAll() {
  await Promise.all([
    store.fetchOne(rackId),
    store.fetchDevices(rackId),
    store.fetchUMap(rackId),
    store.fetchCandidates(rackId),
  ])
}
async function onRackSaved() {
  await Promise.all([store.fetchOne(rackId), store.fetchUMap(rackId)])
}
async function onDelete() {
  const ok = await confirm({
    title: '删除机柜',
    description: '确认删除该机柜？删除前需先下架其内所有设备。',
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.remove(rackId)
    success('删除成功')
    router.push('/racks')
  } catch (e) {
    // 拦截器提示（如仍有设备占用）
  }
}

onMounted(async () => {
  try {
    await store.fetchOne(rackId)
    await Promise.all([store.fetchDevices(rackId), store.fetchUMap(rackId), store.fetchCandidates(rackId)])
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.offrack-scroll {
  /* 内部滚动，避免整页过长 */
}
.offrack-item {
  border: 1px solid #eef0f4;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
  background: #fff;
  cursor: grab;
  transition: box-shadow 0.15s, border-color 0.15s, transform 0.1s;
}
.offrack-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 10px rgba(64, 158, 255, 0.18);
}
.offrack-item:active {
  cursor: grabbing;
  transform: scale(0.99);
}
.offrack-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}
</style>
