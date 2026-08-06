import { defineStore } from 'pinia'
import hardwareApi from '@/api/hardware'

// 硬件管理（独立个体模型）：类型 / 分类 / 具体硬件 / 变动历史 + 设备关联的全局状态。
export const useHardwareStore = defineStore('hardware', {
  state: () => ({
    types: [], // 全部硬件类型（含汇总计数）
    categories: [], // 当前选中类型下的分类列表
    items: [], // 当前分页的硬件列表
    total: 0,
    currentItem: null,
    records: [], // 变动记录（单硬件或全局）
    recordTotal: 0,
    loading: false,
    recordLoading: false,
    deviceHardwares: [], // 设备已安装硬件列表（设备详情页「设备硬件」卡片）
  }),
  actions: {
    // ===== 类型 =====
    async fetchTypes() {
      this.types = await hardwareApi.listTypes()
      return this.types
    },
    async createType(payload) {
      return await hardwareApi.createType(payload)
    },
    async updateType(id, payload) {
      return await hardwareApi.updateType(id, payload)
    },
    async removeType(id) {
      return await hardwareApi.removeType(id)
    },
    // 类型手动排序：调用后端持久化，并用返回的全量列表刷新本地 types。
    async reorderTypes(ids) {
      this.types = await hardwareApi.reorderTypes(ids)
      return this.types
    },

    // ===== 分类 =====
    // 拉取某类型下的分类；空 typeId 直接清空（避免无意义请求 / 误筛）。
    async fetchCategories(typeId) {
      if (!typeId) {
        this.categories = []
        return this.categories
      }
      this.categories = await hardwareApi.listCategories(typeId)
      return this.categories
    },
    async createCategory(typeId, payload) {
      return await hardwareApi.createCategory(typeId, payload)
    },
    async updateCategory(id, payload) {
      return await hardwareApi.updateCategory(id, payload)
    },
    async removeCategory(id) {
      return await hardwareApi.removeCategory(id)
    },
    // 分类手动排序：调用后端持久化，并用返回的全量列表刷新本地 categories。
    async reorderCategories(typeId, ids) {
      this.categories = await hardwareApi.reorderCategories(typeId, ids)
      return this.categories
    },

    // ===== 硬件（独立个体）=====
    async fetchItems(params = {}) {
      this.loading = true
      try {
        const data = await hardwareApi.listItems(params)
        this.items = data.items || []
        this.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    async fetchItem(id) {
      this.currentItem = await hardwareApi.getItem(id)
      return this.currentItem
    },
    async createItem(payload) {
      return await hardwareApi.createItem(payload)
    },
    async updateItem(id, payload) {
      return await hardwareApi.updateItem(id, payload)
    },
    async removeItem(id) {
      return await hardwareApi.removeItem(id)
    },

    // ===== 变动历史 =====
    async fetchRecords(itemId, params = {}) {
      this.recordLoading = true
      try {
        const data = await hardwareApi.itemRecords(itemId, params)
        this.records = data.items || []
        this.recordTotal = data.total || 0
      } finally {
        this.recordLoading = false
      }
    },
    async fetchAllRecords(params = {}) {
      this.recordLoading = true
      try {
        const data = await hardwareApi.allRecords(params)
        this.records = data.items || []
        this.recordTotal = data.total || 0
      } finally {
        this.recordLoading = false
      }
    },

    // ===== 设备硬件联动（一对一）=====
    async fetchDeviceHardwares(deviceId) {
      this.deviceHardwares = await hardwareApi.deviceHardwares(deviceId)
      return this.deviceHardwares
    },
    // 设备添加硬件时的候选池：硬件管理中「在库」的具体硬件（与机柜上架选设备同理）。
    async fetchAvailableItems(params = {}) {
      return await hardwareApi.listItems({ ...params, status: '在库' })
    },
    async assignToDevice(deviceId, payload) {
      return await hardwareApi.assignToDevice(deviceId, payload)
    },
    async unassignFromDevice(deviceId, hardwareItemId) {
      return await hardwareApi.unassignFromDevice(deviceId, hardwareItemId)
    },
  },
})
