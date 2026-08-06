<template>
  <div class="type-manager-page">
    <div class="page-head">
      <div>
        <h2 class="page-title flex items-center gap-2"><Cpu class="h-5 w-5 text-primary" />硬件类型与分类</h2>
        <p class="page-sub">维护硬件类型与分类字典，作为硬件筛选与统计的统一来源（预置主板 / CPU 处理器 / 内存条 / 硬盘 / 阵列卡 / 网卡 / 电源模块，可自定义）</p>
      </div>
    </div>

    <Card class="overflow-hidden">
      <!-- 双栏布局：左「类型」右「分类」，选中态高亮联动 -->
      <div class="grid grid-cols-1 gap-0 md:grid-cols-2">
        <!-- 硬件类型 -->
        <div class="flex flex-col border-b border-border p-5 md:border-b-0 md:border-r">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-foreground">
              硬件类型
              <span class="rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">{{ store.types.length }}</span>
            </h3>
            <Button size="sm" variant="outline" @click="openTypeCreate"><Plus class="h-3.5 w-3.5" />新建</Button>
          </div>

          <div class="max-h-[34rem] space-y-1 overflow-auto pr-1">
            <div
              v-for="t in store.types"
              :key="t.id"
              class="group flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2.5 transition-all"
              :class="selectedTypeId === t.id
                ? 'border-primary/40 bg-primary/10 shadow-soft'
                : 'border-transparent hover:border-border hover:bg-muted'"
              @click="selectType(t.id)"
            >
              <div class="flex min-w-0 items-center gap-2.5">
                <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: hardwareTypeColor(t.id) }"></span>
                <div class="min-w-0">
                  <div class="truncate text-sm font-medium text-foreground">{{ t.name }}</div>
                  <div class="text-xs text-muted-foreground">{{ t.item_count }} 件 · {{ t.category_count }} 分类</div>
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100" @click.stop>
                <!-- 手动排序：上移 / 下移（首条禁上、末条禁下） -->
                <Button size="sm" variant="ghost" :disabled="isFirstType(t.id)" @click="moveType(t.id, -1)"><ArrowUp class="h-3.5 w-3.5" /></Button>
                <Button size="sm" variant="ghost" :disabled="isLastType(t.id)" @click="moveType(t.id, 1)"><ArrowDown class="h-3.5 w-3.5" /></Button>
                <Button size="sm" variant="ghost" @click="openTypeEdit(t)"><Pencil class="h-3.5 w-3.5" /></Button>
                <Button size="sm" variant="ghost" class="text-destructive hover:bg-destructive/10" @click="removeType(t)"><Trash2 class="h-3.5 w-3.5" /></Button>
              </div>
            </div>
            <div v-if="!store.types.length" class="py-10 text-center text-sm text-muted-foreground">暂无类型，点击「新建」添加</div>
          </div>
        </div>

        <!-- 分类 -->
        <div class="flex flex-col p-5">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="flex items-center gap-2 text-sm font-semibold text-foreground">
              分类
              <span v-if="selectedType" class="flex items-center gap-1 text-xs font-normal text-muted-foreground">
                <ChevronRight class="h-3 w-3" />{{ selectedType.name }}
              </span>
            </h3>
            <Button size="sm" variant="outline" :disabled="!selectedTypeId" @click="openCatCreate"><Plus class="h-3.5 w-3.5" />新建</Button>
          </div>

          <div v-if="!selectedTypeId" class="flex flex-1 flex-col items-center justify-center py-14 text-sm text-muted-foreground">
            <MousePointerClick class="mb-2 h-8 w-8 opacity-40" />
            <span>请选择左侧类型</span>
          </div>
          <template v-else>
            <div class="max-h-[34rem] space-y-1 overflow-auto pr-1">
              <div
                v-for="c in store.categories"
                :key="c.id"
                class="group flex items-center justify-between rounded-lg border border-transparent px-3 py-2.5 transition-all hover:border-border hover:bg-muted"
              >
                <div class="min-w-0">
                  <div class="truncate text-sm font-medium text-foreground">{{ c.name }}</div>
                  <div class="text-xs text-muted-foreground">{{ c.item_count }} 件</div>
                </div>
                <div class="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                  <!-- 手动排序：上移 / 下移（首条禁上、末条禁下） -->
                  <Button size="sm" variant="ghost" :disabled="isFirstCat(c.id)" @click="moveCat(c.id, -1)"><ArrowUp class="h-3.5 w-3.5" /></Button>
                  <Button size="sm" variant="ghost" :disabled="isLastCat(c.id)" @click="moveCat(c.id, 1)"><ArrowDown class="h-3.5 w-3.5" /></Button>
                  <Button size="sm" variant="ghost" @click="openCatEdit(c)"><Pencil class="h-3.5 w-3.5" /></Button>
                  <Button size="sm" variant="ghost" class="text-destructive hover:bg-destructive/10" @click="removeCat(c)"><Trash2 class="h-3.5 w-3.5" /></Button>
                </div>
              </div>
              <div v-if="!store.categories.length" class="py-10 text-center text-sm text-muted-foreground">该类型下暂无分类</div>
            </div>
          </template>
        </div>
      </div>

      <!-- 类型新建/编辑弹窗 -->
      <Dialog
        v-model="typeDialogVisible"
        :title="typeDraft.mode === 'edit' ? '编辑硬件类型' : '新建硬件类型'"
        :z-index="'z-[60]'"
        :dismissible="false"
        class="max-w-md"
      >
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-sm font-medium text-foreground">类型名称</label>
            <Input v-model="typeDraft.name" placeholder="类型名称（如：主板 / CPU / 内存）" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-foreground">说明</label>
            <textarea
              v-model="typeDraft.description"
              rows="3"
              placeholder="说明（可选）"
              class="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
            ></textarea>
          </div>
        </div>
        <template #footer>
          <div class="flex justify-end gap-2">
            <Button size="sm" variant="outline" @click="closeTypeDialog">取消</Button>
            <Button size="sm" :loading="typeSaving" @click="saveType">保存</Button>
          </div>
        </template>
      </Dialog>

      <!-- 分类新建/编辑弹窗 -->
      <Dialog
        v-model="catDialogVisible"
        :title="catDraft.mode === 'edit' ? '编辑分类' : '新建分类'"
        :z-index="'z-[60]'"
        :dismissible="false"
        class="max-w-md"
      >
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-sm font-medium text-foreground">分类名称</label>
            <Input v-model="catDraft.name" placeholder="分类名称（如：DDR4 ECC）" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-foreground">说明</label>
            <textarea
              v-model="catDraft.description"
              rows="3"
              placeholder="说明（可选）"
              class="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
            ></textarea>
          </div>
        </div>
        <template #footer>
          <div class="flex justify-end gap-2">
            <Button size="sm" variant="outline" @click="closeCatDialog">取消</Button>
            <Button size="sm" :loading="catSaving" @click="saveCat">保存</Button>
          </div>
        </template>
      </Dialog>
    </Card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useHardwareStore } from '@/stores/hardware'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import Dialog from '@/components/ui/dialog.vue'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Card from '@/components/ui/card.vue'
import { Plus, Pencil, Trash2, Cpu, Layers, ChevronRight, MousePointerClick, ArrowUp, ArrowDown } from 'lucide-vue-next'
import { hardwareTypeColor, setHardwareTypeOrder } from '@/utils/constants'

const store = useHardwareStore()
const { success, error: toastError } = useToast()
const { confirm } = useConfirm()

const selectedTypeId = ref('')
const selectedType = computed(() => store.types.find((t) => t.id === selectedTypeId.value) || null)

const typeDraft = reactive({ mode: 'none', id: '', name: '', description: '' })
const typeSaving = ref(false)
const typeDialogVisible = ref(false)

const catDraft = reactive({ mode: 'none', id: '', name: '', description: '' })
const catSaving = ref(false)
const catDialogVisible = ref(false)

async function loadTypes() {
  await store.fetchTypes()
  setHardwareTypeOrder(store.types.map((t) => t.id))
  if (!selectedTypeId.value && store.types.length) {
    await selectType(store.types[0].id)
  }
}

async function selectType(id) {
  selectedTypeId.value = id
  await store.fetchCategories(id)
}

// ===== 手动排序（持久化：调后端 reorder，返回的全量列表刷新本地）=====
function isFirstType(id) {
  const idx = store.types.findIndex((t) => t.id === id)
  return idx <= 0
}
function isLastType(id) {
  const idx = store.types.findIndex((t) => t.id === id)
  return idx < 0 || idx >= store.types.length - 1
}
async function moveType(id, dir) {
  const idx = store.types.findIndex((t) => t.id === id)
  const target = idx + dir
  if (idx < 0 || target < 0 || target >= store.types.length) return
  const list = store.types.map((t) => t.id)
  ;[list[idx], list[target]] = [list[target], list[idx]]
  await store.reorderTypes(list) // 持久化并刷新（含 setHardwareTypeOrder 联动由调用方处理）
  setHardwareTypeOrder(store.types.map((t) => t.id))
}

function isFirstCat(id) {
  const idx = store.categories.findIndex((c) => c.id === id)
  return idx <= 0
}
function isLastCat(id) {
  const idx = store.categories.findIndex((c) => c.id === id)
  return idx < 0 || idx >= store.categories.length - 1
}
async function moveCat(id, dir) {
  const idx = store.categories.findIndex((c) => c.id === id)
  const target = idx + dir
  if (idx < 0 || target < 0 || target >= store.categories.length) return
  const list = store.categories.map((c) => c.id)
  ;[list[idx], list[target]] = [list[target], list[idx]]
  await store.reorderCategories(selectedTypeId.value, list)
}

// ===== 类型 =====
function openTypeCreate() {
  Object.assign(typeDraft, { mode: 'create', id: '', name: '', description: '' })
  typeDialogVisible.value = true
}
function openTypeEdit(t) {
  Object.assign(typeDraft, { mode: 'edit', id: t.id, name: t.name, description: t.description || '' })
  typeDialogVisible.value = true
}
function closeTypeDialog() {
  typeDialogVisible.value = false
  typeDraft.mode = 'none'
}
async function saveType() {
  const name = typeDraft.name.trim()
  if (!name) {
    toastError('请输入类型名称')
    return
  }
  typeSaving.value = true
  try {
    const payload = { name, description: typeDraft.description.trim() || undefined }
    let targetId = typeDraft.id
    if (typeDraft.mode === 'create') {
      const created = await store.createType(payload)
      targetId = created.id
    } else {
      await store.updateType(typeDraft.id, payload)
    }
    success(typeDraft.mode === 'create' ? '类型已创建' : '类型已更新')
    typeDialogVisible.value = false
    typeDraft.mode = 'none'
    selectedTypeId.value = targetId
    await loadTypes()
    await selectType(targetId)
  } finally {
    typeSaving.value = false
  }
}
async function removeType(t) {
  const ok = await confirm({
    title: '删除硬件类型',
    description: `确认删除类型「${t.name}」？其下分类与硬件将一并删除，不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.removeType(t.id)
    success('已删除')
    if (selectedTypeId.value === t.id) selectedTypeId.value = ''
    await loadTypes()
  } catch (e) {
    // 拦截器提示
  }
}

// ===== 分类 =====
function openCatCreate() {
  if (!selectedTypeId.value) return
  Object.assign(catDraft, { mode: 'create', id: '', name: '', description: '' })
  catDialogVisible.value = true
}
function openCatEdit(c) {
  Object.assign(catDraft, { mode: 'edit', id: c.id, name: c.name, description: c.description || '' })
  catDialogVisible.value = true
}
function closeCatDialog() {
  catDialogVisible.value = false
  catDraft.mode = 'none'
}
async function saveCat() {
  const name = catDraft.name.trim()
  if (!name) {
    toastError('请输入分类名称')
    return
  }
  catSaving.value = true
  try {
    const payload = { name, description: catDraft.description.trim() || undefined }
    if (catDraft.mode === 'create') {
      await store.createCategory(selectedTypeId.value, payload)
    } else {
      await store.updateCategory(catDraft.id, payload)
    }
    success(catDraft.mode === 'create' ? '分类已创建' : '分类已更新')
    catDialogVisible.value = false
    catDraft.mode = 'none'
    await store.fetchCategories(selectedTypeId.value)
    await store.fetchTypes()
  } finally {
    catSaving.value = false
  }
}
async function removeCat(c) {
  const ok = await confirm({
    title: '删除分类',
    description: `确认删除分类「${c.name}」？其下硬件将一并删除，不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.removeCategory(c.id)
    success('已删除')
    await store.fetchCategories(selectedTypeId.value)
    await store.fetchTypes()
  } catch (e) {
    // 拦截器提示
  }
}

onMounted(loadTypes)
</script>
