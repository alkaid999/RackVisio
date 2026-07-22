<template>
  <!-- 弹窗开关：<Dialog> 静态常驻模板，open 由模块级单例 formState.open 驱动。
       open 由父级在「用户手势处理函数内」同步调用 openDeviceForm() 置 true（与 ConfirmDialog/useConfirm 同款机制）。
       底层 Dialog 现基于 Vue Teleport 的普通 v-if 渲染，任意嵌套层级均可稳定挂载内容。 -->
  <Dialog
    v-model="formState.open"
    :title="isEdit ? '编辑设备' : '新增设备'"
    class="max-w-2xl"
    :dismissible="false"
  >
    <!-- 滚动容器：表单较长时内部滚动，底部按钮始终可见 -->
    <div class="device-form-scroll max-h-[62vh] overflow-y-auto pr-1.5 -mr-1.5">
      <Form ref="formRef" :model="form" :rules="rules">
        <!-- 基础信息：标识类核心字段（高频，置顶） -->
        <div class="form-group">
          <div class="form-group__title">基础信息</div>
          <div class="form-grid">
            <FormItem label="设备名称" name="name" :icon="Type">
              <Input v-model="form.name" placeholder="如：Server-01" />
            </FormItem>
            <FormItem label="设备类型" name="device_type" :icon="Component">
              <Select v-model="form.device_type">
                <SelectTrigger placeholder="选择类型" />
                <SelectContent>
                  <SelectItem v-for="o in DEVICE_TYPE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
                </SelectContent>
              </Select>
            </FormItem>
            <FormItem label="设备编号" name="device_code" :icon="Hash">
              <Input v-model="form.device_code" placeholder="留空则自动生成（如 DEV-XXXXXXXX）" />
            </FormItem>
            <FormItem label="设备型号" name="model" :icon="Cpu">
              <Input v-model="form.model" placeholder="如：Dell R740" />
            </FormItem>
          </div>
        </div>

        <!-- 物理与位置：当前位置（只读）+ U 数，置于同一行 -->
        <div class="form-group">
          <div class="form-group__title">物理与位置</div>
          <div class="form-grid">
            <FormItem label="当前位置" name="current_pos" :icon="MapPin">
              <Input :model-value="currentPosLabel || '未上架（保存后可上架）'" disabled title="当前位置由机柜上架流程管理，不可直接编辑" />
              <p v-if="isMounted" class="text-xs text-amber-600 mt-1 font-medium">已上架，位置不可直接修改（如需变更请通过「上架 / 下架」操作）。</p>
            </FormItem>
            <FormItem label="设备 U 数" name="u_height" :icon="Rows3">
              <Input type="number" :min="1" :max="60" v-model="form.u_height" :disabled="isMounted" />
              <p v-if="isMounted" class="text-xs text-amber-600 mt-1 font-medium">已上架，U 数不可修改（防位置冲突）。</p>
            </FormItem>
          </div>
        </div>

        <!-- 网络与资产：联网 / 序列 / 维保 / 状态 -->
        <div class="form-group">
          <div class="form-group__title">网络与资产</div>
          <div class="form-grid">
            <FormItem label="IP 地址" name="ip_address" :icon="Globe">
              <Input v-model="form.ip_address" placeholder="如：10.0.0.1" />
            </FormItem>
            <FormItem label="序列号(SN)" name="sn" :icon="Barcode">
              <Input v-model="form.sn" placeholder="如：SN-2024-0001" />
            </FormItem>
            <FormItem label="维保到期日" name="warranty_expire" :icon="CalendarClock">
              <Input type="date" v-model="form.warranty_expire" />
            </FormItem>
            <FormItem v-if="!isMounted" label="设备状态" name="status" :icon="Signal">
              <Select v-model="form.status">
                <SelectTrigger placeholder="选择状态" />
                <SelectContent>
                  <SelectItem v-for="o in DEVICE_STATUS_EDITABLE" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
                </SelectContent>
              </Select>
            </FormItem>
            <!-- 已上架设备：开关机状态仅此处可设（在库不可修改） -->
            <FormItem v-if="isMounted" label="开关机状态" name="power_status" :icon="Power">
              <Select v-model="form.power_status">
                <SelectTrigger placeholder="选择开关机状态" />
                <SelectContent>
                  <SelectItem v-for="o in DEVICE_POWER_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
                </SelectContent>
              </Select>
            </FormItem>
          </div>
          <p v-if="!isMounted" class="form-group__hint">「已上架 / 已下架」由机柜上架、下架操作自动驱动，此处仅可标记在库 / 待报废。</p>
          <p v-if="isMounted" class="form-group__hint">在架设备的通电状态。关机以红色标识，便于在 2D 机柜视图中一眼识别停机设备。</p>
        </div>

        <!-- 备注 -->
        <div class="form-group">
          <div class="form-group__title">备注</div>
          <div class="form-grid">
            <FormItem label="备注" name="remark" :icon="StickyNote" class="form-item--full">
              <textarea
                v-model="form.remark"
                rows="2"
                placeholder="补充说明（可选）"
                class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
              ></textarea>
            </FormItem>
          </div>
        </div>

      </Form>
    </div>
    <template #footer>
      <div class="flex justify-end gap-2">
        <Button variant="outline" @click="closeForm"><CircleX class="h-4 w-4" />取消</Button>
        <Button :loading="submitting" @click="onSubmit"><Save class="h-4 w-4" />保存</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { useDeviceStore } from '@/stores/device'
import { useDeviceFormState } from '@/composables/useDeviceFormState'
import deviceApi from '@/api/device'
import { DEVICE_TYPE_OPTIONS, DEVICE_STATUS_OPTIONS, DEVICE_POWER_OPTIONS } from '@/utils/constants'
import {
  Hash,
  Type,
  Component,
  Rows3,
  Cpu,
  Barcode,
  Globe,
  CalendarClock,
  StickyNote,
  Signal,
  Power,
  CircleX,
  Save,
  MapPin,
} from 'lucide-vue-next'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Button from '@/components/ui/button.vue'

const emit = defineEmits(['update:visible', 'saved'])

const { success, error } = useToast()
const store = useDeviceStore()
// 模块级单例：open / mode / deviceId 由父级 openDeviceForm() 在用户手势内同步设置。
const formState = useDeviceFormState()
const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => formState.mode === 'edit')

// 资产状态中「已上架 / 已下架」由上下架操作驱动（与「当前位置」一致），
// 手动编辑仅允许设定 在库 / 待报废，避免与位置信息冲突 / 重复。
const DEVICE_STATUS_EDITABLE = DEVICE_STATUS_OPTIONS.filter(
  (o) => o.value === '在库' || o.value === '待报废' || o.value === '借出'
)

const emptyForm = () => ({
  device_code: '',
  name: '',
  device_type: 'server',
  u_height: 1,
  model: '',
  sn: '',
  ip_address: '',
  warranty_expire: '',
  remark: '',
  status: '在库',
  power_status: '开机',
})
const form = reactive(emptyForm())

const currentPosLabel = computed(() => {
  if (!isEdit.value) return ''
  const d = store.currentDevice
  if (!d || !d.current_rack_id) return '未上架'
  return `${d.current_rack_name || ''} / ${d.current_start_u}U`
})
// 已上架（当前有有效上架记录）设备：资产状态由位置派生，状态字段只读。
const isMounted = computed(() => isEdit.value && !!store.currentDevice?.current_rack_id)

const rules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  device_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  u_height: [{ required: true, type: 'number', min: 1, message: '设备 U 数须 ≥1', trigger: 'change' }],
}

async function loadForm() {
  Object.assign(form, emptyForm())
  formRef.value?.clearValidate?.()
  if (isEdit.value && formState.deviceId) {
    // 注意：不要用 store.fetchOne()，它会把全局 store.loading 置 true，
    // 而 DeviceDetail 模板在 loading 时渲染 Spinner 分支、会把本组件（含 <Dialog>）卸载，
    // 触发 onUnmounted 将 formState.open 复位为 false，导致弹窗无法打开。
    // 直接走 deviceApi.get 并把结果写回 store.currentDevice，避免翻转 loading。
    const d = await deviceApi.get(formState.deviceId)
    store.currentDevice = d
    if (!d) return
    form.device_code = d.device_code || ''
    form.name = d.name
    form.device_type = d.device_type
    form.u_height = d.u_height ?? 1
    form.model = d.model || ''
    form.sn = d.sn || ''
    form.ip_address = d.ip_address || ''
    form.warranty_expire = d.warranty_expire || ''
    form.remark = d.remark || ''
    form.status = d.status
    form.power_status = d.power_status || '开机'
  }
}
// 打开时加载（编辑态按 deviceId 拉取，新增态重置空表单）。
watch(
  () => formState.open,
  (v) => {
    if (v) loadForm()
  }
)
onMounted(() => {
  if (formState.open) loadForm()
})
onUnmounted(() => {
  formState.open = false
})

function closeForm() {
  formState.open = false
  emit('update:visible', false)
}

async function onSubmit() {
  const res = formRef.value.validate()
  const valid = res && typeof res.then === 'function' ? await res : !!res
  if (!valid) return
  submitting.value = true
  try {
    const payload = {
      device_code: form.device_code || undefined,
      name: form.name,
      device_type: form.device_type,
      u_height: Number(form.u_height) || 1,
      // 可选字段：清空后发送空字符串 ''（而非 undefined），后端据此把旧值清掉。
      // 注意：此前用 `|| undefined` 会把字段从请求体剔除，后端 partial-update 不更新 → 旧值残留（bug）。
      model: form.model,
      sn: form.sn,
      ip_address: form.ip_address,
      // 日期字段清空时传 null（空串 '' 不是合法日期，会被校验拒绝）。
      warranty_expire: form.warranty_expire ? form.warranty_expire : null,
      remark: form.remark,
      status: form.status,
      // 开关机状态仅在「在架」时有意义；在库设备不更新此字段（避免无意义写入）。
      power_status: isMounted.value ? form.power_status : undefined,
    }
    if (isEdit.value) {
      await store.update(formState.deviceId, payload)
      success('更新成功')
    } else {
      await store.create(payload)
      success('新增成功')
    }
    emit('saved')
    closeForm()
  } catch (e) {
    // 后端错误（含 409）已由统一拦截器提示
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
/* 分组：按逻辑关联性划分（基础信息 / 物理与位置 / 网络与资产 / 标签与备注） */
.form-group {
  margin-bottom: 18px;
}
.form-group__title {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
  padding-left: 9px;
  border-left: 3px solid hsl(var(--primary));
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: hsl(var(--muted-foreground));
}
.form-group__hint {
  margin-top: 8px;
  font-size: 12px;
  color: hsl(var(--muted-foreground));
  line-height: 1.5;
}
/* 每行两个字段；窄屏退化为单列 */
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
}
/* 备注等多行字段跨整行 */
.form-item--full {
  grid-column: 1 / -1;
}
@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
