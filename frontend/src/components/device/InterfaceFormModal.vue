<template>
  <Dialog
    :model-value="modelValue"
    :title="isEdit ? '编辑接口' : (formMode === 'batch' ? '批量添加接口（交换机）' : '添加接口')"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <form class="space-y-4" @submit.prevent="onSave">
      <!-- 编辑 / 单建：仅单条表单；批量模式支持多组混合端口类型 -->
      <div v-if="!isEdit" class="inline-flex rounded-md border border-border p-0.5 text-xs">
        <button type="button" class="rounded px-3 py-1 transition" :class="formMode === 'single' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'" @click="formMode = 'single'">单条</button>
        <button type="button" class="rounded px-3 py-1 transition" :class="formMode === 'batch' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'" @click="formMode = 'batch'">批量（交换机）</button>
      </div>

      <!-- 单条模式 -->
      <template v-if="formMode === 'single'">
        <FormItem name="name" label="接口名称">
          <Input v-model="form.name" placeholder="如 Gig0/1、eth0、Mgmt0/0" :class="{ 'border-destructive': errors.name }" />
        </FormItem>
        <p v-if="errors.name" class="text-xs font-medium text-destructive">{{ errors.name }}</p>

        <FormItem name="interface_no" label="前面板序号">
          <Input v-model="form.interface_no" type="number" min="0" placeholder="留空自动追加（1 基）" />
          <p class="mt-1 text-xs text-muted-foreground">用于面板排序与定位；0 或留空表示自动排到末尾。</p>
        </FormItem>

        <FormItem name="interface_type" label="接口类型">
          <Select v-model="form.interface_type">
            <SelectTrigger placeholder="选择类型" />
            <SelectContent>
              <SelectItem v-for="o in INTERFACE_TYPE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>

        <FormItem name="role" label="接口角色">
          <Select v-model="form.role">
            <SelectTrigger placeholder="选择角色" />
            <SelectContent>
              <SelectItem v-for="o in INTERFACE_ROLE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>

        <FormItem name="speed" label="速率">
          <Select v-model="form.speed">
            <SelectTrigger placeholder="选择速率" />
            <SelectContent>
              <SelectItem v-for="o in SPEED_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>

        <FormItem name="ip_address" label="IP 地址">
          <Input v-model="form.ip_address" placeholder="端口级 IP（可选，如 10.0.0.1/24）" class="font-mono" />
          <p class="mt-1 text-xs text-muted-foreground">该接口的 IP 地址（区别于设备级 IP）；可空，仅作记录用途。</p>
        </FormItem>
      </template>

      <!-- 批量模式：多组混合端口（大型交换机常含 RJ-45 + SFP + QSFP 等） -->
      <template v-else>
        <p class="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
          大型交换机常含多种端口（如 RJ-45 电口 + SFP 光口 + QSFP 光口）。逐组配置后一次性生成，各组前面板序号自动错开（如 RJ-45 占 1–48、SFP 占 49–52）。
        </p>
        <div v-for="(g, gi) in groups" :key="gi" class="batch-group">
          <div class="batch-group__head">
            <span class="batch-group__title">端口组 {{ gi + 1 }}</span>
            <Button v-if="groups.length > 1" variant="ghost" size="sm" class="text-destructive hover:text-destructive" @click="removeGroup(gi)">移除</Button>
          </div>
          <FormItem :name="`type-${gi}`" label="接口类型">
            <Select v-model="g.type">
              <SelectTrigger placeholder="选择类型" />
              <SelectContent>
                <SelectItem v-for="o in INTERFACE_TYPE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
              </SelectContent>
            </Select>
          </FormItem>
          <div class="grid grid-cols-2 gap-3">
            <FormItem :name="`count-${gi}`" label="数量">
              <Input v-model="g.count" type="number" min="1" max="128" placeholder="如 48" :class="{ 'border-destructive': errors.count }" />
            </FormItem>
            <FormItem :name="`naming-${gi}`" label="命名模板">
              <Input v-model="g.naming_pattern" placeholder="如 Gig0/%d" />
            </FormItem>
          </div>
          <p class="mt-1 text-xs text-muted-foreground">将按数量生成 <code>Gig0/1</code>、<code>Gig0/2</code> …（<code>%d</code> 自动递增）。</p>
          <div class="grid grid-cols-2 gap-3">
            <FormItem :name="`speed-${gi}`" label="速率">
              <Select v-model="g.speed">
                <SelectTrigger placeholder="选择速率" />
                <SelectContent>
                  <SelectItem v-for="o in SPEED_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
                </SelectContent>
              </Select>
            </FormItem>
            <FormItem :name="`role-${gi}`" label="角色">
              <Select v-model="g.role">
                <SelectTrigger placeholder="选择角色" />
                <SelectContent>
                  <SelectItem v-for="o in INTERFACE_ROLE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
                </SelectContent>
              </Select>
            </FormItem>
          </div>
        </div>
        <p v-if="errors.count" class="text-xs font-medium text-destructive">{{ errors.count }}</p>
        <Button variant="outline" size="sm" @click="addGroup">+ 添加端口组</Button>
      </template>
    </form>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button variant="outline" @click="close">取消</Button>
        <Button :loading="saving" @click="onSave">{{ isEdit ? '保存' : '添加' }}</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import Dialog from '@/components/ui/dialog.vue'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import FormItem from '@/components/ui/form-item.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import interfaceApi from '@/api/interface'
import { useToast } from '@/composables/useToast'
import {
  INTERFACE_TYPE_OPTIONS,
  INTERFACE_ROLE_OPTIONS,
  SPEED_OPTIONS,
} from '@/utils/constants'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  deviceId: { type: String, required: true },
  // 编辑时传入已有接口；添加时为 null。
  iface: { type: Object, default: null },
  // 设备现有接口（用于默认序号推断）。
  interfaces: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'saved'])
const { success } = useToast()

const saving = ref(false)
const isEdit = computed(() => !!props.iface)
const formMode = ref('single')

const form = reactive({ name: '', interface_no: 0, interface_type: 'rj45', role: 'data', speed: '1G', ip_address: '' })
// 批量模式：多组混合端口类型（大型交换机）。每组独立生成，序号在设备内全局唯一、自动错开。
const groups = ref([
  { type: 'rj45', count: 48, naming_pattern: 'Gig0/%d', speed: '1G', role: 'data' },
])
const errors = reactive({ name: '', count: '' })

function nextNo() {
  const nums = (props.interfaces || []).map((p) => Number(p.interface_no) || 0)
  return nums.length ? Math.max(0, ...nums) + 1 : 1
}
function addGroup() {
  groups.value.push({ type: 'sfp', count: 4, naming_pattern: 'Te0/%d', speed: '10G', role: 'data' })
}
function removeGroup(i) {
  if (groups.value.length > 1) groups.value.splice(i, 1)
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    errors.name = ''
    errors.count = ''
    formMode.value = 'single'
    if (props.iface) {
      form.name = props.iface.name
      form.interface_no = props.iface.interface_no || 0
      form.interface_type = props.iface.interface_type
      form.role = props.iface.role || 'data'
      form.speed = props.iface.speed || '1G'
      form.ip_address = props.iface.ip_address || ''
    } else {
      form.name = ''
      form.interface_no = nextNo()
      form.interface_type = 'rj45'
      form.role = 'data'
      form.speed = '1G'
      form.ip_address = ''
      groups.value = [{ type: 'rj45', count: 48, naming_pattern: 'Gig0/%d', speed: '1G', role: 'data' }]
    }
  }
)

function close() {
  emit('update:modelValue', false)
}

async function onSave() {
  errors.name = ''
  errors.count = ''
  if (formMode.value === 'batch' && !isEdit.value) {
    const payloadGroups = groups.value
      .map((g) => ({
        count: Number(g.count),
        naming_pattern: g.naming_pattern || 'Gig0/%d',
        interface_type: g.type,
        speed: g.speed,
        role: g.role,
      }))
      .filter((g) => g.count >= 1)
    if (!payloadGroups.length) {
      errors.count = '请至少配置一组有效端口（数量 ≥ 1）'
      return
    }
    const total = payloadGroups.reduce((s, g) => s + g.count, 0)
    saving.value = true
    try {
      await interfaceApi.batchCreate(props.deviceId, { groups: payloadGroups })
      success(`已批量生成 ${total} 个接口（${payloadGroups.length} 组）`)
      emit('saved')
      close()
    } catch (e) {
      // 错误信息已由响应拦截器统一提示（如前面板序号重复）。
    } finally {
      saving.value = false
    }
    return
  }

  if (!form.name.trim()) {
    errors.name = '接口名称不能为空'
    return
  }
  const payload = {
    name: form.name.trim(),
    interface_type: form.interface_type,
    role: form.role,
    speed: form.speed,
    interface_no: Number(form.interface_no) || 0,
    // 清空时显式传 null（而非 undefined），确保后端能将 ip_address 置空。
    ip_address: form.ip_address.trim() || null,
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await interfaceApi.update(props.iface.id, payload)
      success('接口已更新')
    } else {
      await interfaceApi.create(props.deviceId, payload)
      success('接口已添加')
    }
    emit('saved')
    close()
  } catch (e) {
    // 错误信息已由响应拦截器统一提示（如前面板序号重复）。
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.batch-group {
  border: 1px solid hsl(var(--border));
  border-radius: 12px;
  padding: 12px 14px;
  background: hsl(var(--muted) / 0.3);
}
.batch-group__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.batch-group__title {
  font-size: 13px;
  font-weight: 700;
  color: hsl(var(--foreground));
}
</style>
