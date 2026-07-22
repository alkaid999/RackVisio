import { defineStore } from 'pinia'
import deviceApi from '@/api/device'

// 设备状态：列表 / 详情。
export const useDeviceStore = defineStore('device', {
  state: () => ({
    devices: [],
    total: 0,
    currentDevice: null,
    loading: false,
  }),
  actions: {
    async fetchList(params = {}) {
      this.loading = true
      try {
        const data = await deviceApi.list(params).catch(() => ({ items: [], total: 0 }))
        this.devices = (data && data.items) || []
        this.total = (data && data.total) || 0
      } finally {
        this.loading = false
      }
    },
    async fetchOne(id) {
      this.loading = true
      try {
        this.currentDevice = await deviceApi.get(id)
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
