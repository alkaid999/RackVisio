import { defineStore } from 'pinia'
import consumableApi from '@/api/consumable'

// 耗材管理：类型 / 分类 / 具体耗材 / 库存变动历史的全局状态。
export const useConsumableStore = defineStore('consumable', {
  state: () => ({
    types: [], // 全部耗材类型（含汇总计数）
    categories: [], // 当前选中类型下的分类列表
    items: [], // 当前分页的耗材列表
    total: 0,
    currentItem: null,
    records: [], // 库存变动记录（单耗材或全局）
    recordTotal: 0,
    loading: false,
    recordLoading: false,
  }),
  actions: {
    // ===== 类型 =====
    async fetchTypes() {
      this.types = await consumableApi.listTypes()
      return this.types
    },
    async createType(payload) {
      return await consumableApi.createType(payload)
    },
    async updateType(id, payload) {
      return await consumableApi.updateType(id, payload)
    },
    async removeType(id) {
      return await consumableApi.removeType(id)
    },

    // ===== 分类 =====
    // 拉取某类型下的分类；空 typeId 直接清空（避免无意义请求 / 误筛）。
    async fetchCategories(typeId) {
      if (!typeId) {
        this.categories = []
        return this.categories
      }
      this.categories = await consumableApi.listCategories(typeId)
      return this.categories
    },
    async createCategory(typeId, payload) {
      return await consumableApi.createCategory(typeId, payload)
    },
    async updateCategory(id, payload) {
      return await consumableApi.updateCategory(id, payload)
    },
    async removeCategory(id) {
      return await consumableApi.removeCategory(id)
    },

    // ===== 耗材 =====
    async fetchItems(params = {}) {
      this.loading = true
      try {
        const data = await consumableApi.listItems(params)
        this.items = data.items || []
        this.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    async fetchItem(id) {
      this.currentItem = await consumableApi.getItem(id)
      return this.currentItem
    },
    async createItem(payload) {
      return await consumableApi.createItem(payload)
    },
    async updateItem(id, payload) {
      return await consumableApi.updateItem(id, payload)
    },
    async removeItem(id) {
      return await consumableApi.removeItem(id)
    },

    // ===== 库存变动 =====
    // 返回更新后的耗材（含最新 current_quantity）。
    async adjustStock(id, payload) {
      return await consumableApi.adjustStock(id, payload)
    },

    // ===== 历史 =====
    async fetchRecords(itemId, params = {}) {
      this.recordLoading = true
      try {
        const data = await consumableApi.itemRecords(itemId, params)
        this.records = data.items || []
        this.recordTotal = data.total || 0
      } finally {
        this.recordLoading = false
      }
    },
    async fetchAllRecords(params = {}) {
      this.recordLoading = true
      try {
        const data = await consumableApi.allRecords(params)
        this.records = data.items || []
        this.recordTotal = data.total || 0
      } finally {
        this.recordLoading = false
      }
    },
  },
})
