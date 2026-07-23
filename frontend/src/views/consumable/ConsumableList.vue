<template>
  <div class="consumable-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">耗材列表</h2>
        <p class="page-sub">共 {{ store.total }} 项耗材 · 按类型 / 分类筛选，支持卡片与表格视图，库存变动全程留痕</p>
      </div>
      <div class="flex items-center gap-2">
        <div class="inline-flex rounded-lg border border-border bg-muted p-0.5">
          <button
            type="button"
            class="flex h-8 items-center gap-1.5 rounded-md px-3 text-sm transition-all"
            :class="viewMode === 'card' ? 'bg-background text-foreground shadow-soft' : 'text-muted-foreground hover:text-foreground'"
            @click="setView('card')"
          >
            <LayoutGrid class="h-4 w-4" />卡片
          </button>
          <button
            type="button"
            class="flex h-8 items-center gap-1.5 rounded-md px-3 text-sm transition-all"
            :class="viewMode === 'table' ? 'bg-background text-foreground shadow-soft' : 'text-muted-foreground hover:text-foreground'"
            @click="setView('table')"
          >
            <List class="h-4 w-4" />表格
          </button>
        </div>
        <Button v-if="canEdit" variant="outline" @click="openTypeManager"><Tags class="h-4 w-4" />类型与分类</Button>
        <Button v-if="canEdit" class="ml-auto" @click="openCreate"><Plus class="h-4 w-4" />新建耗材</Button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Package class="h-3.5 w-3.5 text-muted-foreground" />耗材类型</Label>
          <Select v-model="filter.typeId" class="w-40" @update:model-value="onTypeChange">
            <SelectTrigger placeholder="全部类型" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部类型</SelectItem>
              <SelectItem v-for="t in store.types" :key="t.id" :value="t.id">{{ t.name }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Layers class="h-3.5 w-3.5 text-muted-foreground" />分类</Label>
          <Select
            v-model="filter.categoryId"
            class="w-40"
            :disabled="!typeSelected"
            @update:model-value="reload"
          >
            <SelectTrigger :placeholder="typeSelected ? '全部分类' : '请先选类型'" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部分类</SelectItem>
              <SelectItem v-for="c in store.categories" :key="c.id" :value="c.id">{{ c.name }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="名称 / 规格" class="w-52 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="store.loading" class="flex justify-center py-20">
      <Spinner class="h-6 w-6 text-primary" />
    </div>

    <template v-else>
      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'">
        <div v-if="!store.items.length">
          <EmptyState :icon="Package" title="暂无耗材" />
        </div>
        <div v-else class="grid-cards">
          <Card v-for="item in store.items" :key="item.id" hover class="group">
            <div class="mb-3 flex items-start justify-between gap-2">
              <div class="min-w-0">
                <span class="block truncate text-base font-semibold text-foreground">{{ item.name }}</span>
                <span
                  v-if="item.current_quantity === 0"
                  class="mt-1 inline-flex items-center rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-medium text-destructive"
                >库存为 0</span>
              </div>
              <span
                class="shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium"
                :style="typeBadgeStyle(item.type_id)"
              >{{ item.type_name }}</span>
            </div>
            <div class="mb-3 flex items-baseline gap-1.5">
              <span class="text-3xl font-bold leading-none" :style="{ color: item.current_quantity === 0 ? '#ef4444' : 'hsl(var(--foreground))' }">{{ item.current_quantity }}</span>
              <span class="text-sm text-muted-foreground">{{ item.unit || '个' }}</span>
              <span class="ml-1 text-xs text-muted-foreground">当前结存</span>
            </div>
            <div class="space-y-1.5 text-sm text-muted-foreground">
              <div class="flex justify-between"><span>分类</span><span class="text-foreground">{{ item.category_name || '—' }}</span></div>
              <div class="flex justify-between"><span>规格</span><span class="text-foreground">{{ item.spec || '—' }}</span></div>
            </div>
            <div class="mt-2.5 flex flex-wrap justify-end gap-1 border-t border-border pt-2.5">
              <Button variant="ghost" size="sm" @click.stop="openHistory(item)"><History class="h-3.5 w-3.5" />历史</Button>
              <Button v-if="canEdit" variant="ghost" size="sm" @click.stop="openStock(item)"><ArrowLeftRight class="h-3.5 w-3.5" />变动</Button>
              <Button v-if="canEdit" variant="ghost" size="sm" @click.stop="openEdit(item.id)"><Pencil class="h-3.5 w-3.5" />编辑</Button>
              <Button v-if="canEdit" variant="ghost" size="sm" class="text-destructive hover:bg-destructive/10" @click.stop="onDelete(item)"><Trash2 class="h-3.5 w-3.5" />删除</Button>
            </div>
          </Card>
        </div>
      </div>

      <!-- 表格视图 -->
      <div v-else>
        <div v-if="!store.items.length">
          <EmptyState :icon="Package" title="暂无耗材" />
        </div>
        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>分类</TableHead>
              <TableHead>规格</TableHead>
              <TableHead>单位</TableHead>
              <TableHead class="text-right">当前结存</TableHead>
              <TableHead class="w-44 text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="item in store.items" :key="item.id">
              <TableCell>
                <button class="font-medium text-primary hover:underline" @click="openHistory(item)">{{ item.name }}</button>
              </TableCell>
              <TableCell>
                <span
                  class="shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium"
                  :style="typeBadgeStyle(item.type_id)"
                >{{ item.type_name }}</span>
              </TableCell>
              <TableCell class="text-muted-foreground">{{ item.category_name || '—' }}</TableCell>
              <TableCell class="text-muted-foreground">{{ item.spec || '—' }}</TableCell>
              <TableCell class="text-muted-foreground">{{ item.unit || '—' }}</TableCell>
              <TableCell class="text-right">
                <span class="font-semibold" :style="{ color: item.current_quantity === 0 ? '#ef4444' : 'hsl(var(--foreground))' }">{{ item.current_quantity }}</span>
                <span class="ml-1 text-xs text-muted-foreground">{{ item.unit || '' }}</span>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-1">
                  <EntityActions
                    :extra-actions="rowExtraActions(item)"
                    :show-view="false"
                    :show-edit="canEdit"
                    :show-delete="canEdit"
                    @edit="openEdit(item.id)"
                    @delete="onDelete(item)"
                  />
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </template>

    <!-- 分页 -->
    <ListPager v-if="store.total > 0" :total="store.total" :page="page" :page-size="pageSize" @change="goPage" />

    <!-- 新建 / 编辑耗材弹窗 -->
    <ConsumableForm v-model:visible="formVisible" :mode="formMode" :item-id="formItemId" @saved="load" />
    <!-- 库存变动弹窗 -->
    <ConsumableStockDialog v-model:visible="stockVisible" :item="stockItem" @saved="load" />
    <!-- 变动历史弹窗 -->
    <ConsumableHistoryDialog v-model:visible="historyVisible" :item="historyItem" />
    <!-- 类型与分类管理弹窗 -->
    <ConsumableTypeManager v-model:visible="typeMgrVisible" @changed="onTypesChanged" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  LayoutGrid, List, Plus, Package, Search, Filter, Undo2, ArrowLeftRight,
  History, Pencil, Trash2, Tags, Layers,
} from 'lucide-vue-next'
import { useConsumableStore } from '@/stores/consumable'
import { useAuthStore } from '@/stores/auth'
import ConsumableForm from '@/views/consumable/ConsumableForm.vue'
import ConsumableStockDialog from '@/views/consumable/ConsumableStockDialog.vue'
import ConsumableHistoryDialog from '@/views/consumable/ConsumableHistoryDialog.vue'
import ConsumableTypeManager from '@/views/consumable/ConsumableTypeManager.vue'
import consumableApi from '@/api/consumable'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import { SELECT_ALL, toFilterParam, consumableTypeBadgeStyle as typeBadgeStyle, setConsumableTypeOrder } from '@/utils/constants'
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
import EmptyState from '@/components/ui/empty-state.vue'
import ListPager from '@/components/common/ListPager.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'

const store = useConsumableStore()
const auth = useAuthStore()
const { success } = useToast()
const { confirm } = useConfirm()

// 类型配色基于「全量类型有序列表」统一计算，保证每种类型颜色唯一且与各视图一致。
watch(
  () => store.types,
  (list) => setConsumableTypeOrder((list || []).map((t) => t.id)),
  { immediate: true },
)

// 写操作（新建 / 编辑 / 删除 / 库存变动 / 类型分类管理）均需 consumable:edit。
const canEdit = computed(() => auth.hasPermission('consumable:edit'))

const { filter, clear } = usePersistentFilter('ConsumableList', () => ({
  typeId: SELECT_ALL,
  categoryId: SELECT_ALL,
  keyword: '',
}))
const viewMode = ref('card')

const page = ref(1)
const pageSize = computed(() => (viewMode.value === 'card' ? 12 : 10))
const totalPages = computed(() => Math.max(1, Math.ceil(store.total / pageSize.value)))

const typeSelected = computed(() => filter.typeId && filter.typeId !== SELECT_ALL)

function setView(mode) {
  if (viewMode.value === mode) return
  viewMode.value = mode
  page.value = 1
  load()
}

function buildParams() {
  return {
    page: page.value,
    size: pageSize.value,
    type_id: toFilterParam(filter.typeId),
    category_id: toFilterParam(filter.categoryId),
    keyword: filter.keyword || undefined,
  }
}
async function load() {
  await store.fetchItems(buildParams())
  if (store.items.length === 0 && page.value > 1 && store.total > 0) {
    page.value = Math.max(1, totalPages.value)
    await store.fetchItems(buildParams())
  }
}
function reload() {
  page.value = 1
  load()
}
function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  load()
}
function resetFilter() {
  clear()
  reload()
}
async function onTypeChange() {
  // 切换类型时清空分类并重新拉取该类型下的分类选项。
  filter.categoryId = SELECT_ALL
  await store.fetchCategories(typeSelected.value ? filter.typeId : '')
  reload()
}

// ===== 弹窗控制 =====
const formVisible = ref(false)
const formMode = ref('create')
const formItemId = ref('')
const stockVisible = ref(false)
const stockItem = ref(null)
const historyVisible = ref(false)
const historyItem = ref(null)
const typeMgrVisible = ref(false)

function openCreate() {
  formMode.value = 'create'
  formItemId.value = ''
  formVisible.value = true
}
function openEdit(id) {
  formMode.value = 'edit'
  formItemId.value = id
  formVisible.value = true
}
function openStock(item) {
  stockItem.value = item
  stockVisible.value = true
}
function openHistory(item) {
  historyItem.value = item
  historyVisible.value = true
}
function openTypeManager() {
  typeMgrVisible.value = true
}
// 表格操作列的扩展动作（历史/变动），复用 EntityActions 紧凑图标按钮样式，与各列表表格一致。
function rowExtraActions(item) {
  const acts = [{ key: 'history', label: '变动历史', icon: History, onClick: () => openHistory(item) }]
  if (canEdit.value) {
    acts.push({ key: 'stock', label: '库存变动', icon: ArrowLeftRight, onClick: () => openStock(item) })
  }
  return acts
}
async function onTypesChanged() {
  // 类型 / 分类增删改后，刷新类型下拉并重置分类筛选。
  await store.fetchTypes()
  filter.categoryId = SELECT_ALL
  await store.fetchCategories(typeSelected.value ? filter.typeId : '')
  load()
}

async function onDelete(item) {
  const ok = await confirm({
    title: '删除耗材',
    description: `确认删除耗材「${item.name}」？其全部库存变动历史将一并删除，且不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await consumableApi.removeItem(item.id)
    success('删除成功')
    load()
  } catch (e) {
    // 拦截器已提示
  }
}

onMounted(async () => {
  await store.fetchTypes()
  await store.fetchCategories(typeSelected.value ? filter.typeId : '')
  load()
})
</script>

<style scoped>
.toolbar {
  background: oklch(var(--card) / 0.8);
  border: 1px solid oklch(var(--border) / 0.6);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
  backdrop-filter: blur(8px);
}
.grid-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
</style>
