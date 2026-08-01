<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title flex items-center gap-2">
          <LogIn class="h-6 w-6 text-primary" /> 登录日志
        </h1>
        <p class="page-sub">记录账号的登录与注销行为：用户名、动作、成败状态与来源 IP</p>
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
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="用户名" class="w-56 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <Label>动作</Label>
          <Select v-model="filter.action" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="a in actionOptions" :key="a.value" :value="a.value">{{ a.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>状态</Label>
          <Select v-model="filter.status" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="s in statusOptions" :key="s.value" :value="s.value">{{ s.label }}</SelectItem>
            </SelectContent>
          </Select>
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

    <!-- 登录日志：整页布局、跟随浏览器滚动，无内部独立滚动条 -->
    <VirtualTable
      :columns="columns"
      :rows="rows"
      :virtual="false"
      key-field="id"
      :loading="loading"
      empty-text="暂无登录日志"
    >
      <template #row="{ row }">
        <div class="vt-cell px-3 py-3 tabular-nums text-muted-foreground whitespace-nowrap">{{ formatTime(row.created_at) }}</div>
        <div class="vt-cell px-3 py-3 whitespace-nowrap font-medium">{{ row.username || '—' }}</div>
        <div class="vt-cell px-3 py-3">
          <span class="act-badge" :class="row.action === 'login' ? 'act-badge--in' : 'act-badge--out'">{{ actionLabel(row.action) }}</span>
        </div>
        <div class="vt-cell px-3 py-3">
          <span class="status-pill" :class="row.status === 'success' ? 'status-pill--ok' : 'status-pill--fail'">{{ statusLabel(row.status) }}</span>
        </div>
        <div class="vt-cell px-3 py-3 text-sm text-muted-foreground whitespace-nowrap">{{ row.ip || '—' }}</div>
      </template>
    </VirtualTable>

    <ListPager v-if="total > 0" :total="total" :page="page" :page-size="pageSize" @change="goPage" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { LogIn, RefreshCw, Search, Filter, Undo2 } from 'lucide-vue-next'
import { formatDateTime } from '@/utils/datetime'
import loginLogApi from '@/api/login_log'
import { SELECT_ALL } from '@/utils/constants'
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

const actionOptions = [
  { value: 'login', label: '登录' },
  { value: 'logout', label: '注销' },
]
const statusOptions = [
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
]

// 列定义与详情渲染顺序一致；grid 模板由 VirtualTable 统一推导，列宽自适应对齐。
const columns = [
  { key: 'created_at', label: '时间', width: '11rem' },
  { key: 'username', label: '用户名', width: '12rem' },
  { key: 'action', label: '动作', width: '6rem' },
  { key: 'status', label: '状态', width: '6rem' },
  { key: 'ip', label: 'IP', width: '12rem' },
]

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
// H-03：筛选状态持久化（sessionStorage，刷新/返回后恢复）。
const { filter, clear: clearPersisted } = usePersistentFilter('LoginLog', () => ({
  keyword: '',
  action: SELECT_ALL,
  status: SELECT_ALL,
  start_date: '',
  end_date: '',
}))

function actionLabel(a) {
  return a === 'login' ? '登录' : a === 'logout' ? '注销' : a || '—'
}
function statusLabel(s) {
  return s === 'success' ? '成功' : s === 'failed' ? '失败' : s || '—'
}

function buildParams() {
  const p = { page: page.value, size: pageSize.value }
  if (filter.keyword.trim()) p.keyword = filter.keyword.trim()
  if (filter.action !== SELECT_ALL) p.action = filter.action
  if (filter.status !== SELECT_ALL) p.status = filter.status
  if (filter.start_date) p.start_time = filter.start_date
  if (filter.end_date) p.end_time = filter.end_date
  return p
}

async function load() {
  loading.value = true
  try {
    const data = await loginLogApi.list(buildParams())
    rows.value = (data.items || []).map((l) => ({ ...l }))
    total.value = data.total || 0
    // 当前页清空（如筛选后），回退到首页再拉一次，避免空白。
    if (rows.value.length === 0 && page.value > 1) {
      page.value = 1
      const again = await loginLogApi.list(buildParams())
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

onMounted(load)
</script>

<style scoped>
/* P0 风格统一：page-head/page-title/page-sub/toolbar 移交给全局 @utility（index.css）。 */

.act-badge,
.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 10px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
}
.act-badge--in {
  background: hsl(217 91% 60% / 0.14);
  color: hsl(217 91% 50%);
}
.act-badge--out {
  background: hsl(262 83% 58% / 0.14);
  color: hsl(262 83% 52%);
}
.status-pill--ok {
  background: hsl(142 71% 45% / 0.14);
  color: hsl(142 71% 38%);
}
.status-pill--fail {
  background: hsl(0 84% 60% / 0.14);
  color: hsl(0 84% 52%);
}
</style>
