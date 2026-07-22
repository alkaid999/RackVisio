<template>
  <Dialog
    :model-value="visible"
    :title="readonly ? '查看链路' : (isEdit ? '编辑链路' : '新建链路')"
    class="max-w-3xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <Form ref="formRef" :model="form" :rules="rules">
      <!-- 编辑模式：本端/对端端点信息卡（富图标，只读展示；本端朝向为当前操作设备） -->
      <template v-if="isEdit">
        <div class="link-endpoints">
          <div class="endpoint endpoint--source">
            <span class="endpoint__badge">本端</span>
            <div class="endpoint__info">
              <div class="endpoint__device">{{ editEndpoints.source?.device_name }}</div>
              <div class="endpoint__iface">
                <Cable class="h-3.5 w-3.5" />{{ editEndpoints.source?.interface_name }}
              </div>
            </div>
          </div>

          <div class="endpoint__flow">
            <span class="endpoint__flow-line" />
            <ArrowRight class="endpoint__flow-arrow" />
            <span class="endpoint__flow-line" />
          </div>

          <div class="endpoint endpoint--target">
            <span class="endpoint__badge endpoint__badge--target">对端</span>
            <div class="endpoint__info">
              <div class="endpoint__device">
                <template v-if="!editEndpoints.target?.isExternal">{{ editEndpoints.target?.device_name }}</template>
                <template v-else><ExternalLink class="inline h-3.5 w-3.5" />{{ editEndpoints.target?.external }}</template>
              </div>
              <div class="endpoint__iface">
                <Cable class="h-3.5 w-3.5" />
                <template v-if="!editEndpoints.target?.isExternal">{{ editEndpoints.target?.interface_name }}</template>
                <template v-else>外部位置</template>
              </div>
            </div>
          </div>
        </div>

        <div class="link-edit-divider">
          <span class="link-edit-divider__label"><Pencil class="h-3.5 w-3.5" />链路属性（可修改）</span>
        </div>
      </template>

      <!-- 新建模式：左右两栏分别展示本端 / 对端，清晰区分两端 -->
      <template v-else>
        <!-- 链路资格门控（详细引导统一在「链路管理」二级菜单）：此处仅简洁拦截 -->
        <div
          v-if="linkBlocked"
          class="mb-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700"
        >
          <p class="font-medium">无法创建链路</p>
          <p class="mt-1">本端设备当前不满足建链条件（需已上架机柜且含有接口）。请先在「设备管理」完成前置步骤。</p>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <!-- 左栏：本端（源设备与接口） -->
          <div class="rounded-xl border border-border bg-muted/20 p-3">
            <div class="mb-3 flex items-center gap-2 text-sm font-semibold">
              <span class="end-badge end-badge--source">本端</span>
              <span>源设备与接口</span>
            </div>
            <FormItem label="本端设备" name="sourceDeviceId">
              <DevicePicker
                v-model="form.sourceDeviceId"
                :devices="allDevices"
                :selectable-reason="sourceDeviceReason"
                placeholder="搜索并选择本端设备"
                :disabled="!!sourceInterface || readonly"
                @select="onSourceDeviceChange"
              />
            </FormItem>
            <FormItem label="本端接口" name="source_interface_id">
              <Select v-model="form.source_interface_id" placeholder="选择接口" :disabled="!!sourceInterface || readonly">
                <SelectTrigger placeholder="选择接口" />
                <SelectContent>
                  <SelectItem
                    v-for="p in sourcePorts"
                    :key="p.id"
                    :value="p.id"
                    :disabled="!!occupiedOf(p)"
                    :title="occupiedTip(p)"
                  >
                    <span class="inline-flex flex-wrap items-center gap-x-1">
                      {{ p.name }}（{{ INTERFACE_TYPE_LABELS[p.interface_type] }}/{{ p.speed }}）
                      <span v-if="occupiedOf(p)" class="text-[11px] font-medium text-destructive/80">· 已占用</span>
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
              <p v-if="sourceInterface" class="text-xs text-muted-foreground">
                已锁定为当前接口（{{ sourceInterface.name }}），不可更改。
              </p>
            </FormItem>
          </div>

          <!-- 右栏：对端（目标设备与接口 / 外部位置） -->
          <div class="rounded-xl border border-border bg-muted/20 p-3">
            <div class="mb-3 flex items-center gap-2 text-sm font-semibold">
              <span class="end-badge end-badge--target">对端</span>
              <span>目标设备与接口</span>
            </div>
            <FormItem label="对端类型" name="targetKind">
              <Select v-model="form.targetKind" :disabled="readonly" @update:model-value="onTargetKindChange">
                <SelectTrigger placeholder="选择对端类型" />
                <SelectContent>
                  <SelectItem value="system">系统内设备接口</SelectItem>
                  <SelectItem value="external">外部（未纳管，如运营商 ODF）</SelectItem>
                </SelectContent>
              </Select>
            </FormItem>

            <template v-if="form.targetKind === 'system'">
              <FormItem label="对端设备" name="targetDeviceId">
              <DevicePicker
                v-model="form.targetDeviceId"
                :devices="targetDeviceCandidates"
                :selectable-reason="targetDeviceReason"
                placeholder="搜索并选择对端设备"
                :disabled="readonly"
                @select="onTargetDeviceChange"
              />
              </FormItem>
              <FormItem label="对端接口" name="target_interface_id">
                <Select v-model="form.target_interface_id" placeholder="选择接口" :disabled="!form.targetDeviceId || readonly">
                  <SelectTrigger placeholder="选择接口" />
                  <SelectContent>
                    <SelectItem
                      v-for="p in targetPorts"
                      :key="p.id"
                      :value="p.id"
                      :disabled="!!occupiedOf(p)"
                      :title="occupiedTip(p)"
                    >
                      <span class="inline-flex flex-wrap items-center gap-x-1">
                        {{ p.name }}（{{ INTERFACE_TYPE_LABELS[p.interface_type] }}/{{ p.speed }}）
                        <span v-if="occupiedOf(p)" class="text-[11px] font-medium text-destructive/80">· 已占用</span>
                      </span>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FormItem>
            </template>
            <template v-else>
              <FormItem label="对端外部位置" name="target_external">
                <Input v-model="form.target_external" placeholder="如 运营商 ODF-3、上级核心交换机" />
                <p class="mt-1 text-xs text-muted-foreground">对端不在本系统内时填写自由文本；半链路下仅本端自动置「已连线」。</p>
              </FormItem>
            </template>
          </div>
        </div>
      </template>

      <FormItem label="连接介质" name="medium">
        <Select v-model="form.medium" :disabled="readonly">
          <SelectTrigger placeholder="选择连接介质" />
          <SelectContent>
            <SelectItem v-for="o in mediumOptions" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
          </SelectContent>
        </Select>
      </FormItem>
      <FormItem label="连接器类型" name="connector_type">
        <Select v-model="form.connector_type" :disabled="readonly">
          <SelectTrigger :placeholder="connectorPlaceholder" />
          <SelectContent>
            <SelectItem v-for="o in connectorOptions" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
          </SelectContent>
        </Select>
        <p v-if="connectorDesc" class="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
          <Info class="h-3.5 w-3.5" />{{ connectorDesc }}
        </p>
        <p v-else-if="form.medium === 'tp'" class="mt-1 text-xs text-muted-foreground">
          双绞线需选择线缆类别（RJ-45 为统一物理插头，不单独记录）。
        </p>
        <p v-else-if="!connectorOptions.length" class="mt-1 text-xs text-muted-foreground">
          当前连接介质无可选连接器。
        </p>
      </FormItem>
      <FormItem label="线缆长度" name="cable_length">
        <Input v-model="form.cable_length" :disabled="readonly" placeholder="如 5m / 10m / 3m" />
      </FormItem>
      <FormItem label="备注" name="remark">
        <Input v-model="form.remark" :disabled="readonly" placeholder="备注信息（可选，如用途、责任人、工单号）" />
      </FormItem>

      <div
        v-if="conflictHint"
        class="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
      >
        {{ conflictHint }}
      </div>
    </Form>
    <template #footer>
      <div class="flex justify-end gap-2">
        <Button variant="outline" @click="emit('update:visible', false)">{{ readonly ? '关闭' : '取消' }}</Button>
        <Button v-if="!readonly" :loading="submitting" :disabled="linkBlocked" @click="onSubmit">保存</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import deviceApi from '@/api/device'
import interfaceApi from '@/api/interface'
import linkApi from '@/api/link'
import {
  LINK_MEDIUM_OPTIONS,
  LINK_MEDIUM_LABELS,
  CONNECTOR_TYPE_LABELS,
  CONNECTOR_TYPE_DESC,
  connectorTypeOptionsFor,
  INTERFACE_TYPE_LABELS,
} from '@/utils/constants'
import { ExternalLink, ArrowRight, Cable, Info, Pencil } from 'lucide-vue-next'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Button from '@/components/ui/button.vue'
import DevicePicker from '@/components/device/DevicePicker.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  mode: { type: String, default: 'create' }, // 'create' | 'edit'
  // 查看模式：只读展示已有链路，禁用全部输入并隐藏保存。
  viewMode: { type: Boolean, default: false },
  linkId: { type: String, default: '' },
  link: { type: Object, default: () => null }, // LinkDetailOut（编辑时预填）
  // 建链流程：预置本端接口（含 device_id），创建时锁定本端。
  sourceInterface: { type: Object, default: null },
  // 编辑时传入的「当前操作设备」：从该设备视角进入编辑，则该设备自动作为本端，另一端为对端（仅影响展示朝向，不改写链路两端）。
  contextDeviceId: { type: String, default: '' },
})
const emit = defineEmits(['update:visible', 'saved'])

const { success, error } = useToast()

const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => props.mode === 'edit')
// 查看模式：只读展示已有链路，禁用全部输入并隐藏保存按钮。
const readonly = computed(() => !!props.viewMode)

const deviceOptions = ref([])
const allDevices = ref([]) // 全量设备（供 DevicePicker 客户端搜索/筛选）
const sourcePorts = ref([])
const targetPorts = ref([])
const existingLinks = ref([]) // 用于接口占用判定（含 link id）
// 本端设备所属机房：选定后用于限制对端仅可选同机房设备（禁止跨机房互联）。
const sourceRoomId = ref('')

// 链路资格：设备必须已上架机柜（current_rack_id 非空）且至少含 1 个接口。
function isEligibleDevice(d) {
  return !!d.current_rack_id && (d.interface_count || 0) > 0
}

// 不可建链「具体原因」：供 DevicePicker 红字直接展示，比笼统「不可用于建链」更可读。
function sourceDeviceReason(d) {
  if (!d.current_rack_id) return '未上架'
  if ((d.interface_count || 0) <= 0) return '无可用接口'
  return ''
}
// 对端原因：在「已上架且含接口」基础上，叠加「不能选自身」与同机房约束。
function targetDeviceReason(d) {
  if (form.sourceDeviceId && d.id === form.sourceDeviceId) return '不能选择自身'
  if (!d.current_rack_id) return '未上架'
  if ((d.interface_count || 0) <= 0) return '无可用接口'
  if (sourceRoomId.value && d.current_room_id !== sourceRoomId.value) return '不在同一机房'
  return ''
}

// 已占用接口映射：interfaceId -> 占用它的链路记录（含 id）。
const occupiedMap = computed(() => {
  const m = {}
  for (const l of existingLinks.value) {
    if (l.source_interface_id) m[l.source_interface_id] = l
    if (l.target_interface_id) m[l.target_interface_id] = l
  }
  return m
})
function occupiedOf(p) {
  if (!p || !p.id) return null
  return occupiedMap.value[p.id] || null
}
function occupiedTip(p) {
  const l = occupiedOf(p)
  if (!l) return undefined
  return `该接口已被链路 ${l.id} 占用，需先删除该链路才能重新选择`
}

const emptyForm = () => ({
  sourceDeviceId: '',
  source_interface_id: '',
  targetKind: 'system',
  targetDeviceId: '',
  target_interface_id: '',
  target_external: '',
  remark: '',
  medium: 'tp',
  connector_type: '', // 双绞线/光纤均需在保存前选择连接器类型
  cable_length: '',
})
const form = reactive(emptyForm())

// 建链流程预置本端时，本端设备/接口为系统锁定值，不再要求「必填」校验，
// 避免保存时误报「请选择本端设备」，正确反映已默认选中的状态。
const sourceLocked = computed(() => !isEdit.value && !!props.sourceInterface)
const rules = computed(() => ({
  sourceDeviceId: !sourceLocked.value ? [{ required: true, message: '请选择本端设备', trigger: 'change' }] : [],
  source_interface_id: !sourceLocked.value ? [{ required: true, message: '请选择本端接口', trigger: 'change' }] : [],
  target_interface_id:
    !isEdit.value && form.targetKind === 'system'
      ? [{ required: true, message: '请选择对端接口', trigger: 'change' }]
      : [],
  target_external:
    !isEdit.value && form.targetKind === 'external'
      ? [{ required: true, message: '请填写对端外部位置', trigger: 'blur' }]
      : [],
  medium: [{ required: true, message: '请选择连接介质', trigger: 'change' }],
  // 双绞线(tp)与光纤(smf/mmf)的连接器类型均为必选。
  connector_type: [{ required: true, message: '请选择连接器类型', trigger: 'change' }],
}))

// 连接介质：编辑模式下若存储值为历史介质（已不在可选列表），保留该项以便正常回显。
const mediumOptions = computed(() => {
  let opts = LINK_MEDIUM_OPTIONS
  if (isEdit.value && form.medium && !opts.some((o) => o.value === form.medium)) {
    opts = [...opts, { value: form.medium, label: LINK_MEDIUM_LABELS[form.medium] || form.medium }]
  }
  return opts
})

// 连接器类型按连接介质动态联动：双绞线固定 rj45；光纤可选光纤连接器。
const connectorOptions = computed(() => {
  let opts = connectorTypeOptionsFor(form.medium)
  // 编辑模式：保留历史连接器值以便正确回显（可能为旧类型，如 lc-sc）。
  if (isEdit.value && form.connector_type && !opts.some((o) => o.value === form.connector_type)) {
    opts = [...opts, { value: form.connector_type, label: CONNECTOR_TYPE_LABELS[form.connector_type] || form.connector_type }]
  }
  return opts
})
const connectorPlaceholder = computed(() => {
  if (form.medium === 'tp') return '选择双绞线类别'
  if (form.medium === 'smf' || form.medium === 'mmf') return '选择光纤连接器'
  return '选择连接器类型'
})
// 选中连接器类型的补充说明（帮助用户理解所选类别含义）。
const connectorDesc = computed(() => {
  if (!form.connector_type) return ''
  return CONNECTOR_TYPE_DESC[form.connector_type] || ''
})

// 编辑模式端点朝向：若从某设备视角进入（contextDeviceId 命中对端设备），则把该设备作为「本端」，
// 链路另一端作为「对端」。这样从任意一端查看链路，本端都自动对应当前操作设备，而非写死为链路的存储 source。
// 仅影响展示朝向，不改动链路实际连接拓扑（source/target 仍按存储值，编辑时不可改两端）。
const editEndpoints = computed(() => {
  const l = props.link
  if (!l) return { source: null, target: null, fromTarget: false }
  const fromTarget = !!(props.contextDeviceId && props.contextDeviceId === l.target_device_id)
  const source = fromTarget
    ? { device_id: l.target_device_id, device_name: l.target_device_name, interface_name: l.target_interface_name, isExternal: false }
    : { device_id: l.source_device_id, device_name: l.source_device_name, interface_name: l.source_interface_name, isExternal: false }
  const target = fromTarget
    ? { device_id: l.source_device_id, device_name: l.source_device_name, interface_name: l.source_interface_name, isExternal: false }
    : {
        device_id: l.target_device_id,
        device_name: l.target_device_name,
        interface_name: l.target_interface_name,
        isExternal: !l.target_interface_id,
        external: l.target_external || '外部',
      }
  return { source, target, fromTarget }
})

// 切换连接介质时联动连接器：若当前连接器不在新介质的可选列表内则清空，需重选。
watch(
  () => form.medium,
  () => {
    const opts = connectorTypeOptionsFor(form.medium)
    if (!opts.some((o) => o.value === form.connector_type)) form.connector_type = ''
  }
)

const conflictHint = computed(() => {
  if (isEdit.value) return ''
  if (form.source_interface_id && form.target_interface_id && form.source_interface_id === form.target_interface_id)
    return '本端接口与对端接口不能相同'
  const occSrc = occupiedOf({ id: form.source_interface_id })
  if (form.source_interface_id && occSrc) return `本端接口已被链路 ${occSrc.id} 占用，请先删除该链路`
  if (form.targetKind === 'system' && form.target_interface_id) {
    const occTgt = occupiedOf({ id: form.target_interface_id })
    if (occTgt) return `对端接口已被链路 ${occTgt.id} 占用，请先删除该链路`
  }
  return ''
})

// 链路创建被门控：编辑模式不拦截；新建模式需存在可用（已上架+含接口）设备。
// 建链流程预置本端时，若该本端设备未上架或无接口同样拦截。
const linkBlocked = computed(() => {
  if (isEdit.value) return false
  if (props.sourceInterface) {
    return !deviceOptions.value.some((d) => d.id === props.sourceInterface.device_id)
  }
  return deviceOptions.value.length === 0
})

async function onSourceDeviceChange(device) {
  form.source_interface_id = ''
  const id = device && device.id ? device.id : device
  const picked = allDevices.value.find((d) => d.id === id)
  sourceRoomId.value = picked ? picked.current_room_id || '' : ''
  // 源设备变更后，若已选对端不在同一机房则清空，避免跨机房选项残留。
  if (form.targetDeviceId && sourceRoomId.value) {
    const tgt = allDevices.value.find((d) => d.id === form.targetDeviceId)
    if (!tgt || tgt.current_room_id !== sourceRoomId.value) {
      form.targetDeviceId = ''
      form.target_interface_id = ''
      targetPorts.value = []
    }
  }
  if (id) sourcePorts.value = await interfaceApi.list(id)
  // 选中后立即清除「请选择本端设备」的过时校验（focusout 在值写入前已触发一次）。
  formRef.value?.validateField?.('sourceDeviceId')
}
async function onTargetDeviceChange(device) {
  form.target_interface_id = ''
  const id = device && device.id ? device.id : device
  if (id) targetPorts.value = await interfaceApi.list(id)
  formRef.value?.validateField?.('targetDeviceId')
}
function onTargetKindChange(kind) {
  if (kind === 'external') {
    form.targetDeviceId = ''
    form.target_interface_id = ''
  } else {
    form.target_external = ''
  }
}
// 对端候选：源设备选定后，仅展示与源设备同机房的设备，禁止跨机房互联。
const targetDeviceCandidates = computed(() => {
  if (!sourceRoomId.value) return allDevices.value
  return allDevices.value.filter((d) => d.current_room_id === sourceRoomId.value)
})

watch(
  () => props.visible,
  async (v) => {
    if (!v) return
    Object.assign(form, emptyForm())
    formRef.value?.clearValidate?.()
    await loadDevices()
    if (props.sourceInterface) {
      // 建链流程：预置并锁定本端。
      form.sourceDeviceId = props.sourceInterface.device_id
      form.source_interface_id = props.sourceInterface.id
      sourcePorts.value = await interfaceApi.list(props.sourceInterface.device_id)
      const src = allDevices.value.find((d) => d.id === props.sourceInterface.device_id)
      sourceRoomId.value = src ? src.current_room_id || '' : ''
    }
    if (isEdit.value && props.link) {
      const l = props.link
      // 朝向：若从某设备视角进入且命中对端，则翻转本端/对端，使本端对应当前操作设备。
      const fromTarget = !!(props.contextDeviceId && props.contextDeviceId === l.target_device_id)
      const srcEnd = fromTarget
        ? { device_id: l.target_device_id, interface_id: l.target_interface_id }
        : { device_id: l.source_device_id, interface_id: l.source_interface_id }
      const tgtEnd = fromTarget
        ? { device_id: l.source_device_id, interface_id: l.source_interface_id }
        : { device_id: l.target_device_id, interface_id: l.target_interface_id, external: l.target_external }
      form.sourceDeviceId = srcEnd.device_id
      form.source_interface_id = srcEnd.interface_id
      sourcePorts.value = srcEnd.interface_id ? await interfaceApi.list(srcEnd.device_id) : []
      if (tgtEnd.interface_id) {
        form.targetKind = 'system'
        form.targetDeviceId = tgtEnd.device_id
        form.target_interface_id = tgtEnd.interface_id
        targetPorts.value = await interfaceApi.list(tgtEnd.device_id)
      } else {
        form.targetKind = 'external'
        form.target_external = tgtEnd.external || ''
      }
      form.remark = l.remark || ''
      form.medium = l.medium || 'tp'
      // 连接器类型回填（双绞线与光纤均为可选类别，直接沿用已存值，无则留空待选）。
      form.connector_type = l.connector_type || ''
      form.cable_length = l.cable_length || ''
    }
  },
  { immediate: false }
)

async function loadDevices() {
  const data = await deviceApi.list({ page: 1, size: 1000 })
  allDevices.value = data.items || []
  // 仅「已上架且含接口」的设备可参与建链（用于门控判定与选择器灰显）。
  deviceOptions.value = allDevices.value.filter(isEligibleDevice)
  // 接口占用判定：失败不应阻断设备加载与（预置）本端选择。
  try {
    const links = await linkApi.list({ page: 1, size: 1000 })
    existingLinks.value = links.items || []
  } catch (e) {
    existingLinks.value = []
  }
}

async function onSubmit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (!isEdit.value) {
        if (form.source_interface_id === form.target_interface_id) {
          error('本端接口与对端接口不能相同')
          return
        }
        const payload = {
          source_interface_id: form.source_interface_id,
          remark: form.remark || undefined,
          medium: form.medium,
          connector_type: form.connector_type || undefined,
          cable_length: form.cable_length || undefined,
        }
        if (form.targetKind === 'system') {
          payload.target_interface_id = form.target_interface_id
        } else {
          payload.target_external = form.target_external
        }
        await linkApi.create(payload)
        success('链路创建成功')
      } else {
        await linkApi.update(props.linkId, {
          remark: form.remark || undefined,
          medium: form.medium,
          connector_type: form.connector_type || undefined,
          cable_length: form.cable_length || undefined,
        })
        success('链路更新成功')
      }
      emit('saved')
      emit('update:visible', false)
    } catch (e) {
      // 后端 409 等已由统一拦截器提示
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
/* 编辑模式分隔：端点卡与可编辑属性之间 */
.link-edit-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 4px 0 18px;
  color: hsl(var(--muted-foreground));
}
.link-edit-divider::before,
.link-edit-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: hsl(var(--border));
}
.link-edit-divider__label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

/* 两端徽标：本端（蓝）/ 对端（紫），清晰区分两端 */
.end-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  padding: 1px 8px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
}
.end-badge--source {
  background: rgba(37, 99, 235, 0.12);
  color: #2563eb;
}
.end-badge--target {
  background: rgba(139, 92, 246, 0.14);
  color: #7c3aed;
}

/* 编辑模式：本端→对端 端点信息卡（富图标、现代视觉层次） */
.link-endpoints {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: stretch;
  gap: 10px;
  margin-bottom: 18px;
}
.endpoint {
  position: relative;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: 14px;
  border: 1px solid hsl(var(--border));
  background: linear-gradient(180deg, hsl(var(--card)), hsl(var(--muted) / 0.5));
  box-shadow: inset 0 1px 0 hsl(var(--foreground) / 0.03);
}
.endpoint--source {
  border-left: 3px solid #2563eb;
}
.endpoint--target {
  border-left: 3px solid #7c3aed;
}
.endpoint__badge {
  flex: none;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  padding: 3px 9px;
  border-radius: 9999px;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
}
.endpoint__badge--target {
  color: #7c3aed;
  background: rgba(139, 92, 246, 0.14);
}
.endpoint__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.endpoint__device {
  font-size: 14px;
  font-weight: 700;
  color: hsl(var(--foreground));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.endpoint__iface {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: hsl(var(--muted-foreground));
}
.endpoint__flow {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 2px;
}
.endpoint__flow-line {
  flex: 1;
  height: 2px;
  min-width: 14px;
  border-radius: 9999px;
  background: linear-gradient(90deg, #2563eb, #7c3aed);
  opacity: 0.5;
}
.endpoint__flow-arrow {
  flex: none;
  width: 18px;
  height: 18px;
  color: hsl(var(--muted-foreground));
}
@media (max-width: 560px) {
  .link-endpoints {
    grid-template-columns: 1fr;
  }
  .endpoint__flow {
    flex-direction: row;
    transform: rotate(90deg);
    width: 38px;
    margin: 2px auto;
  }
}
</style>
