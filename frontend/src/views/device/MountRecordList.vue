<template>
  <div class="mount-record-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">上下架记录</h2>
        <p class="page-sub">共 {{ total }} 条记录 · 资产追踪 / 交接审计 / 历史回溯（与设备详情页数据同源）</p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" :loading="exporting" @click="onExport"><Download class="h-4 w-4" />导出</Button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>设备名称</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.deviceName" placeholder="设备名称（模糊）" class="w-48 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <Label>设备编号</Label>
          <div class="relative">
            <Hash class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.deviceCode" placeholder="如 DEV-ABCD1234" class="w-48 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <Label>操作类型</Label>
          <Select v-model="filter.opType" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem value="上架">上架</SelectItem>
              <SelectItem value="下架">下架</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>起始时间</Label>
          <Input
            v-model="filter.startTime"
            type="datetime-local"
            class="w-56 cursor-pointer"
            @change="reload"
            @click="openPicker($event)"
          />
        </div>
        <div class="flex flex-col gap-1">
          <Label>截止时间</Label>
          <Input
            v-model="filter.endTime"
            type="datetime-local"
            class="w-56 cursor-pointer"
            @change="reload"
            @click="openPicker($event)"
          />
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>设备名称</TableHead>
          <TableHead>设备编号</TableHead>
          <TableHead>操作类型</TableHead>
          <TableHead>操作人</TableHead>
          <TableHead>操作时间</TableHead>
          <TableHead>上架/下架位置</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in items" :key="row.id + '-' + row.event_type">
          <TableCell>
            <button v-if="row.device_id" class="font-medium text-primary hover:underline" @click="goDevice(row.device_id)">{{ row.device_name || '—' }}</button>
            <span v-else>{{ row.device_name || '—' }}</span>
          </TableCell>
          <TableCell class="font-mono text-muted-foreground">{{ row.device_code || '—' }}</TableCell>
          <TableCell>
            <span class="inline-flex items-center gap-1.5">
              <i class="hist-dot" :class="row.event_type === '上架' ? 'hist-dot--mount' : 'hist-dot--unmount'"></i>
              {{ row.event_type }}
            </span>
          </TableCell>
          <TableCell class="text-muted-foreground">{{ row.operator || '—' }}</TableCell>
          <TableCell class="text-muted-foreground">{{ formatTime(row.operated_at) }}</TableCell>
          <TableCell class="text-muted-foreground">{{ row.position }}</TableCell>
        </TableRow>
      </TableBody>
    </Table>
    <EmptyState v-if="!loading && items.length === 0" title="暂无上下架记录" />

    <!-- 分页 -->
    <ListPager v-if="!loading && total > 0" :total="total" :page="page" :page-size="pageSize" @change="goPage" />
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import mountRecordApi from '@/api/mountRecord'
import { SELECT_ALL, toFilterParam } from '@/utils/constants'
import { Search, Filter, Undo2, Download, Hash } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import ListPager from '@/components/common/ListPager.vue'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/datetime'

const formatTime = formatDateTime

const router = useRouter()
const { error } = useToast()

// 持久化筛选（路由名 MountRecordList）。
const { filter, clear } = usePersistentFilter(
  'MountRecordList',
  () => ({ deviceName: '', deviceCode: '', opType: SELECT_ALL, startTime: '', endTime: '' })
)

// 点击时间输入框任意位置即弹出原生日期时间面板（不仅限右侧图标）。
// 用 $event.target 直接拿原生 input 元素调用 showPicker()（HTML 标准 API，Chrome/Edge/Firefox 支持）。
function openPicker(e) {
  const el = e.target
  if (el && typeof el.showPicker === 'function') {
    try {
      el.showPicker()
    } catch {
      // 已打开或浏览器不支持时忽略。
    }
  }
}

const items = ref([])
const total = ref(0)
const loading = ref(false)
const exporting = ref(false)
const page = ref(1)
const pageSize = ref(20)

// datetime-local 值（YYYY-MM-DDTHH:mm）转 ISO8601 字符串（含时区偏移交由后端解析）。
function toIsoLocal(v) {
  if (!v) return undefined
  // datetime-local 无时区信息，按本地时间追加 :00 秒，后端用 naive datetime 解析。
  return v.length === 16 ? `${v}:00` : v
}

function buildParams() {
  return {
    page: page.value,
    size: pageSize.value,
    device_name: filter.deviceName || undefined,
    device_code: filter.deviceCode || undefined,
    op_type: toFilterParam(filter.opType),
    start_time: toIsoLocal(filter.startTime),
    end_time: toIsoLocal(filter.endTime),
  }
}

async function load() {
  loading.value = true
  try {
    const data = await mountRecordApi.list(buildParams())
    items.value = data.items || []
    total.value = data.total || 0
    if (items.value.length === 0 && page.value > 1 && total.value > 0) {
      page.value = Math.max(1, Math.ceil(total.value / pageSize.value))
      await load()
    }
  } catch (e) {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function goPage(p) {
  page.value = p
  load()
}

function resetFilter() {
  clear()
  reload()
}

function goDevice(id) {
  router.push(`/devices/${id}`)
}

// 导出：拉取全量匹配记录 → ExcelJS 生成 .xlsx。
async function onExport() {
  exporting.value = true
  try {
    const params = buildParams()
    delete params.page
    delete params.size
    const rows = await mountRecordApi.exportAll(params)
    if (!Array.isArray(rows) || rows.length === 0) {
      error('当前筛选条件下没有可导出的记录')
      return
    }
    const ExcelJS = (await import('exceljs')).default
    const wb = new ExcelJS.Workbook()
    const ws = wb.addWorksheet('上下架记录')
    ws.columns = [
      { header: '设备名称', key: 'device_name', width: 24 },
      { header: '设备编号', key: 'device_code', width: 16 },
      { header: '操作类型', key: 'event_type', width: 10 },
      { header: '操作人', key: 'operator', width: 14 },
      { header: '操作时间', key: 'operated_at', width: 22 },
      { header: '上架/下架位置', key: 'position', width: 48 },
    ]
    rows.forEach((r) => {
      ws.addRow({
        device_name: r.device_name || '—',
        device_code: r.device_code || '—',
        event_type: r.event_type,
        operator: r.operator || '—',
        operated_at: formatTime(r.operated_at),
        position: r.position,
      })
    })
    // 表头加粗。
    ws.getRow(1).font = { bold: true }
    const buffer = await wb.xlsx.writeBuffer()
    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const stamp = new Date().toISOString().slice(0, 10)
    a.href = url
    a.download = `上下架记录_${stamp}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    // 拦截器已提示
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
}
.page-sub {
  margin: 0;
  color: #606266;
  font-size: 13px;
}
.toolbar {
  background: oklch(var(--card) / 0.8);
  border: 1px solid oklch(var(--border) / 0.6);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
  backdrop-filter: blur(8px);
}
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
</style>
