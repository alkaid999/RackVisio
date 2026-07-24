<template>
  <Dialog
    :model-value="visible"
    title="批量新增机柜"
    description="为同一机房一次性生成多个机柜：填写通用信息并设置编号规则，确认后批量创建。"
    class="max-w-2xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <!-- 通用信息（对所有生成的机柜生效） -->
    <div class="grid grid-cols-2 gap-4">
      <div class="flex flex-col gap-1.5">
        <Label>所属机房 <span class="text-destructive">*</span></Label>
        <Select v-model="common.room_id" placeholder="选择机房">
          <SelectTrigger placeholder="选择机房" />
          <SelectContent>
            <SelectItem v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}（{{ r.code }}）</SelectItem>
          </SelectContent>
        </Select>
        <p v-if="errors.room_id" class="text-xs text-destructive">{{ errors.room_id }}</p>
      </div>
      <div class="flex flex-col gap-1.5">
        <Label class="flex items-center gap-1"><Ruler class="h-3.5 w-3.5 text-muted-foreground" />机柜 U 数</Label>
        <Input type="number" :min="1" :max="60" v-model="common.total_u" />
      </div>
      <div class="flex flex-col gap-1.5">
        <Label class="flex items-center gap-1"><CircleDot class="h-3.5 w-3.5 text-muted-foreground" />机柜状态</Label>
        <Select v-model="common.status">
          <SelectTrigger placeholder="选择状态" />
          <SelectContent>
            <SelectItem v-for="o in RACK_STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div class="flex flex-col gap-1.5">
        <Label class="flex items-center gap-1"><Users class="h-3.5 w-3.5 text-muted-foreground" />机柜分组</Label>
        <Input v-model="common.rack_group" placeholder="选填，如：某项目组 / 某部门" />
      </div>
    </div>

    <div class="my-4 h-px bg-border" />

    <!-- 批量生成规则 -->
    <div class="grid grid-cols-4 gap-3">
      <div class="flex flex-col gap-1.5">
        <Label class="flex items-center gap-1"><Columns3 class="h-3.5 w-3.5 text-muted-foreground" />列前缀</Label>
        <Input v-model="gen.prefix" placeholder="如：A" />
      </div>
      <div class="flex flex-col gap-1.5">
        <Label class="flex items-center gap-1"><Hash class="h-3.5 w-3.5 text-muted-foreground" />起始序号</Label>
        <Input type="number" :min="1" v-model="gen.start" />
      </div>
      <div class="flex flex-col gap-1.5">
        <Label class="flex items-center gap-1"><Hash class="h-3.5 w-3.5 text-muted-foreground" />数量</Label>
        <Input type="number" :min="1" :max="100" v-model="gen.count" />
      </div>
      <div class="flex flex-col gap-1.5">
        <Label class="flex items-center gap-1"><Hash class="h-3.5 w-3.5 text-muted-foreground" />编号位数</Label>
        <Input type="number" :min="1" :max="6" v-model="gen.pad" />
      </div>
    </div>

    <!-- 生成结果摘要（只读一行，不渲染可编辑表格，去掉长边框单列） -->
    <p class="mt-3 text-sm text-muted-foreground">
      将生成 <b class="text-foreground">{{ previewCount }}</b> 个机柜：列编号
      <b class="text-foreground">{{ gen.prefix || '?' }}</b>，编号自
      <b class="text-foreground">{{ gen.start }}</b> 起、零填充
      <b class="text-foreground">{{ gen.pad }}</b> 位（示例
      <b class="text-foreground">{{ sampleCode }}</b>）。名称留空自动生成为「列编号-机柜编号」。
    </p>

    <template #footer>
      <div v-if="submitting" class="mb-3">
        <div class="mb-1 flex items-center justify-between text-xs text-muted-foreground">
          <span>正在批量新增机柜…</span>
          <span>{{ progress }}%</span>
        </div>
        <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            class="h-full rounded-full bg-primary transition-all duration-200"
            :style="{ width: progress + '%' }"
          />
        </div>
      </div>
      <div class="flex justify-end gap-2">
        <Button variant="outline" :disabled="submitting" @click="emit('update:visible', false)"><CircleX class="h-4 w-4" />取消</Button>
        <Button :loading="submitting" @click="onSubmit"><Plus class="h-4 w-4" />确认新增</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import rackApi from '@/api/rack'
import Dialog from '@/components/ui/dialog.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Button from '@/components/ui/button.vue'
import { RACK_STATUS_OPTIONS } from '@/utils/constants'
import { Ruler, CircleDot, Users, Columns3, Hash, Plus, CircleX } from 'lucide-vue-next'

const props = defineProps({
  visible: { type: Boolean, default: false },
  // 机房选项（由父组件 RackList 传入，已加载）
  rooms: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:visible', 'saved'])

const { success, error } = useToast()
const { confirm } = useConfirm()

// 通用信息：对所有生成的机柜生效
const common = reactive({ room_id: '', total_u: 42, status: '可用', rack_group: '' })
// 编号生成规则
const gen = reactive({ prefix: 'A', start: 1, count: 5, pad: 2 })
const errors = reactive({ room_id: '' })
const submitting = ref(false)
const progress = ref(0)

// 根据规则推导界面提示：将生成的机柜数 + 示例编号（不再维护可编辑预览行）。
const previewCount = computed(() =>
  Math.min(Math.max(Number(gen.count) || 1, 1), 100)
)
const sampleCode = computed(() => {
  const pad = Math.min(Math.max(Number(gen.pad) || 2, 1), 6)
  const start = Number(gen.start) || 1
  return `${gen.prefix || '?'}-${String(start).padStart(pad, '0')}`
})

// 依据规则直接构造提交项：列编号=列前缀，机柜编号=零填充序号；名称留空交后端自动生成。
function buildItems() {
  const prefix = (gen.prefix || '').trim()
  const start = Number(gen.start) || 1
  const pad = Math.min(Math.max(Number(gen.pad) || 2, 1), 6)
  const items = []
  for (let i = 0; i < previewCount.value; i++) {
    const seq = String(start + i).padStart(pad, '0')
    items.push({ column_code: prefix, code: seq, name: undefined })
  }
  return items
}

// 关闭时清空错误提示，方便下次重填。
watch(
  () => props.visible,
  (v) => {
    if (!v) errors.room_id = ''
  }
)

async function onSubmit() {
  errors.room_id = common.room_id ? '' : '请选择所属机房'
  if (!common.room_id) return
  const items = buildItems()
  if (!items.length) {
    error('请至少生成 1 个机柜')
    return
  }
  const ok = await confirm({
    title: '确认批量新增',
    description: `即将在所选机房新增 ${items.length} 个机柜（列编号「${gen.prefix || '?'}」），确认继续？`,
    variant: 'warning',
    confirmText: '确认新增',
    cancelText: '取消',
  })
  if (!ok) return

  // 限流：分块顺序提交（每批 20 台），避免一次性并发全部请求炸连接池 / 后端事务。
  // 同时实时更新进度条，消除「弹窗死寂」的体感卡顿。
  submitting.value = true
  progress.value = 0
  const total = items.length
  const CHUNK = 20
  let createdCount = 0
  const allFailed = []
  try {
    for (let i = 0; i < total; i += CHUNK) {
      const slice = items.slice(i, i + CHUNK)
      const payload = {
        room_id: common.room_id,
        total_u: Number(common.total_u),
        status: common.status,
        rack_group: (common.rack_group || '').trim() || undefined,
        items: slice.map((r) => ({
          column_code: (r.column_code || '').trim(),
          code: (r.code || '').trim(),
          name: (r.name || '').trim() || undefined,
        })),
      }
      const data = await rackApi.batchCreate(payload)
      const created = data?.created || []
      const failed = data?.failed || []
      createdCount += created.length
      // 后端 failed[].index 为当前分块内下标，需加上分块起点还原为全局行号。
      for (const f of failed) allFailed.push({ ...f, index: i + f.index })
      progress.value = Math.min(100, Math.round(((i + slice.length) / total) * 100))
    }
    if (allFailed.length === 0) success(`成功新增 ${createdCount} 个机柜`)
    else {
      const detail = allFailed
        .slice(0, 5)
        .map((f) => `${f.column_code}-${f.code}：${f.error}`)
        .join('；')
      const more = allFailed.length > 5 ? ` 等${allFailed.length}条` : ''
      success(`成功新增 ${createdCount} 个，失败 ${allFailed.length} 个（${detail}${more}）`)
    }
    emit('saved')
    emit('update:visible', false)
  } catch (e) {
    error('批量新增失败：' + (e?.message || '服务器异常'))
  } finally {
    submitting.value = false
    progress.value = 0
  }
}
</script>
