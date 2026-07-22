<template>
  <div class="iface-panel" @mouseleave="hideTip">
    <div class="iface-chassis">
      <!-- 四角螺丝（CSS 伪元素 + 两个定位元素） -->
      <span class="screw screw--tl" />
      <span class="screw screw--br" />

      <!-- 标题 + 图例 -->
      <header class="panel-head">
        <div class="panel-title">
          <Network class="h-4 w-4 text-primary" />
          <span>接口面板</span>
          <span class="panel-count">{{ interfaces.length }}</span>
        </div>
        <div class="legend">
          <span class="legend-item"><i class="led led--up" />已连线</span>
          <span class="legend-item"><i class="led led--down" />未连线</span>
          <span class="legend-sep" />
          <span class="legend-item"><Cable class="lg-ic" />RJ-45</span>
          <span class="legend-item"><Settings2 class="lg-ic" />Console</span>
          <span class="legend-item"><Zap class="lg-ic" />SFP/QSFP</span>
        </div>
      </header>

      <!-- 按接口名称前缀分组：每组一个可点击折叠/展开的标题行（与列表面板一致） -->
      <div v-if="interfaces.length" class="iface-groups">
        <section v-for="g in grouped" :key="g.prefix" class="iface-group">
          <header
            class="iface-group__head"
            role="button"
            tabindex="0"
            @click="toggle(g.prefix)"
            @keydown.enter="toggle(g.prefix)"
          >
            <ChevronRight class="iface-group__chevron" :class="{ 'is-collapsed': isCollapsed(g.prefix) }" />
            <span class="iface-group__title">{{ g.prefix }}</span>
            <span class="iface-group__count">{{ g.rows.length }}</span>
          </header>
          <div v-show="!isCollapsed(g.prefix)" class="iface-grid" :class="{ 'iface-grid--dense': dense }">
            <button
              v-for="itf in g.rows"
              :key="itf.id"
              type="button"
              class="iface-cell"
              :class="itf.status === 'up' ? 'iface-cell--up' : 'iface-cell--down'"
              @mouseenter="showTip(itf, $event)"
              @mousemove="moveTip($event)"
              @click="onClick(itf)"
            >
              <i class="cell-led" :class="itf.status === 'up' ? 'led--up' : 'led--down'" />
              <component :is="iconComp(itf)" class="cell-icon" :style="{ color: iconColor(itf) }" />
              <span class="cell-no">#{{ itf.interface_no || '—' }}</span>
              <span class="cell-name" :title="itf.name">{{ itf.name }}</span>
              <span v-if="itf.ip_address" class="cell-ip" :title="itf.ip_address">{{ itf.ip_address }}</span>
              <span v-if="itf.role === 'mgmt'" class="cell-role">管理</span>
            </button>
          </div>
        </section>
      </div>
      <EmptyState v-else title="暂无接口" subtitle="点击右上角「添加接口」录入本设备端口" />
    </div>

    <!-- 悬浮明细 -->
    <div v-if="tip" class="iface-tip" :style="tipStyle">
      <div class="tip-name">{{ tip.name }}</div>
      <div class="tip-row"><span>槽位</span><b>#{{ tip.interface_no || '—' }}</b></div>
      <div class="tip-row"><span>类型</span><b>{{ kindHint(tip) }}</b></div>
      <div class="tip-row"><span>角色</span><b>{{ INTERFACE_ROLE_LABELS[tip.role] || tip.role }}</b></div>
      <div class="tip-row"><span>速率</span><b>{{ tip.speed }}</b></div>
      <div v-if="tip.ip_address" class="tip-row"><span>IP 地址</span><b class="font-mono text-[11px]">{{ tip.ip_address }}</b></div>
      <div class="tip-row">
        <span>状态</span>
        <b :style="{ color: tip.status === 'up' ? '#67C23A' : '#909399' }">
          <i class="tip-dot" :style="{ background: tip.status === 'up' ? '#67C23A' : '#909399' }" />
          {{ tip.status === 'up' ? '已连线' : '未连线' }}
        </b>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Cable, Zap, Settings2, Network, ChevronRight } from 'lucide-vue-next'
import EmptyState from '@/components/ui/empty-state.vue'
import { INTERFACE_ROLE_LABELS, INTERFACE_TYPE_LABELS } from '@/utils/constants'

const props = defineProps({
  // 接口数组（仅实际存在的接口）：[{ id, interface_no, name, interface_type, role, speed, status }]
  interfaces: { type: Array, default: () => [] },
})
const emit = defineEmits(['select'])

// 接口多时（交换机）自动切换到紧凑网格。
const dense = computed(() => props.interfaces.length >= 12)

// 接口按「名称前缀」（连续英文字母，如 Gig / Mgmt / Ten）自动分组；
// 前缀提取失败（如名称以数字开头）归入「其他」。各组按前缀字母序排列，组内按槽位 + 名称排序。
const PREFIX_RE = /^([A-Za-z]+)/
const collapsed = ref(new Set())
function isCollapsed(prefix) {
  return collapsed.value.has(prefix)
}
function toggle(prefix) {
  const next = new Set(collapsed.value)
  if (next.has(prefix)) next.delete(prefix)
  else next.add(prefix)
  collapsed.value = next
}
const grouped = computed(() => {
  const map = {}
  for (const itf of props.interfaces || []) {
    const m = (itf.name || '').match(PREFIX_RE)
    const prefix = m ? m[1] : '其他'
    ;(map[prefix] = map[prefix] || []).push(itf)
  }
  return Object.keys(map)
    .sort((a, b) => a.localeCompare(b))
    .map((prefix) => ({
      prefix,
      rows: map[prefix].sort(
        (a, b) => (a.interface_no || 0) - (b.interface_no || 0) || a.name.localeCompare(b.name)
      ),
    }))
})

function typeOf(itf) {
  // 管理口优先按角色归类；其余按物理类型。
  if (itf.role === 'mgmt' || itf.interface_type === 'console') return 'console'
  return itf.interface_type || 'other'
}
function iconComp(itf) {
  const t = typeOf(itf)
  if (t === 'console') return Settings2
  if (t === 'sfp' || t === 'qsfp') return Zap
  return Cable
}
function iconColor(itf) {
  const t = typeOf(itf)
  if (t === 'console') return '#8b5cf6'
  if (t === 'sfp') return '#f59e0b'
  if (t === 'qsfp') return '#10b981'
  return '#3b82f6'
}
function kindHint(itf) {
  if (itf.role === 'mgmt') return '管理口'
  return INTERFACE_TYPE_LABELS[itf.interface_type] || itf.interface_type
}

// —— 悬浮明细 ——
const tip = ref(null)
const tipPos = ref({ x: 0, y: 0 })
const tipStyle = computed(() => ({ left: `${tipPos.value.x + 14}px`, top: `${tipPos.value.y + 14}px` }))
function showTip(itf, e) {
  tip.value = itf
  tipPos.value = { x: e.clientX, y: e.clientY }
}
function moveTip(e) {
  if (tip.value) tipPos.value = { x: e.clientX, y: e.clientY }
}
function hideTip() {
  tip.value = null
}
function onClick(itf) {
  emit('select', itf)
}
</script>

<style scoped>
.iface-panel {
  position: relative;
}
.iface-chassis {
  position: relative;
  border-radius: 18px;
  padding: 16px 18px 18px;
  background: linear-gradient(180deg, hsl(var(--card)), color-mix(in srgb, hsl(var(--muted)) 55%, hsl(var(--card))));
  border: 1px solid hsl(var(--border));
  box-shadow: inset 0 1px 0 hsl(var(--foreground) / 0.04), 0 10px 30px -18px rgba(15, 23, 42, 0.35);
}
/* 四角螺丝 */
.screw {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: hsl(var(--muted-foreground) / 0.35);
  box-shadow: inset 0 0 0 1px hsl(var(--background) / 0.5);
  z-index: 1;
}
.screw--tl {
  left: 12px;
  top: 12px;
}
.screw--br {
  right: 12px;
  bottom: 12px;
}
.iface-chassis::before,
.iface-chassis::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: hsl(var(--muted-foreground) / 0.35);
  box-shadow: inset 0 0 0 1px hsl(var(--background) / 0.5);
  z-index: 1;
}
.iface-chassis::before {
  right: 12px;
  top: 12px;
}
.iface-chassis::after {
  left: 12px;
  bottom: 12px;
}

.panel-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}
.panel-title {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 14px;
  font-weight: 700;
  color: hsl(var(--foreground));
}
.panel-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 0.12);
}
.legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  color: hsl(var(--muted-foreground));
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.legend-sep {
  width: 1px;
  height: 12px;
  background: hsl(var(--border));
}
.lg-ic {
  width: 13px;
  height: 13px;
}
.led {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  display: inline-block;
}
.led--up {
  background: #67c23a;
  box-shadow: 0 0 6px rgba(103, 194, 58, 0.7);
}
.led--down {
  background: #909399;
}

.iface-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.iface-group__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  user-select: none;
  border-radius: 8px;
  padding: 2px 4px;
  transition: background 0.15s ease;
}
.iface-group__head:hover {
  background: hsl(var(--muted) / 0.5);
}
.iface-group__chevron {
  width: 16px;
  height: 16px;
  color: hsl(var(--muted-foreground));
  transition: transform 0.2s ease;
}
.iface-group__chevron.is-collapsed {
  transform: rotate(-90deg);
}
.iface-group__title {
  font-size: 13px;
  font-weight: 700;
  color: hsl(var(--foreground));
}
.iface-group__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 7px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  background: hsl(var(--muted) / 0.6);
}

.iface-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 10px;
}
.iface-grid--dense {
  grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
  gap: 8px;
}

.iface-cell {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 12px 8px 9px;
  border-radius: 12px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--muted) / 0.4);
  cursor: pointer;
  text-align: center;
  transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.18s ease, border-color 0.18s ease;
}
.iface-grid--dense .iface-cell {
  padding: 9px 4px 7px;
}
.iface-cell:hover {
  transform: translateY(-3px);
  border-color: hsl(var(--primary) / 0.5);
  box-shadow: 0 14px 26px -14px rgba(15, 23, 42, 0.45);
}
.iface-cell--up {
  background: color-mix(in srgb, #67c23a 12%, hsl(var(--card)));
  border-color: color-mix(in srgb, #67c23a 45%, hsl(var(--border)));
}
.iface-cell--down {
  background: hsl(var(--muted) / 0.45);
}
.cell-led {
  position: absolute;
  top: 7px;
  right: 7px;
}
.cell-icon {
  width: 26px;
  height: 26px;
}
.iface-grid--dense .cell-icon {
  width: 20px;
  height: 20px;
}
.cell-no {
  font-size: 10px;
  font-weight: 700;
  color: hsl(var(--muted-foreground));
  font-variant-numeric: tabular-nums;
}
.cell-name {
  max-width: 100%;
  font-size: 12px;
  font-weight: 600;
  color: hsl(var(--foreground));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cell-role {
  position: absolute;
  top: 6px;
  left: 6px;
  font-size: 9px;
  font-weight: 700;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 6px;
  color: #8b5cf6;
  background: color-mix(in srgb, #8b5cf6 16%, transparent);
}
.cell-ip {
  max-width: 100%;
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: hsl(var(--primary));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
  padding: 0 2px;
}
.iface-grid--dense .cell-ip {
  font-size: 9px;
}

/* 悬浮明细 */
.iface-tip {
  position: fixed;
  z-index: 90;
  min-width: 172px;
  padding: 10px 12px;
  border-radius: 12px;
  background: hsl(var(--popover) / 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid hsl(var(--border));
  box-shadow: 0 16px 40px -12px rgba(15, 23, 42, 0.4);
  pointer-events: none;
  animation: tip-in 0.12s ease;
}
@keyframes tip-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.tip-name {
  font-size: 13px;
  font-weight: 700;
  color: hsl(var(--foreground));
  margin-bottom: 6px;
}
.tip-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
  color: hsl(var(--muted-foreground));
  line-height: 1.7;
}
.tip-row b {
  color: hsl(var(--foreground));
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.tip-dot {
  width: 7px;
  height: 7px;
  border-radius: 9999px;
  display: inline-block;
}
</style>
