<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title flex items-center gap-2">
          <ScrollText class="h-6 w-6 text-primary" /> 操作审计
        </h1>
        <p class="page-sub">记录「谁在什么时间对什么对象做了什么操作」，覆盖增删改与导入 / 导出</p>
      </div>
      <Button :loading="loading" @click="load">
        <RefreshCw class="h-4 w-4" /> 刷新
      </Button>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="对象名 / 详情 / 操作人" class="w-56 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <Label>模块</Label>
          <Select v-model="filter.module" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="m in moduleOptions" :key="m" :value="m">{{ moduleLabel(m) }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>操作</Label>
          <Select v-model="filter.action" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="a in actionOptions" :key="a" :value="a">{{ actionLabel(a) }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>操作人</Label>
          <Input v-model="filter.operator" placeholder="操作人" class="w-36" @keyup.enter="reload" />
        </div>
        <div class="flex flex-col gap-1">
          <Label>时间范围</Label>
          <div class="flex items-center gap-2">
            <Input type="date" v-model="filter.start_date" class="w-40" @change="reload" />
            <span class="text-muted-foreground">至</span>
            <Input type="date" v-model="filter.end_date" class="w-40" @change="reload" />
          </div>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <!-- 审计日志：虚拟滚动表（变高行自动测量），大批量记录下 DOM 有界、滚动流畅 -->
    <VirtualTable
      :columns="auditColumns"
      :rows="rows"
      :row-height="64"
      :height="560"
      key-field="id"
      :loading="loading"
      empty-text="暂无审计记录"
    >
      <template #row="{ row }">
        <div class="vt-cell px-3 tabular-nums text-muted-foreground">{{ formatTime(row.created_at) }}</div>
        <div class="vt-cell px-3">
          <span class="font-medium">{{ row.operator_name || '—' }}</span>
          <span v-if="row.ip" class="block text-xs text-muted-foreground">{{ row.ip }}</span>
        </div>
        <div class="vt-cell px-3 text-sm text-muted-foreground">{{ moduleLabel(row.module) }}</div>
        <div class="vt-cell px-3">
          <Badge :variant="actionBadge(row.action)">{{ actionLabel(row.action) }}</Badge>
        </div>
        <div class="vt-cell px-3">
          <button
            v-if="objectLink(row)"
            type="button"
            class="font-medium text-primary hover:underline"
            @click="goObject(row)"
          >{{ row.object_name || '—' }}</button>
          <span v-else class="font-medium">{{ row.object_name || '—' }}</span>
        </div>
        <div class="vt-cell px-3 text-sm">
          <!-- 更新类：字段级 diff（直接说明改了什么） -->
          <template v-if="row.view.kind === 'diff'">
            <div
              v-for="c in row.view.changes"
              :key="c.label"
              class="flex flex-wrap items-center gap-1.5 leading-6"
            >
              <span class="font-medium text-foreground/80">{{ c.label }}：</span>
              <span class="text-destructive line-through">{{ c.old }}</span>
              <ArrowRight class="h-3 w-3 shrink-0 text-muted-foreground" />
              <span class="font-medium text-success">{{ c.new }}</span>
            </div>
            <div v-if="row.view.notes && row.view.notes.length" class="flex flex-wrap gap-x-3 gap-y-1 pt-0.5">
              <span
                v-for="n in row.view.notes"
                :key="n.label"
                class="text-warning"
              >{{ n.label }}：{{ n.text }}</span>
            </div>
          </template>
          <span v-else-if="row.view.kind === 'none'" class="text-muted-foreground">未修改字段</span>
          <span v-else class="text-muted-foreground">{{ cleanDetail(row) }}</span>
        </div>
      </template>
    </VirtualTable>

    <ListPager
      v-if="total > 0"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @change="goPage"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ScrollText,
  RefreshCw,
  Search,
  Filter,
  Undo2,
  ArrowRight,
} from 'lucide-vue-next'
import { formatDateTime } from '@/utils/datetime'
import auditApi from '@/api/audit'
import { SELECT_ALL } from '@/utils/constants'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Badge from '@/components/ui/badge.vue'
import ListPager from '@/components/common/ListPager.vue'
import VirtualTable from '@/components/common/VirtualTable.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'

const formatTime = formatDateTime
const router = useRouter()

// 对象列可点击跳转：机柜 / 设备 / 机房 三类实体支持跳转到对应详情页。
const CLICKABLE_TYPES = {
  设备: 'DeviceDetail',
  机柜: 'RackDetail',
  机房: 'RoomDetail',
}
function objectLink(log) {
  const name = CLICKABLE_TYPES[log.object_type]
  if (name && log.object_id) return { name, params: { id: log.object_id } }
  return null
}
function goObject(log) {
  const link = objectLink(log)
  if (link) router.push(link)
}

const MODULE_LABELS = {
  room: '机房',
  rack: '机柜',
  device: '设备',
  account: '账号',
  interface: '接口',
  link: '连接',
  consumable: '耗材',
  import: '导入',
  export: '导出',
  system: '系统',
}
const ACTION_LABELS = {
  create: '创建',
  update: '更新',
  delete: '删除',
  restore: '恢复',
  purge: '彻底删除',
  import: '导入',
  export: '导出',
  login: '登录',
}
// 操作 → Badge 变体（语义化配色，用于「操作」列）。
const ACTION_BADGE = {
  create: 'success',
  restore: 'success',
  update: 'default',
  import: 'default',
  export: 'default',
  login: 'secondary',
  delete: 'warning',
  purge: 'destructive',
}

function moduleLabel(m) {
  return MODULE_LABELS[m] || m
}
function actionLabel(a) {
  return ACTION_LABELS[a] || a
}
function actionBadge(a) {
  return ACTION_BADGE[a] || 'secondary'
}

// —— 审计详情结构化解析 ——
// 更新类详情形如「字段A：旧 → 新；字段B：旧 → 新」或「无字段变更」；
// 非更新类为自由文本（如「导入机房：成功 10 个…」）。解析为 diff 视图所需结构。
// 兼容历史数据：旧版后端在详情前拼接了「更新设备（编号 X）：」「新增机柜：」等前缀，
// 该类前缀与新解析逻辑冲突（会被误判为字段名）。解析前先剥离。
function stripLegacyPrefix(s) {
  return (s || '').replace(/^(?:新增|更新|删除|导入|导出|批量新增)[^：：]*[：:]\s*/, '')
}

function parseDetail(detail) {
  if (!detail) return { kind: 'raw', text: detail }
  if (detail === '无字段变更') return { kind: 'none' }
  const changes = []
  const notes = []
  detail = stripLegacyPrefix(detail)
  detail.split('；').forEach((seg) => {
    const ci = seg.indexOf('：')
    if (ci === -1) return
    const label = seg.slice(0, ci)
    const body = seg.slice(ci + 1).trim()
    const ai = body.indexOf(' → ')
    if (ai !== -1) {
      // 字段变更：旧值 → 新值
      changes.push({ label, old: body.slice(0, ai), new: body.slice(ai + 3) })
    } else if (body) {
      // 无 → 的说明型备注（如「密码：已更新」「权限：已更新」）
      notes.push({ label, text: body })
    }
  })
  if (!changes.length && !notes.length) return { kind: 'raw', text: detail }
  return { kind: 'diff', changes, notes }
}

// 仅「更新」操作尝试解析为 diff；其余操作原样展示文本（去冗余在 cleanDetail 处理）。
function detailView(log) {
  if (log.action !== 'update') return { kind: 'raw', text: log.detail }
  return parseDetail(log.detail)
}

// 操作 → 中文动词（用于详情列去冗余时剥离「动作+类型」前缀）。
const ACTION_VERB = {
  create: '创建',
  update: '更新',
  delete: '删除',
  restore: '恢复',
  purge: '彻底删除',
  import: '导入',
  export: '导出',
  login: '登录',
}

function re(s) {
  return (s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 详情列去冗余：去掉已在「模块 / 操作 / 对象」列体现的信息，剩余为空则统一显示「-」。
function cleanDetail(log) {
  const raw = stripLegacyPrefix((log.detail || '').trim())
  if (!raw) return '—'
  if (log.action === 'login') return '—' // 「登录成功」与「操作=登录」重复

  // 上架 / 下架记录：详情承载「机柜 / U 位 / 操作人」等独有信息，仅去除重复的「对象名」与「操作人」
  if (log.object_type === '上架记录') {
    let t = raw
    const on = log.object_name || ''
    if (on) t = t.replace(new RegExp(`[「（(]${re(on)}[」)）]\\s*`), ' ')
    t = t.replace(/[（(]操作人[：:][^（）()]*[）)]/g, '')
    return t.replace(/[；;，,:\s]+$/, '').trim() || '—'
  }

  const ot = log.object_type || ''
  const on = log.object_name || ''
  const verb = ACTION_VERB[log.action] || ''

  let s = raw
  // 创建类：按「；」分段，去掉与「对象」列重复的对象标识字段（名称 / 编号 / 机柜编号 / 设备编号 / 用户名 / 账号）
  if (log.action === 'create') {
    const ID_LABELS = ['名称', '编号', '机柜编号', '设备编号', '用户名', '账号']
    s = raw
      .split('；')
      .map((x) => x.trim())
      .filter(Boolean)
      .filter((seg) => {
        const ci = seg.indexOf('：')
        if (ci === -1) return true
        return !ID_LABELS.includes(seg.slice(0, ci))
      })
      .join('；')
  }

  // 去掉「动作+类型」「批量新增+类型」前缀，以及零散的对象引用（「A-06」/（A-06）等）
  if (verb && ot) {
    s = s.replace(new RegExp(`^${re(verb)}${re(ot)}[：:]?\\s*`), '')
    s = s.replace(new RegExp(`^批量新增${re(ot)}[：:]?\\s*`), '')
  }
  if (on) {
    s = s.replace(new RegExp(`[「（(]${re(on)}[」)）]\\s*`), ' ')
  }
  // 去掉最外层包裹括号，并清理首尾标点 / 空白
  s = s.replace(/^[（(]([\s\S]*?)[)）]\s*$/, '$1')
  s = s.replace(/^[；;，,:\s]+/, '').replace(/[；;，,:\s]+$/, '').trim()
  return s || '—'
}

// 下拉框选项：移除冗余项（操作：彻底删除 / 恢复；模块：导入 / 导出——仅保留真实实体模块）。
const moduleOptions = Object.keys(MODULE_LABELS).filter((m) => m !== 'import' && m !== 'export')
const actionOptions = Object.keys(ACTION_LABELS).filter((a) => a !== 'restore' && a !== 'purge')

// 虚拟表列定义：与详情渲染顺序一致；grid 模板由 VirtualTable 统一推导，列宽自适应对齐。
const auditColumns = [
  { key: 'created_at', label: '时间', width: '10rem' },
  { key: 'operator_name', label: '操作人', width: '7rem' },
  { key: 'module', label: '模块', width: '5rem' },
  { key: 'action', label: '操作', width: '5rem' },
  { key: 'object_name', label: '对象', width: '12rem' },
  { key: 'detail', label: '详情', width: 'minmax(280px, 1fr)' },
]

const logs = ref([])
// 行数据：在 load() 回调中与 logs 同步赋值（对齐 DeviceList/RackListPanel 的直传 ref 模式，
// 避免 computed 每次重建对象引用导致 @tanstack/vue-virtual 虚拟器状态异常）。
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const filter = reactive({ keyword: '', module: SELECT_ALL, action: SELECT_ALL, operator: '', start_date: '', end_date: '' })

function buildParams() {
  const p = { page: page.value, size: pageSize.value }
  if (filter.keyword.trim()) p.keyword = filter.keyword.trim()
  if (filter.module !== SELECT_ALL) p.module = filter.module
  if (filter.action !== SELECT_ALL) p.action = filter.action
  if (filter.operator.trim()) p.operator = filter.operator.trim()
  if (filter.start_date) p.start_time = filter.start_date
  if (filter.end_date) p.end_time = filter.end_date
  return p
}

async function load() {
  loading.value = true
  try {
    const data = await auditApi.list(buildParams())
    logs.value = data.items || []
    rows.value = (data.items || []).map((l) => ({ ...l, view: detailView(l) }))
    total.value = data.total || 0
    if (logs.value.length === 0 && page.value > 1) {
      page.value = 1
      const again = await auditApi.list(buildParams())
      logs.value = again.items || []
      rows.value = (again.items || []).map((l) => ({ ...l, view: detailView(l) }))
      total.value = again.total || 0
    }
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
  filter.keyword = ''
  filter.module = SELECT_ALL
  filter.action = SELECT_ALL
  filter.operator = ''
  filter.start_date = ''
  filter.end_date = ''
  reload()
}

onMounted(load)
</script>
