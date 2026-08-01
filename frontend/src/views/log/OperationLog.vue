<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title flex items-center gap-2">
          <FileText class="h-6 w-6 text-primary" /> 操作日志
        </h1>
        <p class="page-sub">记录每一次写操作：谁、做了什么（含具体详情）、操作了哪个对象、结果如何与来源 IP。点击「详情」查看改了什么字段、上架到哪、链路两端等完整信息。</p>
      </div>
      <div class="flex items-center gap-2">
        <Button :loading="loading" @click="load">
          <RefreshCw class="h-4 w-4" /> 刷新
        </Button>
        <LogCleanupDialog @cleaned="load" />
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1.5">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="路径 / 操作人 / 对象名" class="w-60 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1.5">
          <Label>操作</Label>
          <Select v-model="filter.action" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="a in actionOptions" :key="a.value" :value="a.value">{{ a.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1.5">
          <Label>资源类型</Label>
          <Select v-model="filter.resource" class="w-40" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="r in resourceOptions" :key="r.value" :value="r.value">{{ r.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1.5">
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

    <!-- 操作日志：整页布局、跟随浏览器滚动，无内部独立滚动条（单页已分页、行数可控） -->
    <VirtualTable
      :columns="columns"
      :rows="rows"
      :virtual="false"
      key-field="id"
      :loading="loading"
      empty-text="暂无操作日志"
    >
      <template #row="{ row }">
        <div class="vt-cell px-3 py-3.5 tabular-nums text-muted-foreground whitespace-nowrap">{{ formatTime(row.created_at) }}</div>
        <div class="vt-cell px-3 py-3.5 whitespace-nowrap font-medium">{{ row.operator_name || '游客' }}</div>
        <div class="vt-cell px-3 py-3.5">
          <span class="status-dot" :class="statusDotClass(row.status_code)" :title="`${statusLabel(row.status_code)} · HTTP ${row.status_code}`"></span>
          <span class="op-verb" :class="actionBadgeClass(row.action || row.method)">{{ verbOf(row) }}</span>
        </div>
        <div class="vt-cell px-3 py-3.5">
          <span class="res-type-pill">{{ resLabel(row.resource) }}</span>
        </div>
        <div class="vt-cell px-3 py-3.5">
          <span v-if="targetOf(row)" class="target-chip" :title="targetOf(row)">{{ targetOf(row) }}</span>
          <span v-else class="text-muted-foreground">—</span>
        </div>
        <div class="vt-cell px-3 py-3.5 text-sm text-muted-foreground whitespace-nowrap">{{ row.ip || '—' }}</div>
        <div class="vt-cell px-3 py-3.5 whitespace-nowrap">
          <button
            class="detail-btn"
            :class="{ 'is-empty': !hasDetail(row.detail) }"
            @click="openDetail(row)"
          >{{ hasDetail(row.detail) ? '详情' : '无详情' }}</button>
        </div>
      </template>
    </VirtualTable>

    <ListPager v-if="total > 0" :total="total" :page="page" :page-size="pageSize" @change="goPage" />

    <!-- 操作详情弹窗：Teleport 到 body，避免被布局祖先的 overflow/transform 裁剪导致「点不开」 -->
    <Teleport to="body">
      <div v-if="detailOpen" class="modal-mask" @click.self="detailOpen = false">
        <div class="modal-panel" role="dialog" aria-modal="true">
          <div class="modal-head">
            <span class="modal-title">操作详情</span>
            <button class="modal-close" aria-label="关闭" @click="detailOpen = false">✕</button>
          </div>
          <div class="modal-body">
            <!-- 元信息条：一眼看清操作上下文（操作人 / 时间 / 操作 / 对象 / 状态） -->
            <div v-if="activeRow" class="meta-card">
              <div class="meta-item">
                <span class="meta-k">操作</span>
                <span class="meta-v">
                  <span class="op-verb" :class="actionBadgeClass(activeRow.action || activeRow.method)">{{ verbOf(activeRow) }}</span>
                </span>
              </div>
              <div class="meta-item">
                <span class="meta-k">操作人</span>
                <span class="meta-v">{{ activeRow.operator_name || '游客' }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-k">时间</span>
                <span class="meta-v">{{ formatTime(activeRow.created_at) }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-k">资源</span>
                <span class="meta-v">{{ resLabel(activeRow.resource) }}</span>
              </div>
              <div class="meta-item meta-item--wide">
                <span class="meta-k">操作对象</span>
                <span class="meta-v">{{ targetOf(activeRow) || '—' }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-k">状态</span>
                <span class="meta-v">
                  <span class="status-dot" :class="statusDotClass(activeRow.status_code)"></span>
                  {{ statusLabel(activeRow.status_code) }}
                </span>
              </div>
              <div class="meta-item meta-item--wide">
                <span class="meta-k">来源 IP</span>
                <span class="meta-v font-mono text-xs">{{ activeRow.ip || '—' }}</span>
              </div>
            </div>

            <div v-if="!hasDetail(activeDetail)" class="text-muted-foreground text-sm py-2">该记录无详细内容（历史数据、读请求或导入/导出）。</div>
            <template v-else>
              <!-- 修改类操作：字段级变更（原值 → 新值） -->
              <div v-if="diffItems(activeDetail).length" class="diff-block">
                <div class="diff-head">变更字段（原值 → 新值）</div>
                <div v-for="(d, i) in diffItems(activeDetail)" :key="'d' + i" class="detail-row diff-row">
                  <dt class="detail-label">{{ d.label }}</dt>
                  <dd class="detail-value">
                    <span class="diff-old">{{ d.old }}</span>
                    <span class="diff-arrow">→</span>
                    <span class="diff-new">{{ d.new }}</span>
                  </dd>
                </div>
              </div>
              <!-- 删除类操作：展示删除前快照（仅 DELETE 显示全量旧值） -->
              <div v-else-if="isDeleteAction(activeRow) && oldItems(activeDetail).length" class="diff-block">
                <div class="diff-head">删除前内容</div>
                <dl class="detail-list">
                  <div v-for="(item, i) in oldItems(activeDetail)" :key="'o' + i" class="detail-row">
                    <dt class="detail-label">{{ item.label }}</dt>
                    <dd class="detail-value">{{ item.value }}</dd>
                  </div>
                </dl>
              </div>
              <!-- 新增/默认：请求体字段 -->
              <dl v-else class="detail-list">
                <div v-for="(item, i) in dataItems(activeDetail)" :key="'n' + i" class="detail-row">
                  <dt class="detail-label">{{ item.label }}</dt>
                  <dd class="detail-value">{{ item.value }}</dd>
                </div>
              </dl>
            </template>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { FileText, RefreshCw, Search, Filter, Undo2 } from 'lucide-vue-next'
import { formatDateTime } from '@/utils/datetime'
import operationLogApi from '@/api/operation_log'
import { SELECT_ALL, LOG_FIELD_LABELS } from '@/utils/constants'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import ListPager from '@/components/common/ListPager.vue'
import VirtualTable from '@/components/common/VirtualTable.vue'
import LogCleanupDialog from '@/components/log/LogCleanupDialog.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'

const formatTime = formatDateTime

// 操作动作筛选（后端归一化键）。
const actionOptions = [
  { value: 'create', label: '新增' },
  { value: 'update', label: '更新' },
  { value: 'delete', label: '删除' },
  { value: 'mount', label: '上架' },
  { value: 'unmount', label: '下架' },
  { value: 'adjust', label: '库存调整' },
]
// 资源类型筛选下拉（与后端 operation_logs.resource 归一化键一致）
const resourceOptions = [
  { value: 'room', label: '机房' },
  { value: 'rack', label: '机柜' },
  { value: 'device', label: '设备' },
  { value: 'interface', label: '接口' },
  { value: 'link', label: '链路' },
  { value: 'account', label: '账号' },
  { value: 'consumable', label: '耗材' },
  { value: 'mount-record', label: '上下架记录' },
]

// 列定义与详情渲染顺序一致；grid 模板由 VirtualTable 统一推导，列宽自适应对齐。
const columns = [
  { key: 'created_at', label: '时间', width: '11rem' },
  { key: 'operator_name', label: '操作人', width: '8rem' },
  { key: 'operation', label: '操作', width: '7.5rem' },
  { key: 'resType', label: '资源类型', width: '7rem' },
  { key: 'target', label: '操作对象', width: 'minmax(160px, 1.3fr)' },
  { key: 'ip', label: 'IP', width: '10rem' },
  { key: 'detail', label: '详情', width: '6rem' },
]

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
// H-03：筛选状态持久化（sessionStorage，刷新/返回后恢复）。
// 恢复发生在 usePersistentFilter 内部的 onMounted(restore)，先于页面 onMounted(load)，
// 故无需 onRestore 回调重复触发加载。
const { filter, clear: clearPersisted } = usePersistentFilter('OperationLog', () => ({
  keyword: '',
  action: SELECT_ALL,
  resource: SELECT_ALL,
  start_date: '',
  end_date: '',
}))
const detailOpen = ref(false)
const activeDetail = ref(null)
const activeRow = ref(null)

function buildParams() {
  const p = { page: page.value, size: pageSize.value }
  if (filter.keyword.trim()) p.keyword = filter.keyword.trim()
  if (filter.action !== SELECT_ALL) p.action = filter.action
  if (filter.resource !== SELECT_ALL) p.resource = filter.resource
  if (filter.start_date) p.start_time = filter.start_date
  if (filter.end_date) p.end_time = filter.end_date
  return p
}

async function load() {
  loading.value = true
  try {
    const data = await operationLogApi.list(buildParams())
    rows.value = (data.items || []).map((l) => ({ ...l }))
    total.value = data.total || 0
    if (rows.value.length === 0 && page.value > 1) {
      page.value = 1
      const again = await operationLogApi.list(buildParams())
      rows.value = (again.items || []).map((l) => ({ ...l }))
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
  // 重置并清掉持久化（H-03），否则下次进入仍会恢复旧筛选。
  clearPersisted()
  reload()
}

function openDetail(row) {
  activeRow.value = row
  activeDetail.value = row.detail
  detailOpen.value = true
}
function hasDetail(d) {
  if (!d) return false
  if (d.diff && d.diff.length) return true
  // 删除类操作：有旧值快照即视为有详情（展示「删除前内容」）。
  if (d.old && typeof d.old === 'object' && Object.keys(d.old).length > 0) return true
  const data = d.data
  if (Array.isArray(data)) return data.length > 0
  if (!data || typeof data !== 'object') return false
  const keys = Object.keys(data).filter((k) => k !== 'id')
  return keys.length > 0
}

// === 人性化映射：把机器字段翻译成人话 ===
// 键为后端 operation_logs.resource 的归一化键（与中间件 _classify 一致）。
const RESOURCE_LABELS = {
  room: '机房',
  rack: '机柜',
  device: '设备',
  account: '账号',
  interface: '接口',
  link: '链路',
  consumable: '耗材',
  'mount-record': '上下架记录',
  meta: '元数据',
  logs: '日志',
  auth: '认证',
}
// HTTP 方法 → 动作（兜底用，优先 row.action）。PUT/PATCH 合并为「更新」。
const METHOD_VERB = { POST: '新增', PUT: '更新', PATCH: '更新', DELETE: '删除' }
const ACTION_VERB = { create: '新增', update: '更新', delete: '删除', mount: '上架', unmount: '下架', adjust: '库存调整' }

const STATUS_LABELS = {
  200: '成功', 201: '已创建', 202: '已接受', 204: '无内容',
  400: '请求错误', 401: '未授权', 403: '禁止访问', 404: '未找到',
  409: '冲突', 422: '校验失败', 429: '请求过多',
  500: '服务器错误', 502: '网关错误', 503: '服务不可用',
}

// 字段中文标签（H-01：已移入 utils/constants.js 的 LOG_FIELD_LABELS，此处复用；
// 未命中的 key 由 prettyKey 退化为可读原文）。

function cap(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}
function prettyKey(k) {
  return k.replace(/_/g, ' ')
}

// 资源类型中文标签：优先后端已归一化的 row.resource，缺省回退路径解析。
function resLabel(key) {
  return RESOURCE_LABELS[key] || (key ? cap(key) : '未知')
}
// 操作动词：优先后端归一化 action（create/update/delete），旧日志缺省回退 method。
function verbOf(row) {
  const a = row.action || METHOD_VERB[row.method]
  return ACTION_VERB[a] || a || row.method || '未知'
}
// 操作对象：优先后端 target 字段；旧日志无 target 时回退前端 inlineSummary。
function targetOf(row) {
  if (row.target) return row.target
  return inlineSummary(row.detail)
}

function statusLabel(code) {
  const c = Number(code)
  if (STATUS_LABELS[c]) return STATUS_LABELS[c]
  if (c >= 200 && c < 300) return '成功'
  if (c >= 300 && c < 400) return '重定向'
  if (c >= 400 && c < 500) return '客户端错误'
  if (c >= 500) return '服务器错误'
  return String(code)
}

// 前端兜底摘要（旧日志无 target 时使用）：从 names/data 拼一行可读文本。
function inlineSummary(detail) {
  if (!detail || !detail.data || typeof detail.data !== 'object' || Array.isArray(detail.data)) return ''
  const data = detail.data
  const names = detail.names || {}
  const parts = []
  // 链路两端：优先接口（模型真实外键），回退设备（历史日志兼容）。
  const srcEp = names.source_interface_id || names.source_device_id
  const dstEp = names.target_interface_id || names.target_device_id
  if (srcEp && dstEp) {
    parts.push(`${srcEp} → ${dstEp}`)
  } else {
    for (const k of ['device_id', 'rack_id', 'room_id', 'consumable_id', 'consumable_type_id', 'category_id', 'owner_device_id']) {
      if (names[k]) parts.push(names[k])
    }
  }
  if (data.name && !parts.includes(data.name)) parts.push(data.name)
  if (data.u_start != null && data.u_end != null) parts.push(`U${data.u_start}-${data.u_end}`)
  if (data.quantity != null) parts.push(`×${data.quantity}`)
  if (data.code && !parts.includes(data.code)) parts.push(data.code)
  return parts.join(' · ')
}

// 弹窗里的「变更字段」列表：标签 + 原值 → 新值。
function diffItems(detail) {
  const diff = detail?.diff || []
  return diff.map((e) => ({
    label: LOG_FIELD_LABELS[e.field] || prettyKey(e.field),
    old: e.old == null ? '—' : String(e.old),
    new: e.new == null ? '—' : String(e.new),
  }))
}

// 弹窗里的「新增/默认请求体」字段列表（含外键解析名称）。
function dataItems(detail) {
  const data = detail?.data
  const names = detail?.names || {}
  if (Array.isArray(data)) return [{ label: '批量数据', value: JSON.stringify(data) }]
  if (!data || typeof data !== 'object') {
    return data == null ? [] : [{ label: '内容', value: String(data) }]
  }
  return Object.entries(data).map(([k, v]) => {
    const label = LOG_FIELD_LABELS[k] || prettyKey(k)
    let value
    if (names[k]) value = `${names[k]}（${v}）`
    else if (v == null) value = '—'
    else if (typeof v === 'object') value = JSON.stringify(v)
    else value = String(v)
    return { label, value }
  })
}

// 弹窗里的「删除前快照」字段列表：从 detail.old + detail.old_names 拼出可读内容。
function isDeleteAction(row) {
  if (!row) return false
  return row.action === 'delete' || row.method === 'DELETE'
}

function oldItems(detail) {
  const old = detail?.old
  if (!old || typeof old !== 'object') return []
  const oldNames = detail?.old_names || {}
  // 过滤无意义字段（纯 ID、密码哈希等）。
  const skip = new Set(['password_hash', 'salt'])
  return Object.entries(old)
    .filter(([k, v]) => v != null && v !== '' && !skip.has(k))
    .map(([k, v]) => {
      const label = LOG_FIELD_LABELS[k] || prettyKey(k)
      let value
      if (oldNames[k]) value = `${oldNames[k]}`
      else if (typeof v === 'object') value = JSON.stringify(v)
      else value = String(v)
      return { label, value }
    })
}

// 动作药丸（语义化配色）：create=绿 / update=琥珀 / delete=红 / mount=蓝 / unmount=紫 / adjust=青。
const ACTION_BADGE = {
  create: 'badge--create',
  update: 'badge--update',
  delete: 'badge--delete',
  mount: 'badge--mount',
  unmount: 'badge--unmount',
  adjust: 'badge--adjust',
}
function actionBadgeClass(a) {
  return ACTION_BADGE[a] || 'badge--default'
}
function statusDotClass(code) {
  const c = Number(code)
  if (c >= 200 && c < 300) return 'dot--success'
  if (c >= 300 && c < 400) return 'dot--info'
  if (c >= 400 && c < 500) return 'dot--warn'
  if (c >= 500) return 'dot--danger'
  return 'dot--default'
}

function onEsc(e) {
  if (e.key === 'Escape') detailOpen.value = false
}
onMounted(load)
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
</script>

<style scoped>
/* P0 风格统一：page-head/page-title/page-sub/toolbar 移交给全局 @utility（index.css）。
   toolbar 内部的 flex 间距特化保留（日志筛选控件多，需更大横向间距）。 */
.toolbar :deep(.flex) { gap: 16px 20px; }

/* 操作动词药丸：新增 / 更新 / 删除，按动作配色 */
.op-verb {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  line-height: 1.4;
}

/* 操作前列前的小圆点：成功绿 / 失败红，hover 看 HTTP 码与含义 */
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  vertical-align: middle;
  flex: none;
}

/* 资源类型药丸 */
.res-type-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  background: hsl(var(--muted) / 0.6);
  color: hsl(var(--foreground));
  border: 1px solid hsl(var(--border) / 0.6);
}

/* 操作对象：可读名称 chip，超长省略 */
.target-chip {
  display: inline-block;
  max-width: 100%;
  padding: 2px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  background: hsl(var(--primary) / 0.08);
  color: hsl(var(--primary));
  border: 1px solid hsl(var(--primary) / 0.18);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}

/* 详情按钮 */
.detail-btn {
  padding: 4px 14px;
  /* P2：圆角归一 9px → 8px（rounded-md） */
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--muted) / 0.5);
  color: hsl(var(--foreground));
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.detail-btn:hover:not(:disabled) {
  background: hsl(var(--primary) / 0.12);
  border-color: hsl(var(--primary) / 0.5);
  color: hsl(var(--primary));
}
.detail-btn.is-empty {
  opacity: 0.5;
  border-color: hsl(var(--border));
  background: hsl(var(--muted) / 0.3);
  color: hsl(var(--muted-foreground));
  cursor: default;
}

/* 详情弹窗 */
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
}
.modal-panel {
  width: min(580px, 92vw);
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border));
  /* P2：圆角归一 20px → rounded-2xl(16px)，与 Dialog 弹窗体系一致 */
  border-radius: 16px;
  /* P2：硬编码阴影 → shadow-card 令牌 */
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid hsl(var(--border) / 0.6);
}
.modal-title {
  /* P2：15px → 16px 规范档（text-base），与全局弹窗标题一致 */
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.modal-close {
  border: none;
  background: transparent;
  font-size: 18px;
  line-height: 1;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
}
.modal-close:hover {
  background: hsl(var(--muted) / 0.6);
  color: hsl(var(--foreground));
}
.modal-body {
  overflow-y: auto;
  padding: 16px 20px 20px;
}

/* 元信息条：操作上下文一览 */
.meta-card {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
  padding: 14px 16px;
  margin-bottom: 16px;
  background: hsl(var(--muted) / 0.4);
  border: 1px solid hsl(var(--border) / 0.6);
  /* P2：圆角归一 14px → 12px（rounded-xl） */
  border-radius: 12px;
}
.meta-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.meta-item--wide {
  grid-column: 1 / -1;
}
.meta-k {
  flex: none;
  width: 4.5rem;
  color: hsl(var(--muted-foreground));
  font-size: 12px;
}
.meta-v {
  min-width: 0;
  font-size: 13px;
  font-weight: 500;
  word-break: break-all;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.detail-list {
  margin: 0;
}
.detail-row {
  display: grid;
  grid-template-columns: 8rem 1fr;
  gap: 8px 12px;
  padding: 8px 0;
  border-bottom: 1px dashed hsl(var(--border) / 0.5);
}
.detail-label {
  color: hsl(var(--muted-foreground));
  font-size: 13px;
}
.detail-value {
  margin: 0;
  font-size: 13px;
  word-break: break-all;
}

/* 变更对比块 */
.diff-block {
  margin: 0;
}
.diff-head {
  font-size: 12px;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}
.diff-row .detail-value {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.diff-old {
  background: hsl(var(--muted) / 0.6);
  color: hsl(var(--muted-foreground));
  padding: 1px 8px;
  border-radius: 6px;
  text-decoration: line-through;
  text-decoration-color: hsl(var(--muted-foreground) / 0.5);
}
.diff-arrow {
  color: hsl(var(--primary));
  font-weight: 700;
}
.diff-new {
  background: hsl(var(--primary) / 0.12);
  color: hsl(var(--primary));
  padding: 1px 8px;
  border-radius: 6px;
  font-weight: 600;
}

/* 动作 / 状态配色（CSS 变量令牌，深浅色通用） */
.badge--create {
  background: hsl(142 71% 45% / 0.14);
  color: hsl(142 71% 38%);
}
.badge--update {
  background: hsl(38 92% 50% / 0.16);
  color: hsl(32 90% 42%);
}
.badge--delete {
  background: hsl(0 84% 60% / 0.14);
  color: hsl(0 84% 52%);
}
.badge--mount {
  background: hsl(210 80% 52% / 0.14);
  color: hsl(210 80% 44%);
}
.badge--unmount {
  background: hsl(270 70% 55% / 0.14);
  color: hsl(270 70% 48%);
}
.badge--adjust {
  background: hsl(180 70% 42% / 0.14);
  color: hsl(180 70% 36%);
}
.badge--default {
  background: hsl(var(--muted));
  color: hsl(var(--muted-foreground));
}
.dot--success { background: hsl(142 71% 45%); }
.dot--info { background: hsl(217 91% 60%); }
.dot--warn { background: hsl(38 92% 50%); }
.dot--danger { background: hsl(0 84% 60%); }
.dot--default { background: hsl(var(--muted-foreground)); }
</style>
