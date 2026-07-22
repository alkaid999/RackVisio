<template>
  <Dialog
    :model-value="visible"
    :title="isEdit ? '编辑机柜' : '新增机柜'"
    class="max-w-2xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <Form ref="formRef" :model="form" :rules="rules">
      <FormItem label="所属机房" name="room_id" :icon="Building2">
        <Select
          v-model="form.room_id"
          placeholder="选择机房"
          :disabled="!!lockedRoomId || isEdit"
          @update:model-value="onRoomChange"
        >
          <SelectTrigger placeholder="选择机房" />
          <SelectContent>
            <SelectItem v-for="r in roomOptions" :key="r.id" :value="r.id">{{ r.name }}（{{ r.code }}）</SelectItem>
          </SelectContent>
        </Select>
      </FormItem>

      <div class="grid grid-cols-2 gap-4">
        <FormItem label="列编号" name="column_code" :icon="Columns3">
          <Input v-model="form.column_code" placeholder="如：A1、B2（同一机房内唯一）" />
        </FormItem>
        <FormItem label="机柜编号" name="code" :icon="Tag">
          <Input v-model="form.code" placeholder="如：01、02（同列内唯一）" />
        </FormItem>
      </div>

      <FormItem label="名称" name="name" :icon="Type">
        <Input v-model="form.name" placeholder="留空则自动生成（列编号-机柜编号）" />
      </FormItem>

      <div class="grid grid-cols-2 gap-4">
        <FormItem label="机柜 U 数" name="total_u" :icon="Ruler">
          <Input type="number" :min="1" :max="60" v-model="form.total_u" :disabled="isEdit" :title="isEdit ? '机柜创建后 U 数不可修改' : ''" />
        </FormItem>
        <FormItem label="机柜状态" name="status" :icon="CircleDot">
          <Select v-model="form.status">
            <SelectTrigger placeholder="选择状态" />
            <SelectContent>
              <SelectItem v-for="o in RACK_STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>
      </div>

      <FormItem label="机柜分组" name="rack_group" :icon="Users">
        <Input v-model="form.rack_group" placeholder="如：某项目组 / 某公司 / 某部门（选填）" />
      </FormItem>
    </Form>
    <template #footer>
      <div class="flex justify-end gap-2">
        <Button variant="outline" @click="emit('update:visible', false)"><CircleX class="h-4 w-4" />取消</Button>
        <Button :loading="submitting" @click="onSubmit"><Save class="h-4 w-4" />保存</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { useRackStore } from '@/stores/rack'
import { useRoomStore } from '@/stores/room'
import roomApi from '@/api/room'
import rackApi from '@/api/rack'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Button from '@/components/ui/button.vue'
import { Building2, Columns3, Tag, Type, Ruler, CircleDot, Users, CircleX, Save } from 'lucide-vue-next'
import { RACK_STATUS_OPTIONS } from '@/utils/constants'

const props = defineProps({
  visible: { type: Boolean, default: false },
  mode: { type: String, default: 'create' }, // 'create' | 'edit'
  rackId: { type: [String, Number], default: '' },
  lockedRoomId: { type: [String, Number], default: '' },
})
const emit = defineEmits(['update:visible', 'saved'])

const { success, error } = useToast()
const store = useRackStore()
const roomStore = useRoomStore()
const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => props.mode === 'edit')

const roomOptions = computed(() => roomStore.rooms)

const emptyForm = () => ({
  room_id: props.lockedRoomId || '',
  column_code: '',
  code: '',
  name: '',
  total_u: 42,
  rack_group: '',
  status: '可用',
})
const form = reactive(emptyForm())

const rules = {
  room_id: [{ required: true, message: '请选择所属机房', trigger: 'change' }],
  column_code: [{ required: true, message: '请输入列编号', trigger: 'blur' }],
  code: [{ required: true, message: '请输入机柜编号', trigger: 'blur' }],
  total_u: [{ required: true, type: 'number', min: 1, max: 60, message: 'U 数须为 1-60', trigger: 'change' }],
}

function onRoomChange() {
  formRef.value?.clearValidate?.('room_id')
}

watch(
  [() => props.visible, () => props.rackId, () => props.mode],
  async ([v]) => {
    if (!v) return
    Object.assign(form, emptyForm())
    formRef.value?.clearValidate?.()
    await roomStore.fetchList({ page: 1, size: 200 })
    if (isEdit.value && props.rackId) {
      await store.fetchOne(props.rackId)
      const r = store.currentRack
      if (r) {
        Object.assign(form, {
          room_id: r.room_id,
          column_code: r.column_code,
          code: r.code,
          name: r.name,
          total_u: r.total_u,
          rack_group: r.rack_group || '',
          status: r.status || '可用',
        })
      }
    }
  },
  { immediate: false, flush: 'post' }
)

async function onSubmit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        name: form.name || undefined,
        column_code: form.column_code,
        code: form.code,
        total_u: Number(form.total_u),
        rack_group: form.rack_group || undefined,
        status: form.status,
      }
      if (isEdit.value) {
        await store.update(props.rackId, payload)
        success('更新成功')
      } else if (props.lockedRoomId) {
        await roomApi.createRack(props.lockedRoomId, payload)
        success('创建成功')
      } else {
        await rackApi.create({ ...payload, room_id: form.room_id })
        success('创建成功')
      }
      emit('saved')
      emit('update:visible', false)
    } catch (e) {
      // 唯一约束 / 校验错误已由统一拦截器提示
    } finally {
      submitting.value = false
    }
  })
}
</script>
