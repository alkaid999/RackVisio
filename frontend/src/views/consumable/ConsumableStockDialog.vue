<template>
  <Dialog
    :model-value="visible"
    :title="`库存变动 — ${item ? item.name : ''}`"
    class="max-w-lg"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <div v-if="item" class="mb-4 flex items-center justify-between rounded-lg bg-muted px-3 py-2">
      <span class="text-sm text-muted-foreground">当前结存</span>
      <span class="text-lg font-bold text-foreground">
        {{ item.current_quantity }} <span class="text-sm font-normal text-muted-foreground">{{ item.unit || '个' }}</span>
      </span>
    </div>

    <Form ref="formRef" :model="form" :rules="rules">
      <FormItem name="operation_type" label="操作类型">
        <Select v-model="form.operation_type" class="w-full" @update:model-value="onOpChange">
          <SelectTrigger placeholder="选择操作类型" />
          <SelectContent>
            <SelectItem v-for="o in CONSUMABLE_OP_OPTIONS" :key="o.value" :value="o.value">
              <span class="inline-flex items-center gap-2">
                <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: CONSUMABLE_OP_COLORS[o.value] }"></span>
                {{ o.label }}
              </span>
            </SelectItem>
          </SelectContent>
        </Select>
      </FormItem>
      <FormItem name="quantity" :label="opHint">
        <Input v-model="form.quantity" type="number" :placeholder="opHint" />
      </FormItem>
      <FormItem label="操作时间" name="operation_time">
        <input
          v-model="form.operation_time"
          type="datetime-local"
          class="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
        />
        <p class="mt-1 text-xs text-muted-foreground">留空则使用当前时间（可用于补录历史单据）。</p>
      </FormItem>
      <FormItem label="原因 / 备注" name="reason">
        <textarea
          v-model="form.reason"
          rows="2"
          placeholder="如：某项目组领用 / 采购到货 / 端口损坏报废（可选）"
          class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
        ></textarea>
      </FormItem>
    </Form>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button variant="outline" @click="emit('update:visible', false)">取消</Button>
        <Button :loading="submitting" @click="onSubmit">提交</Button>
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
import { CONSUMABLE_OP_OPTIONS, CONSUMABLE_OP_COLORS, consumableOpQuantityHint } from '@/utils/constants'

const props = defineProps({
  visible: { type: Boolean, default: false },
  item: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'saved'])

const { success } = useToast()
const store = useConsumableStore()
const formRef = ref(null)
const submitting = ref(false)

const opHint = computed(() => consumableOpQuantityHint(form.operation_type))

const emptyForm = () => ({
  operation_type: '入库',
  quantity: 1,
  operation_time: '',
  reason: '',
})
const form = reactive(emptyForm())

const rules = {
  operation_type: [{ required: true, message: '请选择操作类型', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}

// 切换操作类型时，按语义重置数量默认值：盘点点位为当前结存，其余为 1。
function onOpChange() {
  form.quantity = form.operation_type === '盘点' && props.item ? props.item.current_quantity : 1
}

watch(
  () => props.visible,
  (v) => {
    if (!v) return
    Object.assign(form, emptyForm())
    if (props.item) form.quantity = 1
    formRef.value?.clearValidate?.()
  },
  { immediate: false }
)

async function onSubmit() {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const qty = Number(form.quantity)
      const payload = {
        operation_type: form.operation_type,
        quantity: qty,
        reason: form.reason || undefined,
      }
      // 操作时间：datetime-local 字符串原样提交（后端按 aware datetime 解析）；留空则不传。
      if (form.operation_time) payload.operation_time = form.operation_time
      await store.adjustStock(props.item.id, payload)
      success('库存变动已记录')
      emit('saved')
      emit('update:visible', false)
    } catch (e) {
      // 库存不足 / 参数校验等错误已由统一拦截器提示
    } finally {
      submitting.value = false
    }
  })
}
</script>
