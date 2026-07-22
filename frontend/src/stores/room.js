import { defineStore } from 'pinia'
import roomApi from '@/api/room'

// 机房状态：列表 / 详情 / 平面图 / 容量统计。
export const useRoomStore = defineStore('room', {
  state: () => ({
    rooms: [],
    total: 0,
    currentRoom: null,
    stats: null,
    racks: [],
    loading: false,
  }),
  actions: {
    async fetchList(params = {}) {
      this.loading = true
      try {
        const data = await roomApi.list(params)
        this.rooms = data.items || []
        this.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
    async fetchOne(id) {
      this.loading = true
      try {
        this.currentRoom = await roomApi.get(id)
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      return await roomApi.create(payload)
    },
    async update(id, payload) {
      return await roomApi.update(id, payload)
    },
    async remove(id) {
      return await roomApi.remove(id)
    },
    async fetchStats(id) {
      this.stats = await roomApi.stats(id)
      return this.stats
    },
    async fetchRacks(id) {
      // 防御：空 id 或筛选哨兵（SELECT_ALL）不应发起请求，避免无意义的 404。
      if (!id || id === '__all__') {
        this.racks = []
        return this.racks
      }
      this.racks = await roomApi.racks(id)
      return this.racks
    },
  },
})
