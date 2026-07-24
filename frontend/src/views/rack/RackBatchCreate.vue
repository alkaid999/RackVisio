<template>
  <Dialog
    :model-value="visible"
    title="批量新增机柜"
    description="为同一机房一次性生成多个机柜：先填写通用信息，再设置编号规则并生成预览，确认后批量创建。"
    class="max-w-3xl"
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

    <!-- 预览表（可编辑） -->
    <div class="mt-4">
      <div class="mb-2 flex items-center justify-between">
        <span class="text-sm font-medium">预览（{{ rows.length }} 台）· 名称留空将自动生成为「列编号-机柜编号」</span>
        <Button size="sm" variant="outline" @click="generate"><RefreshCw class="h-3.5 w-3.5" />重新生成</Button>
      </div>
      <div class="max-h-64 overflow-auto rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead class="w-36">列编号</TableHead>
              <TableHead class="w-36">机柜编号</TableHead>
              <TableHead>名称（选填）</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="(r, i) in rows" :key="i" v-memo="[r.column_code, r.code, r.name]">
              <TableCell><Input v-model="r.column_code" class="h-8" /></TableCell>
              <TableCell><Input v-model="r.code" class="h-8" /></TableCell>
              <TableCell>
                <Input v-model="r.name" :placeholder="`${r.column_code || '?'}-${r.code || '?'}`" class="h-8" />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>

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
import { reactive, ref, watch } from 'vue'
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
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import { RACK_STATUS_OPTIONS } from '@/utils/constants'
import { Ruler, CircleDot, Users, Columns3, Hash, Plus, RefreshCw, CircleX } from 'lucide-vue-next'

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
// 可编辑预览行
const rows = ref([])
const errors = reactive({ room_id: '' })
const submitting = ref(false)
const progress = ref(0)

// 根据「列前缀 + 起始序号 + 数量 + 编号位数」生成基础行：
// 列编号 = 列前缀（同一列内多台机柜共享），机柜编号 = 零填充的序号。
// 后端唯一约束为 (room_id, column_code, code) 复合键，故同列多台机柜合法。
function buildRows() {
  const prefix = (gen.prefix || '').trim()
  const start = Number(gen.start) || 1
  const count = Math.min(Math.max(Number(gen.count) || 1, 1), 100)
  const pad = Math.min(Math.max(Number(gen.pad) || 2, 1), 6)
  const list = []
  for (let i = 0; i < count; i++) {
    const seq = String(start + i).padStart(pad, '0')
    list.push({ column_code: prefix, code: seq, name: '' })
  }
  rows.value = list
}
function generate() {
  buildRows()
}

// 打开时若无预览行则生成一份默认预览；关闭时清空，方便下次重新生成。
watch(
  () => props.visible,
  (v) => {
    if (v && rows.value.length === 0) buildRows()
    if (!v) {
      rows.value = []
      errors.room_id = ''
    }
  }
)

async function onSubmit() {
  errors.room_id = common.room_id ? '' : '请选择所属机房'
  if (!common.room_id) return
  const invalid = rows.value.filter((r) => !(r.column_code || '').trim() || !(r.code || '').trim())
  if (invalid.length) {
    error('请补全所有机柜的「列编号」与「机柜编号」')
    return
  }
  const ok = await confirm({
    title: '确认批量新增',
    description: `即将在所选机房新增 ${rows.value.length} 个机柜，确认继续？`,
    variant: 'warning',
    confirmText: '确认新增',
    cancelText: '取消',
  })
  if (!ok) return

  // 限流：分块顺序提交（每批 20 台），避免一次性并发全部请求炸连接池 / 后端事务。
  // 同时实时更新进度条，消除「弹窗死寂」的体感卡顿。
  submitting.value = true
  progress.value = 0
  const total = rows.value.length
  const CHUNK = 20
  let createdCount = 0
  const allFailed = []
  try {
    for (let i = 0; i < total; i += CHUNK) {
      const slice = rows.value.slice(i, i + CHUNK)
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
