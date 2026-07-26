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
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-20">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <Card v-else>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="w-44">时间</TableHead>
            <TableHead class="w-28">操作人</TableHead>
            <TableHead class="w-24">模块</TableHead>
            <TableHead class="w-24">操作</TableHead>
            <TableHead>对象 / 详情</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="log in logs" :key="log.id">
            <TableCell class="text-muted-foreground tabular-nums">{{ formatTime(log.created_at) }}</TableCell>
            <TableCell>
              <span class="font-medium">{{ log.operator_name || '—' }}</span>
              <span v-if="log.ip" class="block text-xs text-muted-foreground">{{ log.ip }}</span>
            </TableCell>
            <TableCell>
              <Badge variant="secondary">{{ moduleLabel(log.module) }}</Badge>
            </TableCell>
            <TableCell>
              <Badge :variant="actionBadge(log.action)">{{ actionLabel(log.action) }}</Badge>
            </TableCell>
            <TableCell>
              <div class="flex flex-col">
                <span v-if="log.object_name" class="font-medium">{{ log.object_type }}：{{ log.object_name }}</span>
                <span class="text-sm text-muted-foreground">{{ log.detail || '—' }}</span>
              </div>
            </TableCell>
          </TableRow>
          <TableRow v-if="!logs.length">
            <TableCell colspan="5" class="text-center text-muted-foreground">暂无审计记录</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </Card>

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
import {
  ScrollText,
  RefreshCw,
  Search,
  Filter,
  Undo2,
} from 'lucide-vue-next'
import { formatDateTime } from '@/utils/datetime'
import auditApi from '@/api/audit'
import { SELECT_ALL } from '@/utils/constants'
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
import Badge from '@/components/ui/badge.vue'
import Spinner from '@/components/ui/spinner.vue'
import ListPager from '@/components/common/ListPager.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'

const formatTime = formatDateTime

const MODULE_LABELS = {
  room: '机房',
  rack: '机柜',
  device: '设备',
  account: '账号',
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
// 操作 → Badge 变体（语义化配色）。
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

const moduleOptions = Object.keys(MODULE_LABELS)
const actionOptions = Object.keys(ACTION_LABELS)

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filter = reactive({ keyword: '', module: SELECT_ALL, action: SELECT_ALL, operator: '' })

function buildParams() {
  const p = { page: page.value, size: pageSize.value }
  if (filter.keyword.trim()) p.keyword = filter.keyword.trim()
  if (filter.module !== SELECT_ALL) p.module = filter.module
  if (filter.action !== SELECT_ALL) p.action = filter.action
  if (filter.operator.trim()) p.operator = filter.operator.trim()
  return p
}

async function load() {
  loading.value = true
  try {
    const data = await auditApi.list(buildParams())
    logs.value = data.items || []
    total.value = data.total || 0
    if (logs.value.length === 0 && page.value > 1) {
      page.value = 1
      const again = await auditApi.list(buildParams())
      logs.value = again.items || []
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
  reload()
}

onMounted(load)
</script>
