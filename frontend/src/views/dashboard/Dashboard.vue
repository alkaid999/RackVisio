<template>
  <div>
    <!-- 页面标题区 -->
    <div class="page-head">
      <div>
        <h1 class="page-title flex items-center gap-2">
          <LayoutDashboard class="h-6 w-6 text-primary" /> 平台总览
        </h1>
        <p class="page-sub">实时反映机房、机柜、设备与资源的最新状态</p>
      </div>
      <Button :loading="loading" @click="load">
        <RefreshCw class="h-4 w-4" /> 刷新数据
      </Button>
    </div>

    <!-- KPI 概览卡：shadcn Card + 入场错峰动画 + hover 微抬升 -->
    <div class="grid grid-cols-2 gap-4 mb-6 sm:grid-cols-3 lg:grid-cols-4">
      <Card
        v-for="(k, i) in kpis"
        :key="k.label"
        hover
        class="animate-slide-in-up"
        :style="{ animationDelay: i * 55 + 'ms' }"
      >
        <div class="flex items-center justify-between">
          <span class="text-sm text-muted-foreground">{{ k.label }}</span>
          <span
            class="flex h-9 w-9 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-110"
            :style="{ background: k.color + '1a', color: k.color }"
          >
            <component :is="k.icon" class="h-4 w-4" />
          </span>
        </div>
        <div class="mt-3 text-3xl font-bold tabular-nums leading-none" :style="{ color: k.color }">
          {{ k.value }}<span v-if="k.suffix" class="ml-1 text-base font-medium text-muted-foreground">{{ k.suffix }}</span>
        </div>
        <div v-if="k.hint" class="mt-1.5 text-xs text-muted-foreground">{{ k.hint }}</div>
      </Card>
    </div>

    <!-- 分析区：Tabs 组织信息层次 -->
    <Tabs default-value="room" class="w-full">
      <TabsList class="mb-5 flex-wrap">
        <TabsTrigger value="room">
          <Building2 class="mr-1.5 h-4 w-4" />机房容量
        </TabsTrigger>
        <TabsTrigger value="device">
          <Cpu class="mr-1.5 h-4 w-4" />设备分析
        </TabsTrigger>
        <TabsTrigger value="resource">
          <Boxes class="mr-1.5 h-4 w-4" />资源台账
        </TabsTrigger>
      </TabsList>

      <!-- 机房容量 -->
      <TabsContent value="room">
        <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card title="各机房机柜使用率" description="矩形树图：面积=总 U，颜色=使用率">
            <div class="h-72">
              <BaseChart v-if="overview" :option="capacityOption" />
              <div v-else class="flex h-full items-center justify-center text-sm text-muted-foreground">加载中…</div>
            </div>
          </Card>

          <Card title="机房机柜使用率明细" description="各机房机柜规模与空间占用">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>机房</TableHead>
                  <TableHead class="text-right">机柜数</TableHead>
                  <TableHead class="text-right">总 U</TableHead>
                  <TableHead class="text-right">已用 U</TableHead>
                  <TableHead class="text-right">使用率</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="r in rooms" :key="r.room_id">
                  <TableCell class="font-medium">{{ r.room_name }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ r.rack_count }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ r.total_u }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ r.used_u }}</TableCell>
                  <TableCell class="text-right">
                    <Badge :variant="utilBadge(r.utilization)">{{ r.utilization }}%</Badge>
                  </TableCell>
                </TableRow>
                <TableRow v-if="!rooms.length">
                  <TableCell colspan="5" class="text-center text-muted-foreground">暂无机房数据</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Card>
        </div>
      </TabsContent>

      <!-- 设备分析 -->
      <TabsContent value="device">
        <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card title="设备状态分布" description="资产生命周期状态占比">
            <div class="h-72">
              <BaseChart v-if="overview" :option="statusOption" />
              <div v-else class="flex h-full items-center justify-center text-sm text-muted-foreground">加载中…</div>
            </div>
          </Card>

          <Card title="设备类型分布" description="按设备类型统计数量">
            <div class="h-72">
              <BaseChart v-if="overview" :option="typeOption" />
              <div v-else class="flex h-full items-center justify-center text-sm text-muted-foreground">加载中…</div>
            </div>
          </Card>
        </div>

        <div class="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card title="设备状态明细" description="各状态设备数量">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>状态</TableHead>
                  <TableHead class="text-right">数量</TableHead>
                  <TableHead class="w-24 text-right">占比</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="s in statusDetail" :key="s.status">
                  <TableCell>
                    <span class="flex items-center gap-2">
                      <span class="h-2.5 w-2.5 rounded-full" :style="{ background: meta.deviceStatusColor(s.status) }" />
                      {{ s.label }}
                    </span>
                  </TableCell>
                  <TableCell class="text-right font-semibold tabular-nums">{{ s.count }}</TableCell>
                  <TableCell class="text-right">
                    <Badge :variant="statusBadge(s.status)">{{ statusPercent(s.count) }}%</Badge>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Card>

          <Card title="设备类型明细" description="各类型设备数量">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>类型</TableHead>
                  <TableHead class="text-right">数量</TableHead>
                  <TableHead class="w-24 text-right">占比</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="t in typeDetail" :key="t.type">
                  <TableCell>
                    <span class="flex items-center gap-2">
                      <span class="h-2.5 w-2.5 rounded-full" :style="{ background: meta.deviceTypeColor(t.type) }" />
                      {{ t.label }}
                    </span>
                  </TableCell>
                  <TableCell class="text-right font-semibold tabular-nums">{{ t.count }}</TableCell>
                  <TableCell class="text-right">
                    <Badge variant="secondary">{{ typePercent(t.count) }}%</Badge>
                  </TableCell>
                </TableRow>
                <TableRow v-if="!typeDetail.length">
                  <TableCell colspan="3" class="text-center text-muted-foreground">暂无设备数据</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Card>
        </div>
      </TabsContent>

      <!-- 资源台账 -->
      <TabsContent value="resource">
        <div class="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          <Card title="链路与账号" description="连接与系统账号规模">
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <span class="flex items-center gap-2 text-sm text-muted-foreground"><Link2 class="h-4 w-4 text-[#06b6d4]" />链路总数</span>
                <span class="text-2xl font-bold tabular-nums">{{ overview?.link_count ?? 0 }}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="flex items-center gap-2 text-sm text-muted-foreground"><Users class="h-4 w-4 text-[#f59e0b]" />账号数</span>
                <span class="text-2xl font-bold tabular-nums">{{ overview?.account_count ?? 0 }}</span>
              </div>
            </div>
          </Card>

          <Card title="耗材库存" description="耗材类型、条目与结存总量">
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <span class="flex items-center gap-2 text-sm text-muted-foreground"><Layers class="h-4 w-4 text-[#8b5cf6]" />耗材类型</span>
                <span class="text-2xl font-bold tabular-nums">{{ overview?.consumable_type_count ?? 0 }}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="flex items-center gap-2 text-sm text-muted-foreground"><Package class="h-4 w-4 text-[#eb4895]" />耗材条目</span>
                <span class="text-2xl font-bold tabular-nums">{{ overview?.consumable_item_count ?? 0 }}</span>
              </div>
              <div class="flex items-center justify-between border-t border-border pt-3">
                <span class="text-sm text-muted-foreground">库存总量</span>
                <span class="text-2xl font-bold tabular-nums text-primary">{{ overview?.consumable_total_quantity ?? 0 }}</span>
              </div>
            </div>
          </Card>

          <Card title="快捷入口" description="常用功能跳转">
            <div class="grid grid-cols-1 gap-3">
              <RouterLink
                v-for="a in quickActions"
                :key="a.to"
                :to="a.to"
                class="flex items-center gap-2 rounded-lg border border-border p-3 text-sm font-medium transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-accent"
              >
                <component :is="a.icon" class="h-4 w-4 text-primary" />
                {{ a.label }}
                <ArrowRight class="ml-auto h-4 w-4 text-muted-foreground" />
              </RouterLink>
            </div>
          </Card>
        </div>
      </TabsContent>
    </Tabs>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import {
  LayoutDashboard,
  RefreshCw,
  Building2,
  Server,
  Cpu,
  CircleCheck,
  Gauge,
  Link2,
  Users,
  Package,
  Boxes,
  ArrowRight,
  Layers,
} from 'lucide-vue-next'
import statsApi from '@/api/stats'
import { useTheme } from '@/composables/useTheme'
import { chartTheme } from '@/utils/echarts-theme'
import { useMetaStore } from '@/stores/meta'
import Button from '@/components/ui/button.vue'
import BaseChart from '@/components/ui/chart.vue'
import Card from '@/components/ui/card.vue'
import Badge from '@/components/ui/badge.vue'
import Tabs from '@/components/ui/tabs.vue'
import TabsList from '@/components/ui/tabs-list.vue'
import TabsTrigger from '@/components/ui/tabs-trigger.vue'
import TabsContent from '@/components/ui/tabs-content.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'

const { isDark } = useTheme()
const meta = useMetaStore()
const overview = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    overview.value = await statsApi.overview()
  } finally {
    loading.value = false
  }
}

// ---- KPI 概览卡（8 张）----
const kpis = computed(() => {
  const o = overview.value || {}
  const statusMap = {}
  for (const s of o.device_status || []) statusMap[s.status] = s.count
  const util = o.overall_utilization ?? 0
  return [
    { label: '机房数量', value: o.room_count ?? 0, icon: Building2, color: '#3b82f6' },
    { label: '机柜数量', value: o.rack_count ?? 0, icon: Server, color: '#13c2c2' },
    { label: '设备总数', value: o.device_count ?? 0, icon: Cpu, color: '#8b5cf6' },
    { label: '已上架设备', value: statusMap['已上架'] ?? 0, icon: CircleCheck, color: '#22c55e' },
    {
      label: '整体机柜使用率',
      value: util,
      suffix: '%',
      icon: Gauge,
      color: meta.usageColor(util),
      hint: `已用 ${o.used_u ?? 0} / 共 ${o.total_u ?? 0} U`,
    },
    { label: '链路总数', value: o.link_count ?? 0, icon: Link2, color: '#06b6d4' },
    { label: '账号数', value: o.account_count ?? 0, icon: Users, color: '#f59e0b' },
    { label: '耗材条目', value: o.consumable_item_count ?? 0, icon: Package, color: '#eb4895' },
  ]
})

// ---- 派生数据 ----
const rooms = computed(() => overview.value?.rack_capacity_by_room || [])
const statusDetail = computed(() => overview.value?.device_status || [])
const typeDetail = computed(() => overview.value?.device_type_distribution || [])

// 机柜使用率阈值配色（阈值来自后端 /meta，消除魔法数字）。
function utilBadge(v) {
  if (v >= meta.usageCrit) return 'destructive'
  if (v >= meta.usageWarn) return 'warning'
  return 'success'
}
// 设备状态 Badge 变体。
const STATUS_BADGE = {
  已上架: 'success',
  在库: 'secondary',
  待报废: 'destructive',
  借出: 'default',
  已下架: 'warning',
}
function statusBadge(s) {
  return STATUS_BADGE[s] || 'secondary'
}
function statusPercent(c) {
  const total = statusDetail.value.reduce((a, b) => a + b.count, 0)
  return total ? Math.round((c / total) * 100) : 0
}
function typePercent(c) {
  const total = typeDetail.value.reduce((a, b) => a + b.count, 0)
  return total ? Math.round((c / total) * 100) : 0
}
// 将 hex 颜色转为带透明度的 rgba，用于图表渐变（无需引入 echarts.graphic）。
function hexToRgba(hex, a) {
  const h = String(hex).replace('#', '')
  const full = h.length === 3 ? h.split('').map((x) => x + x).join('') : h
  const n = parseInt(full, 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}
// 使用率阈值配色（阈值/颜色来自后端 /meta，消除魔法数字与内联色，审查报告#352）。
function utilColor(v) {
  return meta.usageColor(v)
}

// ---- 图表配置（随主题切换配色）----
const statusOption = computed(() => {
  if (!overview.value) return {}
  const t = chartTheme(isDark.value)
  const dist = overview.value.device_status || []
  const data = dist
    .filter((d) => d.count > 0)
    .map((d) => ({
      name: d.label,
      value: d.count,
      itemStyle: {
        color: meta.deviceStatusColor(d.status),
        borderColor: isDark.value ? '#181b24' : '#fff',
        borderWidth: 2,
        borderRadius: 5,
      },
    }))
  const total = dist.reduce((a, b) => a + b.count, 0)
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c} 台（{d}%）' },
    legend: { bottom: 0, icon: 'circle', itemWidth: 10, itemHeight: 10, textStyle: { color: t.text } },
    // 中心叠加大字「设备总数」，提升信息密度（南丁格尔玫瑰中心留白）。
    title: {
      text: String(total),
      subtext: '设备总数',
      left: 'center',
      top: '40%',
      textStyle: { color: t.text, fontSize: 26, fontWeight: 700 },
      subtextStyle: { color: t.axis, fontSize: 12 },
      itemGap: 4,
    },
    series: [
      {
        type: 'pie',
        roseType: 'radius',
        radius: ['30%', '72%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: isDark.value ? '#181b24' : '#fff', borderWidth: 2, borderRadius: 5 },
        label: { show: false },
        labelLine: { show: false },
        data,
      },
    ],
  }
})

const capacityOption = computed(() => {
  if (!overview.value) return {}
  const list = [...(overview.value.rack_capacity_by_room || [])]
  // 矩形树图（treemap，非环形 / 非柱状）：
  //  - 面积 = 总 U（体量，越大块越大）
  //  - 颜色 = 使用率（阈值 绿/黄/红，竖向渐变 + 留白描边）
  const data = list.map((r) => {
    const c = utilColor(r.utilization)
    return {
      name: r.room_name,
      value: Math.max(r.total_u, 1), // 面积维度；保底 1 防止零面积不渲染
      _util: r.utilization,
      _used: r.used_u,
      _racks: r.rack_count,
      itemStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: hexToRgba(c, 0.95) },
          { offset: 1, color: hexToRgba(c, 0.62) },
        ] },
        borderColor: isDark.value ? 'rgba(20,23,32,0.9)' : 'rgba(255,255,255,0.92)',
        borderWidth: 3,
        gapWidth: 3,
      },
      label: {
        show: true,
        formatter: (p) => `${p.name}\n${p.data._util}% · ${p.value}U`,
        color: '#fff',
        fontSize: 13,
        fontWeight: 700,
        lineHeight: 18,
      },
    }
  })
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const d = p.data
        return `<b>${d.name}</b><br/>总 U：${d.value}<br/>已用 U：${d._used}<br/>机柜数：${d._racks}<br/>使用率：<b>${d._util}%</b>`
      },
    },
    series: [
      {
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        width: '100%',
        height: '100%',
        top: 4,
        left: 4,
        right: 4,
        bottom: 4,
        itemStyle: { borderWidth: 0, gapWidth: 3 },
        label: { show: true },
        emphasis: { itemStyle: { borderColor: '#fff', borderWidth: 3 } },
        data,
      },
    ],
  }
})

const typeOption = computed(() => {
  if (!overview.value) return {}
  const t = chartTheme(isDark.value)
  const list = [...(overview.value.device_type_distribution || [])].sort((a, b) => b.count - a.count)
  const names = list.map((d) => d.label)
  const max = Math.max(...list.map((d) => d.count), 1)
  const data = list.map((d) => {
    const c = meta.deviceTypeColor(d.type)
    return {
      value: d.count,
      itemStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [
          { offset: 0, color: hexToRgba(c, 0.45) },
          { offset: 1, color: c },
        ] },
        borderRadius: [0, 6, 6, 0],
      },
    }
  })
  return {
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>数量：${p[0].value} 台` },
    grid: { left: 80, right: 48, top: 12, bottom: 12 },
    xAxis: {
      type: 'value',
      max,
      axisLabel: { color: t.axis },
      splitLine: { lineStyle: { color: t.split } },
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: t.axis },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data,
        barWidth: '56%',
        showBackground: true,
        backgroundStyle: { color: isDark.value ? 'rgba(148,163,184,0.12)' : 'rgba(15,23,42,0.05)', borderRadius: 6 },
        label: { show: true, position: 'right', formatter: '{c}', color: t.text, fontSize: 12, fontWeight: 600 },
      },
    ],
  }
})

// 快捷入口（保留原功能）。
const quickActions = [
  { to: '/rooms', label: '机房列表', icon: Building2 },
  { to: '/devices', label: '设备列表', icon: Cpu },
  { to: '/consumables', label: '耗材管理', icon: Package },
]

onMounted(load)
</script>
