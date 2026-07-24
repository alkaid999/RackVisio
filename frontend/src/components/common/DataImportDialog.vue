<template>
  <Sheet
    :model-value="visible"
    :title="`导入${config?.title || ''}`"
    side="right"
    class="w-full sm:max-w-5xl bg-card border-border/60 shadow-xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <div class="flex flex-1 min-h-0 flex-col">
      <!-- 主体：左常驻说明 + 右滚动工作流 -->
      <div class="flex min-h-0 flex-1">
        <!-- 左栏：常驻参考（模板下载 / 步骤 / 字段说明），始终可见 -->
        <aside class="hidden w-72 shrink-0 flex-col gap-4 overflow-y-auto border-r border-border/60 bg-muted/30 p-4 md:flex">
          <div class="space-y-2">
            <div class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">第 1 步 · 准备</div>
            <p class="text-sm leading-relaxed text-muted-foreground">
              先下载模板，按表头填写后导入。表头标 <span class="font-semibold text-red-500">*</span> 为必填。
            </p>
            <Button variant="outline" size="sm" class="mt-1 w-full" @click="downloadTemplate">
              <Download class="h-4 w-4" />下载导入模板
            </Button>
          </div>

          <Separator class="!my-1" />

          <Collapsible v-model="guideOpen" :default-open="true">
            <CollapsibleTrigger class="flex w-full items-center justify-between rounded-lg px-1 py-1 text-sm font-medium transition-colors hover:text-primary">
              <span>字段说明</span>
              <span class="text-xs text-muted-foreground">必填 {{ requiredFields.length }} · 选填 {{ optionalFields.length }}</span>
              <ChevronDown class="h-4 w-4 text-muted-foreground transition-transform duration-200" :class="guideOpen ? 'rotate-180' : ''" />
            </CollapsibleTrigger>
            <CollapsibleContent class="mt-3 space-y-4">
              <!-- 必填字段：浅红 pill（恢复上一版红标，仅调浅色） -->
              <div>
                <div class="mb-2 flex items-center gap-1.5 text-xs font-semibold text-red-500">
                  <span class="h-1.5 w-1.5 rounded-full bg-red-500" />必填字段
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="f in requiredFields"
                    :key="f.key"
                    class="inline-flex items-center gap-0.5 rounded-full border border-red-200/70 bg-red-50/50 px-2 py-0.5 text-xs font-medium text-red-500 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400"
                  >
                    <span class="text-red-500">*</span>{{ f.label }}
                  </span>
                </div>
              </div>
              <!-- 选填字段：中性 pill -->
              <div>
                <div class="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                  <span class="h-1.5 w-1.5 rounded-full bg-muted-foreground/50" />选填字段
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="f in optionalFields"
                    :key="f.key"
                    class="inline-flex items-center rounded-full border border-border bg-card px-2 py-0.5 text-xs text-muted-foreground"
                  >
                    {{ f.label }}
                  </span>
                </div>
              </div>
              <!-- 填写提示 -->
              <div v-if="hintFields.length">
                <div class="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                  <span class="h-1.5 w-1.5 rounded-full bg-primary/60" />填写提示
                </div>
                <ul class="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
                  <li v-for="f in hintFields" :key="f.key" class="flex gap-1.5">
                    <span class="mt-1 shrink-0 text-primary">·</span>
                    <span><b class="font-medium text-foreground/80">{{ f.label }}</b>：{{ f.hint }}</span>
                  </li>
                </ul>
              </div>
            </CollapsibleContent>
          </Collapsible>

          <Separator class="!my-1" />

          <div class="rounded-xl border border-border/60 bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
            <p class="mb-1.5 font-medium text-foreground/80">导入说明</p>
            <ul class="list-disc space-y-1 pl-4">
              <li>支持 .xlsx / .xls / .csv</li>
              <li>单次最多 500 行，超出请拆分</li>
              <li>导出文件可直接改后回导</li>
            </ul>
          </div>
        </aside>

        <!-- 右栏：工作流（独立纵向滚动，横向不溢出） -->
        <section class="flex min-h-0 min-w-0 flex-1 flex-col">
          <!-- 步骤进度 -->
          <div class="flex shrink-0 items-center gap-2 border-b border-border/60 bg-card px-5 py-3">
            <template v-for="(s, i) in steps" :key="s.key">
              <div class="flex items-center gap-2" :class="i <= activeStep ? 'text-foreground' : 'text-muted-foreground'">
                <span
                  class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold transition-all duration-300"
                  :class="i < activeStep ? 'bg-primary text-primary-foreground' : i === activeStep ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'"
                >
                  <Check v-if="i < activeStep" class="h-3.5 w-3.5" />
                  <span v-else>{{ i + 1 }}</span>
                </span>
                <span class="text-sm">{{ s.label }}</span>
              </div>
              <ChevronRight v-if="i < steps.length - 1" class="h-4 w-4 text-muted-foreground/40" />
            </template>
          </div>

          <!-- 滚动工作区 -->
          <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
            <!-- 步骤 1：上传（拖拽 / 点击） -->
            <div
              class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-all duration-200"
              :class="dragOver ? 'border-primary bg-primary/5 scale-[1.01]' : 'border-border/70 bg-muted/40 hover:border-primary/50 hover:bg-muted/60'"
              @dragover.prevent="dragOver = true"
              @dragleave.prevent="dragOver = false"
              @drop.prevent="onDrop"
            >
              <div class="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary transition-transform duration-200" :class="dragOver ? 'scale-110' : ''">
                <UploadCloud class="h-7 w-7" />
              </div>
              <p class="text-sm font-medium">拖拽文件到此处，或</p>
              <Button variant="outline" size="sm" class="mt-3" @click="fileInput?.click()">
                <Upload class="h-4 w-4" />选择文件
              </Button>
              <input ref="fileInput" type="file" accept=".xlsx,.xls,.csv" class="hidden" @change="onFileChange" />
              <p v-if="fileName" class="mt-3 max-w-full truncate text-sm text-muted-foreground">已选择：{{ fileName }}</p>
              <p v-if="parseError" class="mt-2 text-sm text-red-500">{{ parseError }}</p>
            </div>

            <!-- 步骤 2：校验与预览 -->
            <div v-if="records.length">
              <div class="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                <span class="text-muted-foreground">
                  已读取 <span class="font-semibold text-foreground">{{ records.length }}</span> 行
                </span>
                <span v-if="tooMany" class="rounded-full bg-red-100/70 px-2.5 py-0.5 text-xs font-medium text-red-500 dark:bg-red-900/40 dark:text-red-400">
                  超过 500 行上限，请拆分文件
                </span>
              </div>

              <!-- 必填缺失：整块浅红提示 -->
              <div
                v-if="requiredErrors.length"
                class="mb-3 rounded-xl border border-red-200 bg-red-50/70 p-3 text-sm dark:border-red-900/50 dark:bg-red-950/30"
              >
                <div class="mb-1 font-medium text-red-500 dark:text-red-400">
                  发现 {{ requiredErrors.length }} 处必填缺失，请修正后重新选择文件：
                </div>
                <ul class="list-disc space-y-0.5 pl-4 text-red-500 dark:text-red-400">
                  <li v-for="(e, i) in requiredErrors.slice(0, 20)" :key="i">第 {{ e.row }} 行：{{ e.errors.join('；') }}</li>
                  <li v-if="requiredErrors.length > 20">…共 {{ requiredErrors.length }} 处</li>
                </ul>
              </div>

              <!-- 预览：每行一张「行卡片」，按页展示；行卡片内 label:value 响应式网格自动换行 → 无横向滚动 -->
              <div v-else class="space-y-2.5">
                <div class="text-xs font-medium text-muted-foreground">
                  预览（每页 {{ PREVIEW_PAGE_SIZE }} 行，可翻页查看全部 {{ records.length }} 行）
                </div>
                <div
                  v-for="(row, i) in pagedRows"
                  :key="i"
                  class="rounded-xl border bg-card p-3.5 transition-colors duration-200 hover:border-primary/40"
                  :class="errorRows.has(rowNo(i)) ? 'border-red-200 dark:border-red-900/50' : 'border-border/60'"
                >
                  <div class="mb-2.5 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                    第 {{ rowNo(i) }} 行
                    <span v-if="errorRows.has(rowNo(i))" class="rounded-full bg-red-100/70 px-1.5 py-0.5 text-red-500 dark:bg-red-900/40 dark:text-red-400">必填缺失</span>
                  </div>
                  <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
                    <div v-for="f in config.fields" :key="f.key" class="flex min-w-0 gap-1">
                      <dt class="shrink-0 text-muted-foreground">{{ f.label }}：</dt>
                      <dd class="truncate font-medium" :title="displayVal(row[f.label])">
                        {{ displayVal(row[f.label]) }}
                      </dd>
                    </div>
                  </dl>
                </div>

                <!-- 分页控件：仅当行数超过单页时显示 -->
                <div v-if="records.length > PREVIEW_PAGE_SIZE" class="mt-3 flex items-center justify-between text-sm text-muted-foreground">
                  <span>第 {{ previewPage }} / {{ totalPreviewPages }} 页</span>
                  <div class="flex gap-2">
                    <Button size="sm" variant="outline" :disabled="previewPage === 1" @click="previewPage--">上一页</Button>
                    <Button size="sm" variant="outline" :disabled="previewPage === totalPreviewPages" @click="previewPage++">下一页</Button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 步骤 3：导入结果（成功/失败摘要已统一经右上角 Toast 呈现；此处仅保留需滚动查看的失败明细） -->
            <div v-if="result" class="space-y-2.5">
              <div
                v-if="result.failures.length"
                class="max-h-56 overflow-y-auto rounded-xl border border-red-200 bg-red-50/70 p-3 text-sm dark:border-red-900/50 dark:bg-red-950/30"
              >
                <div class="mb-1 font-medium text-red-500 dark:text-red-400">
                  失败明细（共 {{ result.failures.length }} 条，已通过右上角通知汇总）：
                </div>
                <ul class="list-disc space-y-0.5 pl-4 text-red-500 dark:text-red-400">
                  <li v-for="(f, i) in result.failures.slice(0, 50)" :key="i">
                    第 {{ f.row }} 行：{{ f.errors.join('；') }}
                  </li>
                  <li v-if="result.failures.length > 50">…共 {{ result.failures.length }} 条失败</li>
                </ul>
              </div>
              <p v-else class="text-xs text-muted-foreground">
                导入结果已通过右上角通知呈现，列表已刷新。
              </p>
            </div>
          </div>
        </section>
      </div>

      <!-- 底部操作（固定，不随工作区滚动） -->
      <div class="flex shrink-0 justify-end gap-2 border-t border-border/60 bg-card px-4 py-3">
        <Button variant="outline" @click="emit('update:visible', false)">关闭</Button>
        <Button v-if="result" variant="outline" @click="reset">重新导入</Button>
        <Button
          v-else
          :loading="importing"
          :disabled="!canImport"
          @click="onImport"
        >
          <Upload class="h-4 w-4" />开始导入
        </Button>
      </div>
    </div>
  </Sheet>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Download, Upload, UploadCloud, Check, ChevronDown, ChevronRight } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { exportData, readRowsFromFile, rowsToItems } from '@/utils/excel'
import { templateColumns, validateRequired } from '@/utils/importConfig'
import Sheet from '@/components/ui/sheet.vue'
import Button from '@/components/ui/button.vue'
import Separator from '@/components/ui/separator.vue'
import Collapsible from '@/components/ui/collapsible.vue'
import CollapsibleTrigger from '@/components/ui/collapsible-trigger.vue'
import CollapsibleContent from '@/components/ui/collapsible-content.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  config: { type: Object, required: true }, // 来自 importConfig 的 room/rack/device 配置
  importFn: { type: Function, required: true }, // async (items) => ImportResult
})
const emit = defineEmits(['update:visible', 'imported'])

const { success, error: toastError, warning } = useToast()

const PREVIEW_PAGE_SIZE = 10 // 预览每页行数（配分页，避免一次性渲染全部/长列表）

const fileInput = ref(null)
const fileName = ref('')
const records = ref([])
const items = ref([])
const parseError = ref('')
const requiredErrors = ref([])
const importing = ref(false)
const result = ref(null)
const dragOver = ref(false)
const guideOpen = ref(true)
const previewPage = ref(1)

const requiredFields = computed(() => props.config.fields.filter((f) => f.required))
const optionalFields = computed(() => props.config.fields.filter((f) => !f.required))
const hintFields = computed(() => props.config.fields.filter((f) => f.hint))
const tooMany = computed(() => records.value.length > 500)
const canImport = computed(
  () => records.value.length > 0 && !tooMany.value && requiredErrors.value.length === 0 && !importing.value
)

// 步骤状态机：选择文件 → 校验预览 → 导入结果
const steps = [
  { key: 'select', label: '选择文件' },
  { key: 'preview', label: '校验预览' },
  { key: 'done', label: '导入结果' },
]
const activeStep = computed(() => (result.value ? 2 : records.value.length ? 1 : 0))
// 预览中标记「必填缺失」的行号集合（用于行卡片红框）
const errorRows = computed(() => new Set(requiredErrors.value.map((e) => e.row)))
// 分页：当前页切片 + 总页数
const totalPreviewPages = computed(() => Math.max(1, Math.ceil(records.value.length / PREVIEW_PAGE_SIZE)))
const pagedRows = computed(() => {
  const start = (previewPage.value - 1) * PREVIEW_PAGE_SIZE
  return records.value.slice(start, start + PREVIEW_PAGE_SIZE)
})
// 由当前页内序号推算原始行号（1-based），用于必填缺失高亮
function rowNo(i) {
  return (previewPage.value - 1) * PREVIEW_PAGE_SIZE + i + 1
}

function displayVal(v) {
  return v == null || v === '' ? '—' : v
}

watch(
  () => props.visible,
  (v) => {
    if (v) reset()
  }
)

function reset() {
  fileName.value = ''
  records.value = []
  items.value = []
  parseError.value = ''
  requiredErrors.value = []
  result.value = null
  importing.value = false
  dragOver.value = false
  previewPage.value = 1
}

async function parseFile(file) {
  if (!file) return
  fileName.value = file.name
  parseError.value = ''
  result.value = null
  previewPage.value = 1
  try {
    const { rows } = await readRowsFromFile(file)
    records.value = rows
    items.value = rows.map((r) => {
      const it = rowsToItems([r], props.config.fields)[0] || {}
      return props.config.transformItem ? props.config.transformItem(it) : it
    })
    requiredErrors.value = validateRequired(rows, props.config)
  } catch (err) {
    parseError.value = '文件解析失败：' + (err?.message || err)
    records.value = []
    items.value = []
  }
}

function onFileChange(e) {
  const f = e.target.files?.[0]
  e.target.value = '' // 允许重复选择同一文件
  parseFile(f)
}

function onDrop(e) {
  dragOver.value = false
  parseFile(e.dataTransfer?.files?.[0])
}

function downloadTemplate() {
  const cols = templateColumns(props.config)
  exportData({ rows: [], columns: cols, filename: `${props.config.module}_导入模板`, type: 'xlsx' })
}

async function onImport() {
  if (!canImport.value) return
  importing.value = true
  result.value = null
  try {
    const res = await props.importFn(items.value)
    result.value = res
    if (res && res.created > 0) emit('imported')
    // 导入结果统一走右上角 Toast（与全站成功/失败提示同风格），不在弹窗内重复渲染摘要 pill
    const label = props.config.title || ''
    if (res.created > 0 && res.failed === 0) {
      success(`成功导入 ${res.created} 条${label}`, {
        description: '列表已刷新，可前往查看。',
      })
    } else if (res.created > 0 && res.failed > 0) {
      warning(`部分导入：${res.created} 条成功，${res.failed} 条失败`, {
        description: '失败明细见弹窗下方，修正后可重新导入。',
      })
    } else {
      toastError(`导入失败：${res.failed} 条未导入，请检查后重试`)
    }
  } catch (e) {
    toastError('导入请求失败，请重试')
  } finally {
    importing.value = false
  }
}
</script>
