<template>
  <!-- 设备硬件卡片：展示该设备已安装的硬件（一对一关联，每件硬件独立追踪） -->
  <Card class="mb-5">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span class="section-title flex items-center gap-1.5">
          <Cpu class="h-4 w-4" />设备硬件（{{ store.deviceHardwares.length }}）
        </span>
        <div class="flex items-center gap-2">
          <Button v-if="canEdit" size="sm" @click="assignVisible = true"><Plus class="h-4 w-4" />添加硬件</Button>
        </div>
      </div>
    </template>

    <div v-if="loading" class="flex justify-center py-10">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <template v-else-if="store.deviceHardwares.length">
      <!-- 表格：硬件名称 / 类型 / 品牌 / SN / 规格 / 安装时间 / 操作 -->
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>硬件</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>品牌</TableHead>
            <TableHead>SN 号</TableHead>
            <TableHead>规格</TableHead>
            <TableHead>安装时间</TableHead>
            <TableHead class="w-24 text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="hw in store.deviceHardwares" :key="hw.id">
            <TableCell>
              <button class="font-medium text-primary hover:underline" @click="openHistory(hw)">{{ hw.name }}</button>
            </TableCell>
            <TableCell>
              <span
                class="shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium"
                :style="typeBadgeStyle(hw.type_id)"
              >{{ hw.type_name || '—' }}</span>
            </TableCell>
            <TableCell class="text-muted-foreground">{{ hw.brand || '—' }}</TableCell>
            <TableCell class="font-mono text-muted-foreground">{{ hw.sn || '—' }}</TableCell>
            <TableCell class="text-muted-foreground">{{ hw.spec || '—' }}</TableCell>
            <TableCell class="text-muted-foreground">{{ formatTime(hw.assigned_at) }}</TableCell>
            <TableCell class="text-right">
              <div class="flex justify-end gap-1">
                <Button variant="ghost" size="sm" @click="openHistory(hw)"><History class="h-3.5 w-3.5" /></Button>
                <Button v-if="canEdit" variant="ghost" size="sm" class="text-destructive hover:bg-destructive/10" @click="onRecover(hw)"><Undo2 class="h-3.5 w-3.5" /></Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </template>
    <div v-else class="flex flex-col items-center justify-center py-10 text-sm text-muted-foreground">
      <Cpu class="mb-2 h-8 w-8 opacity-40" />
      <span>该设备暂未安装硬件</span>
      <span class="mt-1 text-xs text-muted-foreground/70">点击右上角「添加硬件」从硬件管理中分配（与机柜上架选设备同理）</span>
    </div>

    <!-- 添加硬件弹窗（从硬件管理「在库」列表选择具体某件） -->
    <Dialog v-model="assignVisible" title="添加硬件" class="max-w-2xl" :dismissible="false">
      <div class="space-y-3">
        <!-- 筛选：类型 / 关键字 -->
        <div class="flex flex-wrap items-end gap-3">
          <div class="flex flex-col gap-1">
            <Label class="text-xs text-muted-foreground">硬件类型</Label>
            <Select v-model="pickTypeId" class="w-40" @update:model-value="onPickTypeChange">
              <SelectTrigger placeholder="全部类型" />
              <SelectContent>
                <SelectItem :value="SELECT_ALL">全部类型</SelectItem>
                <SelectItem v-for="t in store.types" :key="t.id" :value="t.id">{{ t.name }}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="flex flex-col gap-1">
            <Label class="text-xs text-muted-foreground">关键字</Label>
            <div class="relative">
              <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input v-model="pickKeyword" placeholder="名称 / 品牌 / SN" class="w-48 pl-8" @keyup.enter="onPickQuery" />
            </div>
          </div>
          <div class="flex items-center gap-2 pb-1">
            <!-- 修复：@click 不能直接绑 loadAvailable——Vue 会把 MouseEvent 当参数传入，
                 导致 pickPage 被赋成事件对象、page 参数序列化非法 → 后端 422「参数校验失败」。
                 改为显式箭头函数调用，不传事件对象。 -->
            <Button size="sm" variant="outline" @click="onPickQuery"><Filter class="h-3.5 w-3.5" />查询</Button>
            <!-- 风格与「查询」一致（outline），同排操作按钮视觉统一 -->
            <Button size="sm" variant="outline" @click="onPickReset"><Undo2 class="h-3.5 w-3.5" />重置</Button>
          </div>
        </div>

        <!-- 在库硬件候选列表 -->
        <div v-if="pickLoading" class="flex justify-center py-8">
          <Spinner class="h-5 w-5 text-primary" />
        </div>
        <div v-else-if="!availableItems.length" class="py-8 text-center text-sm text-muted-foreground">
          暂无「在库」硬件可分配（请先在硬件管理中新建硬件）
        </div>
        <div v-else class="max-h-72 space-y-1 overflow-y-auto pr-1">
          <div
            v-for="hw in availableItems"
            :key="hw.id"
            class="flex cursor-pointer items-center justify-between gap-3 rounded-md border border-border px-3 py-2 transition-colors"
            :class="selectedHwId === hw.id ? 'border-primary bg-primary/10' : 'hover:bg-muted'"
            @click="selectedHwId = hw.id"
          >
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span class="truncate text-sm font-medium text-foreground">{{ hw.name }}</span>
                <span
                  class="shrink-0 rounded-full border px-1.5 py-0.5 text-[11px] font-medium"
                  :style="typeBadgeStyle(hw.type_id)"
                >{{ hw.type_name }}</span>
              </div>
              <div class="mt-0.5 truncate text-xs text-muted-foreground">
                <span v-if="hw.brand">{{ hw.brand }}</span>
                <span v-if="hw.sn" class="font-mono"> · SN: {{ hw.sn }}</span>
                <span v-if="hw.spec"> · {{ hw.spec }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-between">
          <ListPager v-if="availableTotal > 0" :total="availableTotal" :page="pickPage" :page-size="pickSize" @change="pickGoPage" />
          <div class="flex gap-2">
            <Button variant="outline" @click="assignVisible = false">取消</Button>
            <Button :loading="assigning" :disabled="!selectedHwId" @click="onAssign">确认添加</Button>
          </div>
        </div>
      </template>
    </Dialog>

    <!-- 硬件变动历史弹窗 -->
    <HardwareHistoryDialog v-model:visible="historyVisible" :item="historyItem" />
  </Card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Cpu, Plus, History, Undo2, Search, Filter } from 'lucide-vue-next'
import { useHardwareStore } from '@/stores/hardware'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import HardwareHistoryDialog from '@/views/hardware/HardwareHistoryDialog.vue'
import {
  SELECT_ALL, toFilterParam,
  hardwareTypeBadgeStyle as typeBadgeStyle, setHardwareTypeOrder,
} from '@/utils/constants'
import { formatDateTime } from '@/utils/datetime'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Card from '@/components/ui/card.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import Spinner from '@/components/ui/spinner.vue'
import ListPager from '@/components/common/ListPager.vue'
import Dialog from '@/components/ui/dialog.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'

const props = defineProps({
  deviceId: { type: [String, Number], required: true },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['mutated'])

const store = useHardwareStore()
const auth = useAuthStore()
const { success } = useToast()
const { confirm } = useConfirm()
const formatTime = formatDateTime

const loading = ref(false)
const historyVisible = ref(false)
const historyItem = ref(null)

watch(
  () => store.types,
  (list) => setHardwareTypeOrder((list || []).map((t) => t.id)),
  { immediate: true },
)

async function load() {
  loading.value = true
  try {
    await store.fetchDeviceHardwares(props.deviceId)
  } finally {
    loading.value = false
  }
}

function openHistory(hw) {
  historyItem.value = hw
  historyVisible.value = true
}

async function onRecover(hw) {
  const ok = await confirm({
    title: '回收硬件',
    description: `确认将该硬件「${hw.name}」${hw.sn ? `（SN: ${hw.sn}）` : ''}从本设备回收？回收后硬件回到「在库」，可在硬件管理中重新分配。`,
    variant: 'danger',
    confirmText: '回收',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await store.unassignFromDevice(props.deviceId, hw.id)
    success('已回收，硬件回到在库')
    await load()
    emit('mutated')
  } catch (e) {
    // 拦截器已提示
  }
}

// ===== 添加硬件弹窗 =====
const assignVisible = ref(false)
const availableItems = ref([])
const availableTotal = ref(0)
const pickLoading = ref(false)
const assigning = ref(false)
const pickTypeId = ref(SELECT_ALL)
const pickKeyword = ref('')
const selectedHwId = ref('')
const pickPage = ref(1)
const pickSize = 8

async function loadAvailable(p = 1) {
  pickPage.value = p
  pickLoading.value = true
  try {
    const data = await store.fetchAvailableItems({
      page: p,
      size: pickSize,
      type_id: toFilterParam(pickTypeId.value),
      keyword: pickKeyword.value || undefined,
    })
    availableItems.value = data.items || []
    availableTotal.value = data.total || 0
  } catch (e) {
    availableItems.value = []
    availableTotal.value = 0
  } finally {
    pickLoading.value = false
  }
}
function pickGoPage(p) {
  loadAvailable(p)
}
// 查询：显式传 1，避免事件对象混入（见模板注释）。
function onPickQuery() {
  loadAvailable(1)
}
// 重置：清空查询条件（类型回「全部」、关键字清空、页码回 1）并重新加载候选池。
function onPickReset() {
  pickTypeId.value = SELECT_ALL
  pickKeyword.value = ''
  selectedHwId.value = ''
  loadAvailable(1)
}
async function onPickTypeChange() {
  selectedHwId.value = ''
  loadAvailable(1)
}

async function onAssign() {
  if (!selectedHwId.value || assigning.value) return
  assigning.value = true
  try {
    await store.assignToDevice(props.deviceId, { hardware_item_id: selectedHwId.value })
    success('已添加硬件到设备')
    assignVisible.value = false
    selectedHwId.value = ''
    await load()
    emit('mutated')
  } catch (e) {
    // 拦截器已提示（如该硬件已被其他设备占用）
  } finally {
    assigning.value = false
  }
}

watch(assignVisible, (v) => {
  if (v) {
    selectedHwId.value = ''
    pickTypeId.value = SELECT_ALL
    pickKeyword.value = ''
    // 确保类型下拉有数据。
    if (!store.types.length) store.fetchTypes()
    loadAvailable(1)
  }
})

onMounted(load)
</script>
