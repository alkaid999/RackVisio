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
          <Button size="sm" variant="outline" @click="startTypeCreate"><Plus class="h-3.5 w-3.5" />新建</Button>
        </div>

        <!-- 类型内联表单 -->
        <div v-if="typeDraft.mode !== 'none'" class="mb-2 space-y-2 rounded-lg border border-border bg-muted/40 p-2.5">
          <Input v-model="typeDraft.name" placeholder="类型名称（如：网线）" />
          <textarea
            v-model="typeDraft.description"
            rows="2"
            placeholder="说明（可选）"
            class="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
          ></textarea>
          <div class="flex justify-end gap-2">
            <Button size="sm" :loading="typeSaving" @click="saveType">保存</Button>
            <Button size="sm" variant="outline" @click="cancelType">取消</Button>
          </div>
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
              <Button size="sm" variant="ghost" @click="startTypeEdit(t)"><Pencil class="h-3.5 w-3.5" /></Button>
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
          <Button size="sm" variant="outline" :disabled="!selectedTypeId" @click="startCatCreate"><Plus class="h-3.5 w-3.5" />新建</Button>
        </div>

        <div v-if="!selectedTypeId" class="flex flex-1 items-center justify-center py-10 text-sm text-muted-foreground">
          请选择左侧类型
        </div>
        <template v-else>
          <!-- 分类内联表单 -->
          <div v-if="catDraft.mode !== 'none'" class="mb-2 space-y-2 rounded-lg border border-border bg-muted/40 p-2.5">
            <Input v-model="catDraft.name" placeholder="分类名称（如：六类跳线）" />
            <textarea
              v-model="catDraft.description"
              rows="2"
              placeholder="说明（可选）"
              class="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
            ></textarea>
            <div class="flex justify-end gap-2">
              <Button size="sm" :loading="catSaving" @click="saveCat">保存</Button>
              <Button size="sm" variant="outline" @click="cancelCat">取消</Button>
            </div>
          </div>

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
                <Button size="sm" variant="ghost" @click="startCatEdit(c)"><Pencil class="h-3.5 w-3.5" /></Button>
                <Button size="sm" variant="ghost" class="text-destructive hover:bg-destructive/10" @click="removeCat(c)"><Trash2 class="h-3.5 w-3.5" /></Button>
              </div>
            </div>
            <div v-if="!store.categories.length" class="py-8 text-center text-sm text-muted-foreground">该类型下暂无分类</div>
          </div>
        </template>
      </div>
    </div>

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
const catDraft = reactive({ mode: 'none', id: '', name: '', description: '' })
const catSaving = ref(false)

async function loadTypes() {
  await store.fetchTypes()
  setConsumableTypeOrder(store.types.map((t) => t.id))
  if (!selectedTypeId.value && store.types.length) {
    await selectType(store.types[0].id)
  }
}

async function selectType(id) {
  selectedTypeId.value = id
  catDraft.mode = 'none'
  await store.fetchCategories(id)
}

// ===== 类型 =====
function startTypeCreate() {
  catDraft.mode = 'none'
  Object.assign(typeDraft, { mode: 'create', id: '', name: '', description: '' })
}
function startTypeEdit(t) {
  Object.assign(typeDraft, { mode: 'edit', id: t.id, name: t.name, description: t.description || '' })
}
function cancelType() {
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
    if (typeDraft.mode === 'create') {
      await store.createType(payload)
    } else {
      await store.updateType(typeDraft.id, payload)
    }
    success(typeDraft.mode === 'create' ? '类型已创建' : '类型已更新')
    typeDraft.mode = 'none'
    await loadTypes()
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
function startCatCreate() {
  if (!selectedTypeId.value) return
  Object.assign(catDraft, { mode: 'create', id: '', name: '', description: '' })
}
function startCatEdit(c) {
  Object.assign(catDraft, { mode: 'edit', id: c.id, name: c.name, description: c.description || '' })
}
function cancelCat() {
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
    catDraft.mode = 'none'
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
    if (!v) return
    await loadTypes()
  },
  { immediate: false }
)
</script>
