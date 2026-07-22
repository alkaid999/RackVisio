<template>
  <Dialog :model-value="visible" :title="isEdit ? '编辑机房' : '新建机房'" class="max-w-2xl" @update:model-value="(v) => emit('update:visible', v)">
    <Form ref="formRef" :model="form" :rules="rules">
      <FormItem name="name" label="名称">
        <Input v-model="form.name" placeholder="如：某数据中心" />
      </FormItem>
      <FormItem name="code" label="编号">
        <Input v-model="form.code" placeholder="如：DC-01（仅数字/字母/_/-，全局唯一）" />
      </FormItem>
      <FormItem name="alias" label="别名">
        <Input v-model="form.alias" placeholder="如：核心机房A（选填）" />
      </FormItem>
      <div class="grid grid-cols-2 gap-4">
        <FormItem name="area" label="所属区域">
          <Input v-model="form.area" placeholder="如：华南（选填）" />
        </FormItem>
        <FormItem name="building" label="所属楼宇">
          <Input v-model="form.building" placeholder="如：T2（选填）" />
        </FormItem>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <FormItem name="floor" label="所在楼层">
          <Input v-model="form.floor" placeholder="如：5F（选填）" />
        </FormItem>
        <FormItem name="address" label="机房地址">
          <Input v-model="form.address" placeholder="详细街道地址（选填）" />
        </FormItem>
      </div>
      <FormItem name="status" label="状态">
        <Select v-model="form.status" class="w-40">
          <SelectTrigger placeholder="选择状态" />
          <SelectContent>
            <SelectItem v-for="o in ROOM_STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
          </SelectContent>
        </Select>
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
import { useRoomStore } from '@/stores/room'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'
import Button from '@/components/ui/button.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import { ROOM_STATUS_OPTIONS } from '@/utils/constants'

const props = defineProps({
  visible: { type: Boolean, default: false },
  mode: { type: String, default: 'create' }, // 'create' | 'edit'
  roomId: { type: [String, Number], default: '' },
})
const emit = defineEmits(['update:visible', 'saved'])

const { success } = useToast()
const store = useRoomStore()
const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => props.mode === 'edit')

const emptyForm = () => ({
  name: '',
  code: '',
  alias: '',
  area: '',
  building: '',
  floor: '',
  address: '',
  status: 'active',
})
const form = reactive(emptyForm())

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [
    { required: true, message: '请输入编号', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9_-]+$/,
      message: '编号仅允许数字、字母、下划线或连字符',
      trigger: 'blur',
    },
  ],
}

watch(
  () => props.visible,
  async (v) => {
    if (!v) return
    Object.assign(form, emptyForm())
    formRef.value?.clearValidate?.()
    if (isEdit.value && props.roomId) {
      await store.fetchOne(props.roomId)
      const r = store.currentRoom
      if (r) {
        Object.assign(form, {
          name: r.name,
          code: r.code,
          alias: r.alias || '',
          area: r.area || '',
          building: r.building || '',
          floor: r.floor || '',
          address: r.address || '',
          status: r.status || 'active',
        })
      }
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
        name: form.name,
        code: form.code,
        alias: form.alias || undefined,
        area: form.area || undefined,
        building: form.building || undefined,
        floor: form.floor || undefined,
        address: form.address || undefined,
        status: isEdit.value ? form.status || 'active' : undefined,
      }
      if (isEdit.value) {
        await store.update(props.roomId, payload)
        success('更新成功')
      } else {
        await store.create(payload)
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
