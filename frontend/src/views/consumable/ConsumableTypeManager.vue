<template>
  <Dialog
    :model-value="visible"
    title="类型与分类管理"
    class="max-w-3xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <div class="grid grid-cols-2 gap-5">
      <!-- 耗材类型 -->
      <div class="flex flex-col">
        <div class="mb-2 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-foreground">耗材类型</h3>
          <Button size="sm" variant="outline" @click="openTypeCreate"><Plus class="h-3.5 w-3.5" />新建</Button>
        </div>

        <div class="max-h-80 space-y-1 overflow-auto pr-1">
          <div
            v-for="t in store.types"
            :key="t.id"
            class="flex cursor-pointer items-center justify-between rounded-md px-2.5 py-2 transition-colors"
            :class="selectedTypeId === t.id ? 'bg-primary/10' : 'hover:bg-muted'"
            @click="selectType(t.id)"
          >
            <div class="flex min-w-0 items-center gap-2">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: consumableTypeColor(t.id) }"></span>
              <div class="min-w-0">
                <div class="truncate text-sm font-medium text-foreground">{{ t.name }}</div>
                <div class="text-xs text-muted-foreground">{{ t.item_count }} 项 · {{ t.category_count }} 分类</div>
              </div>
            </div>
            <div class="flex gap-0.5" @click.stop>
              <Button size="sm" variant="ghost" @click="openTypeEdit(t)"><Pencil class="h-3.5 w-3.5" /></Button>
              <Button size="sm" variant="ghost" class="text-destructive hover:bg-destructive/10" @click="removeType(t)"><Trash2 class="h-3.5 w-3.5" /></Button>
            </div>
          </div>
          <div v-if="!store.types.length" class="py-8 text-center text-sm text-muted-foreground">暂无类型，点击「新建」添加</div>
        </div>
      </div>

      <!-- 分类 -->
      <div class="flex flex-col border-l border-border pl-5">
        <div class="mb-2 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-foreground">
            分类<span v-if="selectedType" class="ml-1 text-xs font-normal text-muted-foreground">· {{ selectedType.name }}</span>
          </h3>
          <Button size="sm" variant="outline" :disabled="!selectedTypeId" @click="openCatCreate"><Plus class="h-3.5 w-3.5" />新建</Button>
        </div>

        <div v-if="!selectedTypeId" class="flex flex-1 items-center justify-center py-10 text-sm text-muted-foreground">
          请选择左侧类型
        </div>
        <template v-else>
          <div class="max-h-80 space-y-1 overflow-auto pr-1">
            <div
              v-for="c in store.categories"
              :key="c.id"
              class="flex items-center justify-between rounded-md px-2.5 py-2 transition-colors hover:bg-muted"
            >
              <div class="min-w-0">
                <div class="truncate text-sm font-medium text-foreground">{{ c.name }}</div>
                <div class="text-xs text-muted-foreground">{{ c.item_count }} 项</div>
              </div>
              <div class="flex gap-0.5">
                <Button size="sm" variant="ghost" @click="openCatEdit(c)"><Pencil class="h-3.5 w-3.5" /></Button>
                <Button size="sm" variant="ghost" class="text-destructive hover:bg-destructive/10" @click="removeCat(c)"><Trash2 class="h-3.5 w-3.5" /></Button>
              </div>
            </div>
            <div v-if="!store.categories.length" class="py-8 text-center text-sm text-muted-foreground">该类型下暂无分类</div>
          </div>
        </template>
      </div>
    </div>

    <!-- 类型新建/编辑弹窗（需求#4：统一弹窗卡片操作，非内联） -->
    <Dialog
      v-model="typeDialogVisible"
      :title="typeDraft.mode === 'edit' ? '编辑耗材类型' : '新建耗材类型'"
      :z-index="'z-[60]'"
      :dismissible="false"
      class="max-w-md"
    >
      <div class="space-y-3">
        <div>
          <label class="mb-1 block text-sm font-medium text-foreground">类型名称</label>
          <Input v-model="typeDraft.name" placeholder="类型名称（如：网线）" />
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
          <Input v-model="catDraft.name" placeholder="分类名称（如：六类跳线）" />
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

    <template #footer>
      <div class="flex justify-end">
        <Button variant="outline" @click="emit('update:visible', false)">关闭</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useConsumableStore } from '@/stores/consumable'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import Dialog from '@/components/ui/dialog.vue'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import { Plus, Pencil, Trash2 } from 'lucide-vue-next'
import { consumableTypeColor, setConsumableTypeOrder } from '@/utils/constants'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['update:visible', 'changed'])

const store = useConsumableStore()
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
  setConsumableTypeOrder(store.types.map((t) => t.id))
  if (!selectedTypeId.value && store.types.length) {
    await selectType(store.types[0].id)
  }
}

async function selectType(id) {
  selectedTypeId.value = id
  await store.fetchCategories(id)
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
    // 需求#3：保存后选中当前创建的类型，并让列表按「新增置顶」刷新。
    selectedTypeId.value = targetId
    await loadTypes()
    await selectType(targetId)
    emit('changed')
  } finally {
    typeSaving.value = false
  }
}
async function removeType(t) {
  const ok = await confirm({
    title: '删除耗材类型',
    description: `确认删除类型「${t.name}」？其下分类与耗材将一并删除，不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.removeType(t.id)
    success('已删除')
    if (selectedTypeId.value === t.id) selectedTypeId.value = ''
    await loadTypes()
    emit('changed')
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
    // 需求#2：新增分类后立即同步分类列表（无需重新点类型）。
    await store.fetchCategories(selectedTypeId.value)
    await store.fetchTypes() // 同步类型下的分类计数
    emit('changed')
  } finally {
    catSaving.value = false
  }
}
async function removeCat(c) {
  const ok = await confirm({
    title: '删除分类',
    description: `确认删除分类「${c.name}」？其下耗材将一并删除，不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.removeCategory(c.id)
    success('已删除')
    await store.fetchCategories(selectedTypeId.value)
    await store.fetchTypes()
    emit('changed')
  } catch (e) {
    // 拦截器提示
  }
}

watch(
  () => props.visible,
  async (v) => {
    if (!v) {
      // 主弹窗关闭时一并收起嵌套弹窗，避免残留。
      typeDialogVisible.value = false
      catDialogVisible.value = false
      typeDraft.mode = 'none'
      catDraft.mode = 'none'
      return
    }
    await loadTypes()
  },
  { immediate: false }
)
</script>
