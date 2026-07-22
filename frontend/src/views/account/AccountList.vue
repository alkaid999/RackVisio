<template>
  <div class="account-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">账号管理</h2>
        <p class="page-sub">共 {{ total }} 个账号 · 管理登录账号、角色与细粒度权限分配</p>
      </div>
      <Button v-if="canManage" class="ml-auto" @click="openCreate"><CirclePlus class="h-4 w-4" />新建账号</Button>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>用户名</TableHead>
          <TableHead class="w-32">显示名</TableHead>
          <TableHead class="w-24">角色</TableHead>
          <TableHead>权限</TableHead>
          <TableHead class="w-20">状态</TableHead>
          <TableHead class="w-40">创建时间</TableHead>
          <TableHead class="w-28 text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in rows" :key="row.id">
          <TableCell class="font-medium">{{ row.username }}</TableCell>
          <TableCell class="text-muted-foreground">{{ row.display_name || '—' }}</TableCell>
          <TableCell>
            <span
              class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
              :class="row.role === 'admin' ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'"
            >{{ row.role_label }}</span>
          </TableCell>
          <TableCell>
            <div class="flex flex-wrap gap-1">
              <span
                v-for="p in permissionSummary(row.permissions, row.role === 'admin')"
                :key="p.module"
                class="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium"
                :class="p.level === 'full' ? 'bg-primary/10 text-primary' : p.level === 'view' ? 'bg-muted text-muted-foreground' : 'bg-destructive/10 text-destructive'"
              >{{ p.label }}</span>
            </div>
          </TableCell>
          <TableCell>
            <span
              v-if="row.disabled"
              class="inline-flex items-center gap-1 text-xs text-destructive"
            ><CircleSlash class="h-3.5 w-3.5" />已禁用</span>
            <span v-else class="inline-flex items-center gap-1 text-xs text-emerald-600"><CircleCheck class="h-3.5 w-3.5" />正常</span>
          </TableCell>
          <TableCell class="text-muted-foreground">{{ row.created_at || '—' }}</TableCell>
          <TableCell class="text-right">
            <div class="flex justify-end gap-1">
              <Button variant="ghost" size="icon" aria-label="查看" title="查看" @click="openView(row)"><Eye class="h-4 w-4" /></Button>
              <template v-if="canManage">
                <Button variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="openEdit(row)"><Pencil class="h-4 w-4" /></Button>
                <Button
                  variant="ghost"
                  size="icon"
                  class="text-destructive hover:text-destructive"
                  aria-label="删除"
                  :disabled="row.id === currentUserId"
                  @click="onDelete(row)"
                ><Trash2 class="h-4 w-4" /></Button>
              </template>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <!-- 新建 / 编辑账号弹窗 -->
    <Dialog v-model="dialogOpen" :title="viewMode ? '查看账号' : (mode === 'create' ? '新建账号' : '编辑账号')" :dismissible="!saving">
      <Form ref="formRef" :model="form" :rules="rules" class="space-y-4" @submit.prevent="onSubmit">
        <FormItem v-if="mode === 'create'" name="username" label="用户名">
          <Input v-model="form.username" :disabled="viewMode || saving" placeholder="3-64 个字符" autocomplete="off" />
        </FormItem>
        <FormItem name="display_name" label="显示名">
          <Input v-model="form.display_name" :disabled="viewMode || saving" placeholder="可选，如「张三」" autocomplete="off" />
        </FormItem>
        <FormItem v-if="mode === 'create' || (mode === 'edit' && !viewMode)" :name="mode === 'create' ? 'password' : 'password_edit'" :label="mode === 'create' ? '密码' : '重置密码'" :icon="Lock">
          <Input v-model="form.password" type="password" :disabled="viewMode || saving" :placeholder="mode === 'create' ? '6-128 个字符' : '留空表示不修改'" autocomplete="new-password" />
        </FormItem>
        <FormItem name="role" label="角色" :icon="ShieldCheck">
          <Select v-model="form.role" :disabled="viewMode || saving">
            <SelectTrigger :placeholder="SELECT_ALL === form.role ? '请选择角色' : ''" />
            <SelectContent>
              <SelectItem v-for="o in ROLE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>

        <!-- 细粒度权限矩阵：仅普通用户可配置；管理员恒全权限。 -->
        <div v-if="form.role === 'user'" class="space-y-1.5">
          <label class="text-sm font-medium text-foreground">模块权限</label>
          <div class="rounded-md border">
            <div class="grid grid-cols-[1fr_auto_auto] items-center gap-2 border-b bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground">
              <span>模块</span>
              <span class="w-16 text-center">查看</span>
              <span class="w-16 text-center">编辑</span>
            </div>
            <div
              v-for="m in PERMISSION_MODULES"
              :key="m"
              class="grid grid-cols-[1fr_auto_auto] items-center gap-2 border-b px-3 py-2 last:border-0"
            >
              <span class="text-sm">{{ PERMISSION_MODULE_LABELS[m] }}</span>
              <div class="flex w-16 justify-center">
                <Switch
                  :model-value="form.permissions[m].view"
                  :disabled="viewMode || saving"
                  @update:model-value="(v) => setPerm(m, 'view', v)"
                />
              </div>
              <div class="flex w-16 justify-center">
                <Switch
                  :model-value="form.permissions[m].edit"
                  :disabled="viewMode || saving"
                  @update:model-value="(v) => setPerm(m, 'edit', v)"
                />
              </div>
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            查看：可浏览该模块数据；编辑：可新增 / 删除该模块数据。两者可独立配置。
          </p>
        </div>
        <div v-else class="rounded-md border border-dashed px-3 py-3 text-sm text-muted-foreground">
          管理员拥有全部模块的查看与编辑权限，无需单独配置。
        </div>

        <FormItem v-if="mode === 'edit'" name="disabled" label="账号状态">
            <div class="flex items-center gap-2">
              <Switch v-model="form.disabled" :disabled="viewMode || saving" />
              <span class="text-sm text-muted-foreground">{{ form.disabled ? '已禁用' : '正常' }}</span>
            </div>
        </FormItem>
      </Form>
    <template #footer>
      <Button variant="outline" :disabled="saving" @click="dialogOpen = false">{{ viewMode ? '关闭' : '取消' }}</Button>
      <Button v-if="!viewMode" :disabled="saving" @click="onSubmit">
        <Spinner v-if="saving" class="mr-1.5 h-4 w-4" />保存
      </Button>
    </template>
    </Dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import accountApi from '@/api/account'
import {
  ROLE_OPTIONS,
  SELECT_ALL,
  PERMISSION_MODULES,
  PERMISSION_MODULE_LABELS,
  defaultPermissions,
  permissionSummary,
} from '@/utils/constants'
import { CirclePlus, Eye, Pencil, Trash2, Lock, ShieldCheck, CircleSlash, CircleCheck } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Dialog from '@/components/ui/dialog.vue'
import Form from '@/components/ui/form.vue'
import FormItem from '@/components/ui/form-item.vue'
import Input from '@/components/ui/input.vue'
import Switch from '@/components/ui/switch.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Spinner from '@/components/ui/spinner.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'

const auth = useAuthStore()
const { success } = useToast()
const { confirm } = useConfirm()

// 账号管理（创建 / 编辑 / 删除）需 account:edit。
const canManage = computed(() => auth.hasPermission('account:edit'))
const currentUserId = computed(() => auth.user?.id)

const rows = ref([])
const total = ref(0)
const loading = ref(false)

const dialogOpen = ref(false)
const mode = ref('create') // create | edit
const viewMode = ref(false) // 查看模式：只读展示账号详情
const saving = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  username: '',
  display_name: '',
  password: '',
  role: 'user',
  disabled: false,
  // 权限映射（仅普通用户生效）：{ room:{view,edit}, ... }
  permissions: defaultPermissions(),
})

const rules = computed(() => ({
  username:
    mode.value === 'create'
      ? { required: true, message: '请输入用户名（3-64 字符）', pattern: /^.{3,64}$/ }
      : {},
  password:
    mode.value === 'create'
      ? { required: true, message: '请输入密码（至少 6 字符）', pattern: /^.{6,128}$/ }
      : { pattern: /^.{6,128}$/, message: '密码至少 6 字符' },
  role: { required: true, message: '请选择角色' },
}))

// 将权限映射结构化为标准形态（补齐模块 / 操作键），并深拷贝，避免污染源数据。
function clonePermissions(map) {
  const out = {}
  for (const m of PERMISSION_MODULES) {
    const entry = (map && map[m]) || {}
    out[m] = { view: !!entry.view, edit: !!entry.edit }
  }
  return out
}

// 切换单个权限开关：编辑隐含查看，关闭查看隐含关闭编辑，保证语义一致。
function setPerm(module, op, val) {
  form.permissions[module][op] = val
  if (op === 'edit' && val) form.permissions[module].view = true
  if (op === 'view' && !val) form.permissions[module].edit = false
}

async function load() {
  loading.value = true
  try {
    const data = await accountApi.list({ page: 1, size: 200 })
    rows.value = (data && data.items) || []
    total.value = (data && data.total) || rows.value.length
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.username = ''
  form.display_name = ''
  form.password = ''
  form.role = 'user'
  form.disabled = false
  form.permissions = defaultPermissions()
  formRef.value && formRef.value.clearValidate && formRef.value.clearValidate()
}

function openCreate() {
  mode.value = 'create'
  editingId.value = null
  resetForm()
  dialogOpen.value = true
}

// 将行数据填充到表单（编辑 / 查看共用）。
function fillForm(row) {
  form.username = row.username
  form.display_name = row.display_name || ''
  form.password = ''
  form.role = row.role
  form.disabled = !!row.disabled
  // 普通用户带上其权限映射；管理员恒全权限（矩阵隐藏，提交时不传 permissions）。
  form.permissions = clonePermissions(row.permissions)
  formRef.value && formRef.value.clearValidate && formRef.value.clearValidate()
}
function openEdit(row) {
  viewMode.value = false
  mode.value = 'edit'
  editingId.value = row.id
  fillForm(row)
  dialogOpen.value = true
}
// 查看模式：普通用户无需编辑权限即可只读浏览账号详情。
function openView(row) {
  viewMode.value = true
  mode.value = 'edit'
  editingId.value = row.id
  fillForm(row)
  dialogOpen.value = true
}

async function onSubmit() {
  if (saving.value) return
  const okValid = await (formRef.value && formRef.value.validate ? formRef.value.validate() : Promise.resolve(true))
  if (okValid !== true) return

  saving.value = true
  try {
    if (mode.value === 'create') {
      const payload = {
        username: form.username.trim(),
        display_name: form.display_name.trim() || null,
        password: form.password,
        role: form.role,
      }
      // 仅普通用户提交权限映射；管理员忽略。
      if (form.role === 'user') payload.permissions = clonePermissions(form.permissions)
      await accountApi.create(payload)
      success('账号创建成功')
    } else {
      const payload = {
        display_name: form.display_name.trim() || null,
        role: form.role,
        disabled: form.disabled,
      }
      if (form.password) payload.password = form.password
      if (form.role === 'user') payload.permissions = clonePermissions(form.permissions)
      await accountApi.update(editingId.value, payload)
      success('账号更新成功')
    }
    dialogOpen.value = false
    load()
  } catch (e) {
    // 后端错误（如用户名重复、末管理员守卫）已由拦截器 toast 提示。
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  if (row.id === currentUserId.value) return
  const ok = await confirm({
    title: '删除账号',
    description: `确认删除账号「${row.username}」？该操作不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await accountApi.remove(row.id)
    success('账号已删除')
    load()
  } catch (e) {
    // 守卫冲突（如末管理员）已由拦截器提示。
  }
}

onMounted(load)
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
}
.page-sub {
  margin: 0;
  color: hsl(var(--muted-foreground));
  font-size: 13px;
}
</style>
