import { defineStore } from 'pinia'
import rackApi from '@/api/rack'

// 机柜状态：列表 / 详情 / U 位图 / 设备列表 / 候选设备。
export const useRackStore = defineStore('rack', {
  state: () => ({
    list: [],
    total: 0,
    currentRack: null,
    devices: [],
    candidates: [],
    uMap: null,
    loading: false,
  }),
  actions: {
    async fetchList(params = {}) {
      this.loading = true
      try {
        const data = await rackApi.list(params)
        this.list = data.items || []
        this.total = data.total || 0
        return this.list
      } finally {
        this.loading = false
      }
    },
    async fetchOne(id) {
      this.loading = true
      try {
        this.currentRack = await rackApi.get(id)
      } finally {
        this.loading = false
      }
    },
    async update(id, payload) {
      return await rackApi.update(id, payload)
    },
    async remove(id) {
      return await rackApi.remove(id)
    },
    async fetchDevices(id) {
      this.devices = await rackApi.devices(id)
      return this.devices
    },
    async fetchUMap(id) {
      this.uMap = await rackApi.uMap(id)
      return this.uMap
    },
    async fetchCandidates(id) {
      this.candidates = await rackApi.candidates(id)
      return this.candidates
    },
    async mount(id, payload) {
      return await rackApi.mount(id, payload)
    },
    async unmount(id, payload) {
      return await rackApi.unmount(id, payload)
    },
  },
})
