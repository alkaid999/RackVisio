// Excel / CSV 工具：导出（xlsx / csv）与文件解析（xlsx / csv）。
// 依赖 exceljs（^4.4.0，已安装）；xlsx/csv 解析全部在前端完成，
// 解析结果以纯对象数组交给导入接口，后端只负责校验 + 落库（单一事实来源）。
import { downloadBlob } from './download'

// ============ 导出 ============

// 导出为 Excel / CSV。
// @param rows     后端返回的行数组
// @param columns  [{ key, label, render?(row)=>any }] —— render 处理派生/格式化字段（如楼宇/楼层合并）
// @param filename 目标文件名（不含扩展名）
// @param type     'xlsx' | 'csv'
export async function exportData({ rows = [], columns = [], filename = 'export', type = 'xlsx' }) {
  const safeName = sanitizeFilename(filename)
  if (type === 'csv') {
    const csv = toCsv(rows, columns)
    // BOM 保证中文在 Excel 中不乱码
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    downloadBlob(blob, `${safeName}.csv`)
    return
  }

  const ExcelJS = await import('exceljs')
  const XLSX = ExcelJS.default || ExcelJS
  const wb = new XLSX.Workbook()
  const ws = wb.addWorksheet('Sheet1')
  ws.columns = columns.map((c) => ({ header: c.label, key: c.key, width: 18 }))
  for (const row of rows) {
    const obj = {}
    for (const c of columns) {
      const v = c.render ? c.render(row) : row?.[c.key]
      obj[c.key] = formatCellValue(v)
    }
    ws.addRow(obj)
  }
  // 表头加粗
  if (ws.getRow(1)) {
    ws.getRow(1).font = { bold: true }
    ws.getRow(1).alignment = { vertical: 'middle' }
  }
  const buf = await wb.xlsx.writeBuffer()
  const blob = new Blob([buf], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  downloadBlob(blob, `${safeName}.xlsx`)
}

function toCsv(rows, columns) {
  const escape = (v) => {
    const s = v == null ? '' : String(v)
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }
  const lines = [columns.map((c) => escape(c.label)).join(',')]
  for (const row of rows) {
    lines.push(
      columns
        .map((c) => escape(formatCellValue(c.render ? c.render(row) : row?.[c.key])))
        .join(',')
    )
  }
  return lines.join('\r\n')
}

function sanitizeFilename(name) {
  return String(name).replace(/[\\/:*?"<>|]/g, '_').slice(0, 80) || 'export'
}

// 导出单元格值格式化：Date → YYYY-MM-DD，Boolean → 'true'/'false'，其余原样。
// 目的：保证导出文件中的日期/布尔值可被「导入」原样识别（round-trip 一致）。
// （经 HTTP JSON 反序列化的日期已是字符串、布尔/数字照常，此函数仅作兜底防御。）
function formatCellValue(v) {
  if (v == null) return ''
  if (v instanceof Date) {
    const p = (n) => String(n).padStart(2, '0')
    return `${v.getFullYear()}-${p(v.getMonth() + 1)}-${p(v.getDate())}`
  }
  if (typeof v === 'boolean') return v ? 'true' : 'false'
  return v
}

// ============ 解析 ============

// 读取用户上传的 .xlsx / .xls / .csv 文件，返回 { headers, rows }。
// rows 中每条记录以「表头文本」为键；表头会去掉末尾的「 * 」（模板必填标记）。
export async function readRowsFromFile(file) {
  const name = (file.name || '').toLowerCase()
  if (name.endsWith('.csv')) {
    const text = await file.text()
    return parseCsv(text)
  }
  const ExcelJS = await import('exceljs')
  const XLSX = ExcelJS.default || ExcelJS
  const wb = new XLSX.Workbook()
  const buf = await file.arrayBuffer()
  await wb.xlsx.load(buf)
  const ws = wb.worksheets[0]
  if (!ws) return { headers: [], rows: [] }
  const headers = []
  const records = []
  let first = true
  ws.eachRow((row) => {
    if (first) {
      row.eachCell((cell) => headers.push(normalizeHeader(cell.text ?? cell.value)))
      first = false
      return
    }
    const obj = {}
    row.eachCell((cell, colNumber) => {
      const h = headers[colNumber - 1]
      if (h != null) obj[h] = cell.text ?? cell.value ?? ''
    })
    records.push(obj)
  })
  return { headers, rows: records }
}

function normalizeHeader(h) {
  return String(h == null ? '' : h).replace(/\s*\*\s*$/, '').trim()
}

// 标准 CSV 解析（支持引号、逗号、换行、双引号转义、BOM）。
function parseCsv(text) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1)
  const matrix = []
  let field = ''
  let row = []
  let inQuotes = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        field += c
      }
    } else if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      row.push(field)
      field = ''
    } else if (c === '\r') {
      // 忽略，统一按 \n 切行
    } else if (c === '\n') {
      row.push(field)
      matrix.push(row)
      row = []
      field = ''
    } else {
      field += c
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field)
    matrix.push(row)
  }
  if (matrix.length === 0) return { headers: [], rows: [] }
  const rawHeaders = matrix[0].map(normalizeHeader)
  const rows = matrix.slice(1).map((r) => {
    const obj = {}
    rawHeaders.forEach((h, idx) => {
      obj[h] = r[idx] != null ? r[idx] : ''
    })
    return obj
  })
  return { headers: rawHeaders, rows }
}

// ============ 行 → 导入项 ============

// 将解析后的记录按 fields 映射为后端导入项的数组。
// fields: [{ key, label, required?, type? }]，key 必须与后端 ImportItem 字段名一致。
// 自动做类型转换（integer / boolean），空单元格跳过（保留后端默认值）。
export function rowsToItems(rows, fields) {
  return rows
    .map((row) => {
      const item = {}
      for (const f of fields) {
        const raw = row[f.label]
        if (raw == null || raw === '') continue
        const coerced = coerce(f, raw)
        if (coerced !== undefined) item[f.key] = coerced
      }
      return item
    })
    .filter((item) => Object.keys(item).length > 0)
}

function coerce(field, raw) {
  const v = String(raw).trim()
  if (v === '') return undefined
  switch (field.type) {
    case 'integer': {
      const n = Number(v)
      return Number.isFinite(n) ? n : v
    }
    case 'boolean':
      return v === 'true' || v === '是' || v === '1' || v === 'yes' || v === 'y'
    default:
      return v
  }
}
