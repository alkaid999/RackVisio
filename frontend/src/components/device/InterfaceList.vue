<template>
  <div class="iface-list">
    <div v-if="loading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <template v-else>
      <!-- 按接口名称前缀自动分组：每组一个可点击折叠/展开的标题行（如 eth / GigabitEthernet / console） -->
      <div v-if="grouped.length" class="iface-groups">
        <section v-for="g in grouped" :key="g.prefix" class="iface-group">
          <header class="iface-group__head" role="button" tabindex="0" @click="toggle(g.prefix)" @keydown.enter="toggle(g.prefix)">
            <ChevronRight class="iface-group__chevron" :class="{ 'is-collapsed': isCollapsed(g.prefix) }" />
            <span class="iface-group__title">{{ g.prefix }}</span>
            <span class="iface-group__count">{{ g.rows.length }}</span>
          </header>
          <div v-show="!isCollapsed(g.prefix)">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead class="w-32">接口名</TableHead>
                  <TableHead class="w-16">槽位</TableHead>
                  <TableHead class="w-20">角色</TableHead>
                  <TableHead class="w-20">速率</TableHead>
                  <TableHead class="w-32">IP 地址</TableHead>
                  <TableHead class="w-24">状态</TableHead>
                  <TableHead class="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="row in g.rows" :key="row.id">
                  <TableCell>{{ row.name }}</TableCell>
                  <TableCell><span class="font-mono text-xs text-muted-foreground">#{{ row.interface_no || '—' }}</span></TableCell>
                  <TableCell>
                    <span
                      v-if="row.role === 'mgmt'"
                      class="role-pill role-pill--mgmt"
                    >管理口</span>
                    <span v-else class="role-pill role-pill--data">数据口</span>
                  </TableCell>
                  <TableCell>{{ row.speed }}</TableCell>
                  <TableCell><span class="font-mono text-xs truncate block max-w-[10rem]" :title="row.ip_address || ''">{{ row.ip_address || '—' }}</span></TableCell>
                  <TableCell><StatusBadge type="interface" :value="row.status" /></TableCell>
                  <TableCell class="text-right">
                    <div class="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" aria-label="查看" title="查看" @click="$emit('view', row)"><Eye class="h-4 w-4" /></Button>
                      <Button v-if="canEdit" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="$emit('edit', row)"><Pencil class="h-4 w-4" /></Button>
                      <Button v-if="canEdit" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="删除" title="删除" @click="onDelete(row)"><Trash2 class="h-4 w-4" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </section>
      </div>
      <div v-else class="py-10 text-center text-sm text-muted-foreground">
        暂无接口，点击「添加接口」录入本设备端口
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import interfaceApi from '@/api/interface'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { ChevronRight, Eye, Pencil, Trash2 } from 'lucide-vue-next'
import { INTERFACE_TYPE_LABELS, INTERFACE_TYPE_COLORS } from '@/utils/constants'
import Button from '@/components/ui/button.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import Spinner from '@/components/ui/spinner.vue'

const props = defineProps({
  deviceId: { type: String, required: true },
  // 是否允许编辑 / 删除接口（无 device:edit 权限时隐藏写操作）。
  canEdit: { type: Boolean, default: true },
})
const emit = defineEmits(['loaded', 'view', 'edit', 'mutated'])

const { success } = useToast()
const { confirm } = useConfirm()

const rows = ref([])
const loading = ref(false)

// 接口按「名称前缀」（连续英文字母，如 eth / GigabitEthernet / Gi / console）自动分组；
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
  for (const r of rows.value) {
    const m = (r.name || '').match(PREFIX_RE)
    const prefix = m ? m[1] : '其他'
    ;(map[prefix] = map[prefix] || []).push(r)
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

async function load() {
  loading.value = true
  try {
    rows.value = await interfaceApi.list(props.deviceId)
    emit('loaded', rows.value.length)
  } finally {
    loading.value = false
  }
}
async function onDelete(row) {
  const ok = await confirm({
    title: '提示',
    description: `确认删除接口「${row.name}」？若已建链将一并断开。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await interfaceApi.remove(row.id)
    success('已删除')
    await load()
    emit('mutated', rows.value.length)
  } catch (e) {
    // 取消或失败
  }
}

// 暴露刷新方法，供父组件（添加/编辑/建链后）调用。
defineExpose({ refresh: load })

onMounted(load)
</script>

<style scoped>
.iface-list {
  min-height: 60px;
}
.iface-groups {
  display: flex;
  flex-direction: column;
  gap: 18px;
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
.iface-group__dot {
  width: 9px;
  height: 9px;
  border-radius: 9999px;
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
.role-pill {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  padding: 3px 7px;
  border-radius: 9999px;
}
.role-pill--data {
  color: #3b82f6;
  background: color-mix(in srgb, #3b82f6 14%, transparent);
}
.role-pill--mgmt {
  color: #8b5cf6;
  background: color-mix(in srgb, #8b5cf6 16%, transparent);
}
</style>
