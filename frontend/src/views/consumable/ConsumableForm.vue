<template>
  <Dialog
    :model-value="visible"
    :title="isEdit ? '编辑耗材' : '新建耗材'"
    class="max-w-2xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <Form ref="formRef" :model="form" :rules="rules">
      <div class="grid grid-cols-2 gap-4">
        <FormItem name="type_id" label="耗材类型">
          <Select v-model="form.type_id" class="w-full" @update:model-value="onTypeChange">
            <SelectTrigger placeholder="选择类型" />
            <SelectContent>
              <SelectItem v-for="t in store.types" :key="t.id" :value="t.id">{{ t.name }}</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>
        <FormItem name="category_id" label="分类">
          <Select v-model="form.category_id" class="w-full" :disabled="!form.type_id">
            <SelectTrigger :placeholder="form.type_id ? '选择分类' : '请先选类型'" />
            <SelectContent>
              <SelectItem v-for="c in store.categories" :key="c.id" :value="c.id">{{ c.name }}</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>
      </div>
      <FormItem name="name" label="名称">
        <Input v-model="form.name" placeholder="如：六类非屏蔽跳线 2m" />
      </FormItem>
      <div class="grid grid-cols-2 gap-4">
        <FormItem name="spec" label="规格">
          <Input v-model="form.spec" placeholder="如：CAT6 / 10G（选填）" />
        </FormItem>
        <FormItem name="unit" label="单位">
          <Input v-model="form.unit" placeholder="如：根 / 个 / 箱（选填）" />
        </FormItem>
      </div>
      <FormItem v-if="!isEdit" name="current_quantity" label="初始数量">
        <Input v-model="form.current_quantity" type="number" placeholder="建档时的当前结存，缺省 0" />
        <p class="mt-1 text-xs text-muted-foreground">保存后将自动生成一条「盘点」记录作为初始建账留痕。</p>
      </FormItem>
      <FormItem label="备注" name="remark">
        <textarea
          v-model="form.remark"
          rows="2"
          placeholder="补充说明（可选）"
          class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
        ></textarea>
      </FormItem>
    </Form>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button variant="outline" @click="emit('update:visible', false)">取消</Button>
        <Button :loading="submitting" @click="onSubmit">保存</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { useConsumableStore } from '@/stores/consumable'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'
import Button from '@/components/ui/button.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  mode: { type: String, default: 'create' }, // 'create' | 'edit'
  itemId: { type: [String, Number], default: '' },
})
const emit = defineEmits(['update:visible', 'saved'])

const { success } = useToast()
const store = useConsumableStore()
const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => props.mode === 'edit')

const emptyForm = () => ({
  type_id: '',
  category_id: '',
  name: '',
  spec: '',
  unit: '',
  // 编辑态不允许直接改数量（须经库存变动接口）；创建态可填初始结存。
  current_quantity: 0,
  remark: '',
})
const form = reactive(emptyForm())

const rules = {
  type_id: [{ required: true, message: '请选择耗材类型', trigger: 'change' }],
  category_id: [{ required: true, message: '请选择分类', trigger: 'change' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

// 类型变更 → 重新拉取该类型下的分类并清空已选分类。
async function onTypeChange() {
  form.category_id = ''
  if (form.type_id) {
    await store.fetchCategories(form.type_id)
  } else {
    store.categories = []
  }
}

watch(
  () => props.visible,
  async (v) => {
    if (!v) return
    Object.assign(form, emptyForm())
    formRef.value?.clearValidate?.()
    // 确保类型下拉有数据（列表已加载，这里兜底）。
    if (!store.types.length) await store.fetchTypes()
    if (isEdit.value && props.itemId) {
      const item = await store.fetchItem(props.itemId)
      if (item) {
        form.type_id = item.type_id || ''
        // 先拉取该类型下的分类，再回填分类，确保下拉有可选项。
        if (item.type_id) await store.fetchCategories(item.type_id)
        form.category_id = item.category_id || ''
        form.name = item.name || ''
        form.spec = item.spec || ''
        form.unit = item.unit || ''
        form.remark = item.remark || ''
      }
    } else {
      store.categories = []
    }
  },
  { immediate: false }
)

async function onSubmit() {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        type_id: form.type_id,
        category_id: form.category_id,
        name: form.name,
        spec: form.spec || undefined,
        unit: form.unit || undefined,
        remark: form.remark || undefined,
      }
      if (isEdit.value) {
        await store.updateItem(props.itemId, payload)
        success('更新成功')
      } else {
        payload.current_quantity = Number(form.current_quantity) || 0
        await store.createItem(payload)
        success('创建成功')
      }
      emit('saved')
      emit('update:visible', false)
    } catch (e) {
      // 唯一约束等错误已由统一拦截器提示
    } finally {
      submitting.value = false
    }
  })
}
</script>
