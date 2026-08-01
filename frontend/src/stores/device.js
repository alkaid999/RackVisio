import { defineStore } from 'pinia'
import deviceApi from '@/api/device'

// 设备状态：列表 / 详情。
export const useDeviceStore = defineStore('device', {
  state: () => ({
    devices: [],
    total: 0,
    currentDevice: null,
    loading: false,
    // H-06：请求失败标志。此前 fetchList 静默吞错返回空列表，页面只区分
    // loading/empty 两态 → 失败被误显示为「暂无设备」；补 error 供页面渲染
    // 失败态与重试按钮（与 room/rack/consumable 的错误策略对齐）。
    error: null,
  }),
  actions: {
    async fetchList(params = {}) {
      this.loading = true
      this.error = null
      try {
        const data = await deviceApi.list(params)
        this.devices = (data && data.items) || []
        this.total = (data && data.total) || 0
      } catch (e) {
        // 拦截器已统一 toast；此处仅记录错误标志，不吞错冒泡（调用方无 catch 也不会 unhandled）。
        this.error = e
        this.devices = []
        this.total = 0
      } finally {
        this.loading = false
      }
    },
    async fetchOne(id) {
      this.loading = true
      this.error = null
      try {
        this.currentDevice = await deviceApi.get(id)
      } catch (e) {
        this.error = e
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      return await deviceApi.create(payload)
    },
    async update(id, payload) {
      return await deviceApi.update(id, payload)
    },
    async remove(id) {
      return await deviceApi.remove(id)
    },
  },
})
