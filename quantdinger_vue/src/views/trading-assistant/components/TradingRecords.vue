<template>
  <div class="trading-records">
    <div v-if="records.length === 0 && !loading" class="empty-state">
      <a-empty :description="$t('trading-assistant.table.noPositions')" />
    </div>
    <a-table
      v-else
      :columns="columns"
      :data-source="records"
      :loading="loading"
      :pagination="{ pageSize: 10 }"
      size="small"
      rowKey="id"
      :scroll="{ x: 800 }"
    >
      <template slot="type" slot-scope="text">
        <a-tag :color="getTradeTypeColor(text)">
          {{ getTradeTypeText(text) }}
        </a-tag>
      </template>
      <template slot="price" slot-scope="text">
        ${{ parseFloat(text).toFixed(4) }}
      </template>
      <template slot="amount" slot-scope="text">
        {{ parseFloat(text).toFixed(4) }}
      </template>
      <template slot="value" slot-scope="text">
        ${{ parseFloat(text).toFixed(2) }}
      </template>
      <template slot="profit" slot-scope="text">
        <span :style="{ color: text > 0 ? '#52c41a' : text < 0 ? '#f5222d' : '#666' }">
          {{ formatMoney(text) }}
        </span>
      </template>
      <template slot="time" slot-scope="text, record">
        {{ formatTime(record.created_at || text) }}
      </template>
    </a-table>
  </div>
</template>

<script>
import { getStrategyTrades } from '@/api/strategy'

export default {
  name: 'TradingRecords',
  props: {
    strategyId: {
      type: Number,
      required: true
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  computed: {
    columns () {
      return [
        {
          title: this.$t('trading-assistant.table.time'),
          dataIndex: 'created_at',
          key: 'created_at',
          width: 180,
          scopedSlots: { customRender: 'time' }
        },
        {
          title: this.$t('dashboard.indicator.backtest.tradeType'),
          dataIndex: 'type',
          key: 'type',
          width: 140,
          scopedSlots: { customRender: 'type' }
        },
        {
          title: this.$t('trading-assistant.table.price'),
          dataIndex: 'price',
          key: 'price',
          width: 120,
          scopedSlots: { customRender: 'price' }
        },
        {
          title: this.$t('trading-assistant.table.amount'),
          dataIndex: 'amount',
          key: 'amount',
          width: 120,
          scopedSlots: { customRender: 'amount' }
        },
        {
          title: this.$t('trading-assistant.table.value'),
          dataIndex: 'value',
          key: 'value',
          width: 120,
          scopedSlots: { customRender: 'value' }
        },
        {
          title: this.$t('dashboard.indicator.backtest.profit'),
          dataIndex: 'profit',
          key: 'profit',
          width: 120,
          scopedSlots: { customRender: 'profit' }
        },
        {
          title: this.$t('trading-assistant.table.commission'),
          dataIndex: 'commission',
          key: 'commission',
          width: 100
        }
      ]
    }
  },
  data () {
    return {
      records: []
    }
  },
  watch: {
    strategyId: {
      handler (val) {
        if (val) {
          this.loadRecords()
        }
      },
      immediate: true
    }
  },
  methods: {
    async loadRecords () {
      if (!this.strategyId) return

      try {
        const res = await getStrategyTrades(this.strategyId)
        if (res.code === 1) {
          // 确保数据格式正确
          this.records = (res.data.trades || []).map(trade => ({
            ...trade,
            // 确保时间字段存在
            time: trade.created_at || trade.time
          }))
        } else {
          this.$message.error(res.msg || this.$t('trading-assistant.messages.loadTradesFailed'))
        }
      } catch (error) {
      }
    },
    formatTime (time) {
      if (!time) return '--'

      try {
        // 只处理时间戳格式（数字或字符串数字）
        if (typeof time !== 'number' && (typeof time !== 'string' || !/^\d+$/.test(time))) {
          return '--'
        }

        // 转换为数字
        const timestamp = typeof time === 'string' ? parseInt(time, 10) : time

        // 判断是秒级还是毫秒级时间戳
        // 如果时间戳小于 1e12，认为是秒级，需要乘以 1000
        // 如果大于等于 1e12，认为是毫秒级
        const timestampMs = timestamp < 1e12 ? timestamp * 1000 : timestamp
        const date = new Date(timestampMs)

        // 检查日期是否有效
        if (isNaN(date.getTime())) {
          return '--'
        }

        // 使用24小时制格式化时间
        const locale = this.$i18n.locale || 'zh-CN'
        const localeMap = {
          'zh-CN': 'zh-CN',
          'zh-TW': 'zh-TW',
          'en-US': 'en-US'
        }
        return date.toLocaleString(localeMap[locale] || 'zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false
        })
      } catch (e) {
        return '--'
      }
    },
    // 获取交易类型颜色
    getTradeTypeColor (type) {
      const colorMap = {
        // 旧格式
        'buy': 'green',
        'sell': 'red',
        'liquidation': 'orange',
        // 新格式 - 做多
        'open_long': 'green',
        'add_long': 'cyan',
        'close_long': 'orange',
        'close_long_stop': 'red',
        'close_long_profit': 'lime',
        // 新格式 - 做空
        'open_short': 'red',
        'add_short': 'magenta',
        'close_short': 'blue',
        'close_short_stop': 'red',
        'close_short_profit': 'cyan'
      }
      return colorMap[type] || 'default'
    },
    // 获取交易类型文本
    getTradeTypeText (type) {
      const textMap = {
        // 旧格式
        'buy': this.$t('dashboard.indicator.backtest.buy'),
        'sell': this.$t('dashboard.indicator.backtest.sell'),
        'liquidation': this.$t('dashboard.indicator.backtest.liquidation'),
        // 新格式 - 做多
        'open_long': this.$t('dashboard.indicator.backtest.openLong'),
        'add_long': this.$t('dashboard.indicator.backtest.addLong'),
        'close_long': this.$t('dashboard.indicator.backtest.closeLong'),
        'close_long_stop': this.$t('dashboard.indicator.backtest.closeLongStop'),
        'close_long_profit': this.$t('dashboard.indicator.backtest.closeLongProfit'),
        // 新格式 - 做空
        'open_short': this.$t('dashboard.indicator.backtest.openShort'),
        'add_short': this.$t('dashboard.indicator.backtest.addShort'),
        'close_short': this.$t('dashboard.indicator.backtest.closeShort'),
        'close_short_stop': this.$t('dashboard.indicator.backtest.closeShortStop'),
        'close_short_profit': this.$t('dashboard.indicator.backtest.closeShortProfit')
      }
      return textMap[type] || type
    },
    // 格式化金额（盈亏）
    formatMoney (value) {
      if (value === null || value === undefined) return '--'
      // 正数显示+，负数显示-
      const sign = value >= 0 ? '+' : '-'
      return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    }
  }
}
</script>

<style lang="less" scoped>
.trading-records {
  width: 100%;
  min-height: 300px;
  padding: 0;
  overflow-x: visible;
  overflow-y: visible;
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    padding: 40px 0;
  }
  ::v-deep .ant-spin-nested-loading {
    overflow-x: visible;
  }

  ::v-deep .ant-spin-container {
    overflow-x: visible;
  }

  ::v-deep .ant-table-wrapper {
    overflow-x: visible;
    // 自定义细滚动条
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 0, 0, 0.2) transparent;
    &::-webkit-scrollbar {
      height: 6px;
      width: 6px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
      border-radius: 3px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 3px;
      &:hover {
        background: rgba(0, 0, 0, 0.3);
      }
    }
  }

  ::v-deep .ant-table {
    font-size: 13px;
    color: #333;
  }

  ::v-deep .ant-table-container {
    overflow-x: visible;
  }

  ::v-deep .ant-table-body {
    overflow-x: auto;
    overflow-y: visible;
    // 自定义细滚动条
    scrollbar-width: thin; // Firefox - 细滚动条
    scrollbar-color: rgba(0, 0, 0, 0.2) transparent; // Firefox - 滑块颜色和轨道颜色
    &::-webkit-scrollbar {
      height: 6px; // 横向滚动条高度
      width: 6px; // 纵向滚动条宽度
    }
    &::-webkit-scrollbar-track {
      background: transparent; // 轨道背景透明
      border-radius: 3px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.2); // 滑块颜色
      border-radius: 3px;
      &:hover {
        background: rgba(0, 0, 0, 0.3); // 悬停时颜色
      }
    }
  }

  // 表格容器的滚动条样式
  ::v-deep .ant-table-container {
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 0, 0, 0.2) transparent;
    &::-webkit-scrollbar {
      height: 6px;
      width: 6px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
      border-radius: 3px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 3px;
      &:hover {
        background: rgba(0, 0, 0, 0.3);
      }
    }
  }

  // 所有可能的表格滚动容器的滚动条样式
  ::v-deep .ant-table-content {
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 0, 0, 0.2) transparent;
    &::-webkit-scrollbar {
      height: 6px;
      width: 6px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
      border-radius: 3px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 3px;
      &:hover {
        background: rgba(0, 0, 0, 0.3);
      }
    }
  }

  // 防止单元格折行，触发横向滚动
  ::v-deep .ant-table-thead > tr > th,
  ::v-deep .ant-table-tbody > tr > td {
    white-space: nowrap;
  }

  ::v-deep .ant-table-thead > tr > th {
    background: #fafafa;
    font-weight: 600;
    color: #333;
    border-bottom: 1px solid #e8e8e8;
  }

  ::v-deep .ant-table-tbody > tr > td {
    padding: 12px 16px;
    color: #333;
    border-bottom: 1px solid #e8e8e8;
  }

  // 暗黑主题适配
  &.theme-dark,
  .theme-dark & {
    ::v-deep .ant-table {
      background: #1e222d !important;
      color: #d1d4dc !important;
    }

    ::v-deep .ant-table-thead > tr > th {
      background: #2a2e39 !important;
      color: #d1d4dc !important;
      border-bottom-color: #363c4e !important;
      font-weight: 600;
    }

    ::v-deep .ant-table-tbody > tr > td {
      background: #1e222d !important;
      color: #d1d4dc !important;
      border-bottom-color: #363c4e !important;
    }

    ::v-deep .ant-table-tbody > tr:hover > td {
      background: #2a2e39 !important;
    }

    ::v-deep .ant-table-tbody > tr > td span {
      color: #d1d4dc !important;
    }
  }

  ::v-deep .ant-table-tbody > tr:hover > td {
    background: #fafafa;
  }

  // 移动端适配
  @media (max-width: 768px) {
    min-height: 200px;
    overflow-x: visible;

    ::v-deep .ant-table {
      font-size: 12px;
    }

    // 移动端也使用细滚动条
    ::v-deep .ant-table-body,
    ::v-deep .ant-table-container,
    ::v-deep .ant-table-wrapper {
      scrollbar-width: thin;
      scrollbar-color: rgba(0, 0, 0, 0.2) transparent;
      &::-webkit-scrollbar {
        height: 4px;
        width: 4px;
      }
      &::-webkit-scrollbar-track {
        background: transparent;
        border-radius: 2px;
      }
      &::-webkit-scrollbar-thumb {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 2px;
        &:hover {
          background: rgba(0, 0, 0, 0.3);
        }
      }
    }

    ::v-deep .ant-table-thead > tr > th {
      padding: 8px 10px;
      font-size: 11px;
      white-space: nowrap;
    }

    ::v-deep .ant-table-tbody > tr > td {
      padding: 8px 10px;
      font-size: 11px;
      white-space: nowrap;
    }

    ::v-deep .ant-pagination {
      margin-top: 12px;
      text-align: center;

      .ant-pagination-item,
      .ant-pagination-prev,
      .ant-pagination-next {
        margin: 0 2px;
        min-width: 28px;
        height: 28px;
        line-height: 26px;
        font-size: 12px;
      }
    }
  }

  @media (max-width: 480px) {
    ::v-deep .ant-table {
      font-size: 11px;
    }

    ::v-deep .ant-table-thead > tr > th {
      padding: 6px 8px;
      font-size: 10px;
    }

    ::v-deep .ant-table-tbody > tr > td {
      padding: 6px 8px;
      font-size: 10px;
    }
  }
}

// 暗黑主题 - 在 scoped 中处理，确保优先级足够高
</style>

<style lang="less">
// 暗黑主题适配 - 使用最高优先级的选择器覆盖 scoped 样式
// 关键：必须使用与 scoped 样式完全相同的选择器结构，加上 theme-dark 前缀
.theme-dark .trading-records .ant-table-tbody > tr > td,
.theme-dark .trading-records[data-v] .ant-table-tbody > tr > td,
body.dark .trading-records .ant-table-tbody > tr > td,
body.realdark .trading-records .ant-table-tbody > tr > td {
  color: #d1d4dc !important;
  background: #1e222d !important;
  border-bottom-color: #363c4e !important;
}

.theme-dark .trading-records .ant-table-thead > tr > th,
.theme-dark .trading-records[data-v] .ant-table-thead > tr > th,
body.dark .trading-records .ant-table-thead > tr > th,
body.realdark .trading-records .ant-table-thead > tr > th {
  background: #2a2e39 !important;
  color: #d1d4dc !important;
  border-bottom-color: #363c4e !important;
  font-weight: 600 !important;
}

.theme-dark .trading-records .ant-table,
.theme-dark .trading-records[data-v] .ant-table,
body.dark .trading-records .ant-table,
body.realdark .trading-records .ant-table {
  background: #1e222d !important;
  color: #d1d4dc !important;
}

.theme-dark .trading-records .ant-table-tbody > tr > td *,
.theme-dark .trading-records[data-v] .ant-table-tbody > tr > td *,
body.dark .trading-records .ant-table-tbody > tr > td *,
body.realdark .trading-records .ant-table-tbody > tr > td * {
  color: #d1d4dc !important;
}

.theme-dark .trading-records .ant-table-tbody > tr:hover > td,
.theme-dark .trading-records[data-v] .ant-table-tbody > tr:hover > td,
body.dark .trading-records .ant-table-tbody > tr:hover > td,
body.realdark .trading-records .ant-table-tbody > tr:hover > td {
  background: #2a2e39 !important;
}

// 确保表头文字可见
.theme-dark .trading-records .ant-table-thead > tr > th,
.theme-dark .trading-records[data-v] .ant-table-thead > tr > th,
body.dark .trading-records .ant-table-thead > tr > th,
body.realdark .trading-records .ant-table-thead > tr > th {
  .ant-table-column-title {
    color: #d1d4dc !important;
  }
}

.theme-dark .trading-records[data-v-8a68b65a] .ant-table-tbody > tr:hover > td {
  background: #2a2e39 !important;
}

// body.dark 和 body.realdark 支持
body.dark .trading-records[data-v-8a68b65a] .ant-table-tbody > tr > td,
body.realdark .trading-records[data-v-8a68b65a] .ant-table-tbody > tr > td {
  color: #d1d4dc !important;
  background: #1e222d !important;
  border-bottom-color: #363c4e !important;
}

body.dark .trading-records[data-v-8a68b65a] .ant-table-thead > tr > th,
body.realdark .trading-records[data-v-8a68b65a] .ant-table-thead > tr > th {
  background: #2a2e39 !important;
  color: #d1d4dc !important;
  border-bottom-color: #363c4e !important;
}

// 通用后备选择器（如果 data-v 值变化）
.theme-dark .trading-records[data-v] .ant-table-tbody > tr > td,
body.dark .trading-records[data-v] .ant-table-tbody > tr > td,
body.realdark .trading-records[data-v] .ant-table-tbody > tr > td {
  color: #d1d4dc !important;
  background: #1e222d !important;
  border-bottom-color: #363c4e !important;
}

.theme-dark .trading-records[data-v] .ant-table-thead > tr > th,
body.dark .trading-records[data-v] .ant-table-thead > tr > th,
body.realdark .trading-records[data-v] .ant-table-thead > tr > th {
  background: #2a2e39 !important;
  color: #d1d4dc !important;
  border-bottom-color: #363c4e !important;
}

// 分页器样式
.theme-dark .trading-records[data-v-8a68b65a] .ant-pagination-item,
body.dark .trading-records[data-v-8a68b65a] .ant-pagination-item,
body.realdark .trading-records[data-v-8a68b65a] .ant-pagination-item {
  background: #1e222d !important;
  border-color: #363c4e !important;

  a {
    color: #d1d4dc !important;
  }

  &:hover {
    border-color: #1890ff !important;

    a {
      color: #1890ff !important;
    }
  }
}

.theme-dark .trading-records[data-v-8a68b65a] .ant-pagination-item-active,
body.dark .trading-records[data-v-8a68b65a] .ant-pagination-item-active,
body.realdark .trading-records[data-v-8a68b65a] .ant-pagination-item-active {
  background: #1890ff !important;
  border-color: #1890ff !important;

  a {
    color: #fff !important;
  }
}

.theme-dark .trading-records[data-v-8a68b65a] .ant-pagination-prev .ant-pagination-item-link,
.theme-dark .trading-records[data-v-8a68b65a] .ant-pagination-next .ant-pagination-item-link,
body.dark .trading-records[data-v-8a68b65a] .ant-pagination-prev .ant-pagination-item-link,
body.dark .trading-records[data-v-8a68b65a] .ant-pagination-next .ant-pagination-item-link,
body.realdark .trading-records[data-v-8a68b65a] .ant-pagination-prev .ant-pagination-item-link,
body.realdark .trading-records[data-v-8a68b65a] .ant-pagination-next .ant-pagination-item-link {
  background: #1e222d !important;
  border-color: #363c4e !important;
  color: #d1d4dc !important;
}

.theme-dark .trading-records[data-v-8a68b65a] .ant-pagination-prev:hover .ant-pagination-item-link,
.theme-dark .trading-records[data-v-8a68b65a] .ant-pagination-next:hover .ant-pagination-item-link,
body.dark .trading-records[data-v-8a68b65a] .ant-pagination-prev:hover .ant-pagination-item-link,
body.dark .trading-records[data-v-8a68b65a] .ant-pagination-next:hover .ant-pagination-item-link,
body.realdark .trading-records[data-v-8a68b65a] .ant-pagination-prev:hover .ant-pagination-item-link,
body.realdark .trading-records[data-v-8a68b65a] .ant-pagination-next:hover .ant-pagination-item-link {
  border-color: #1890ff !important;
  color: #1890ff !important;
}

// 通用后备选择器
.theme-dark .trading-records[data-v] .ant-pagination-item,
body.dark .trading-records[data-v] .ant-pagination-item,
body.realdark .trading-records[data-v] .ant-pagination-item {
  background: #1e222d !important;
  border-color: #363c4e !important;

  a {
    color: #d1d4dc !important;
  }

  &:hover {
    border-color: #1890ff !important;

    a {
      color: #1890ff !important;
    }
  }
}

.theme-dark .trading-records[data-v] .ant-pagination-item-active,
body.dark .trading-records[data-v] .ant-pagination-item-active,
body.realdark .trading-records[data-v] .ant-pagination-item-active {
  background: #1890ff !important;
  border-color: #1890ff !important;

  a {
    color: #fff !important;
  }
}

.theme-dark .trading-records[data-v] .ant-pagination-prev .ant-pagination-item-link,
.theme-dark .trading-records[data-v] .ant-pagination-next .ant-pagination-item-link,
body.dark .trading-records[data-v] .ant-pagination-prev .ant-pagination-item-link,
body.dark .trading-records[data-v] .ant-pagination-next .ant-pagination-item-link,
body.realdark .trading-records[data-v] .ant-pagination-prev .ant-pagination-item-link,
body.realdark .trading-records[data-v] .ant-pagination-next .ant-pagination-item-link {
  background: #1e222d !important;
  border-color: #363c4e !important;
  color: #d1d4dc !important;
}

.theme-dark .trading-records[data-v] .ant-pagination-prev:hover .ant-pagination-item-link,
.theme-dark .trading-records[data-v] .ant-pagination-next:hover .ant-pagination-item-link,
body.dark .trading-records[data-v] .ant-pagination-prev:hover .ant-pagination-item-link,
body.dark .trading-records[data-v] .ant-pagination-next:hover .ant-pagination-item-link,
body.realdark .trading-records[data-v] .ant-pagination-prev:hover .ant-pagination-item-link,
body.realdark .trading-records[data-v] .ant-pagination-next:hover .ant-pagination-item-link {
  border-color: #1890ff !important;
  color: #1890ff !important;
}

// 暗黑主题滚动条样式
.theme-dark .trading-records[data-v-8a68b65a] .ant-table-body,
.theme-dark .trading-records[data-v-8a68b65a] .ant-table-container,
.theme-dark .trading-records[data-v-8a68b65a] .ant-table-content,
.theme-dark .trading-records[data-v-8a68b65a] .ant-table-wrapper,
body.dark .trading-records[data-v-8a68b65a] .ant-table-body,
body.dark .trading-records[data-v-8a68b65a] .ant-table-container,
body.dark .trading-records[data-v-8a68b65a] .ant-table-content,
body.dark .trading-records[data-v-8a68b65a] .ant-table-wrapper,
body.realdark .trading-records[data-v-8a68b65a] .ant-table-body,
body.realdark .trading-records[data-v-8a68b65a] .ant-table-container,
body.realdark .trading-records[data-v-8a68b65a] .ant-table-content,
body.realdark .trading-records[data-v-8a68b65a] .ant-table-wrapper {
  scrollbar-width: thin;
  scrollbar-color: rgba(209, 212, 220, 0.3) transparent;
  &::-webkit-scrollbar {
    height: 6px;
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
    border-radius: 3px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(209, 212, 220, 0.3);
    border-radius: 3px;
    &:hover {
      background: rgba(209, 212, 220, 0.5);
    }
  }
}

// 通用后备选择器
.theme-dark .trading-records[data-v] .ant-table-body,
.theme-dark .trading-records[data-v] .ant-table-container,
.theme-dark .trading-records[data-v] .ant-table-content,
.theme-dark .trading-records[data-v] .ant-table-wrapper,
body.dark .trading-records[data-v] .ant-table-body,
body.dark .trading-records[data-v] .ant-table-container,
body.dark .trading-records[data-v] .ant-table-content,
body.dark .trading-records[data-v] .ant-table-wrapper,
body.realdark .trading-records[data-v] .ant-table-body,
body.realdark .trading-records[data-v] .ant-table-container,
body.realdark .trading-records[data-v] .ant-table-content,
body.realdark .trading-records[data-v] .ant-table-wrapper {
  scrollbar-width: thin;
  scrollbar-color: rgba(209, 212, 220, 0.3) transparent;
  &::-webkit-scrollbar {
    height: 6px;
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
    border-radius: 3px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(209, 212, 220, 0.3);
    border-radius: 3px;
    &:hover {
      background: rgba(209, 212, 220, 0.5);
    }
  }
}
</style>

<style lang="less">
// 暗黑主题适配 - 使用全局样式确保能够覆盖
.theme-dark .trading-records {
  ::v-deep .ant-table {
    background: #1e222d !important;
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table table {
    background: #1e222d !important;
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-thead > tr > th {
    background: #2a2e39 !important;
    color: #d1d4dc !important;
    border-bottom-color: #363c4e !important;
  }

  ::v-deep .ant-table-tbody {
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-tbody > tr > td {
    background: #1e222d !important;
    color: #d1d4dc !important;
    border-bottom-color: #363c4e !important;
  }

  ::v-deep .ant-table-tbody > tr > td,
  ::v-deep .ant-table-tbody > tr > td span,
  ::v-deep .ant-table-tbody > tr > td div,
  ::v-deep .ant-table-tbody > tr > td *:not(.ant-tag) {
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-tbody > tr:hover > td {
    background: #2a2e39 !important;
  }

  ::v-deep .ant-table-placeholder {
    background: #1e222d !important;
    color: #868993 !important;
  }

  // 暗黑主题滚动条样式
  ::v-deep .ant-table-body,
  ::v-deep .ant-table-container,
  ::v-deep .ant-table-content,
  ::v-deep .ant-table-wrapper {
    scrollbar-width: thin;
    scrollbar-color: rgba(209, 212, 220, 0.3) transparent;
    &::-webkit-scrollbar {
      height: 6px;
      width: 6px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
      border-radius: 3px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(209, 212, 220, 0.3);
      border-radius: 3px;
      &:hover {
        background: rgba(209, 212, 220, 0.5);
      }
    }
  }

  ::v-deep .ant-pagination {
    .ant-pagination-item {
      background: #1e222d !important;
      border-color: #363c4e !important;

      a {
        color: #d1d4dc !important;
      }

      &:hover {
        border-color: #1890ff !important;

        a {
          color: #1890ff !important;
        }
      }
    }

    .ant-pagination-item-active {
      background: #1890ff !important;
      border-color: #1890ff !important;

      a {
        color: #fff !important;
      }
    }

    .ant-pagination-prev,
    .ant-pagination-next {
      .ant-pagination-item-link {
        background: #1e222d !important;
        border-color: #363c4e !important;
        color: #d1d4dc !important;
      }

      &:hover .ant-pagination-item-link {
        border-color: #1890ff !important;
        color: #1890ff !important;
      }
    }

    .ant-pagination-options {
      .ant-select {
        .ant-select-selector {
          background: #1e222d !important;
          border-color: #363c4e !important;
          color: #d1d4dc !important;
        }
      }
    }
  }
}

body.dark .trading-records,
body.realdark .trading-records {
  ::v-deep .ant-table {
    background: #1e222d !important;
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table table {
    background: #1e222d !important;
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-thead > tr > th {
    background: #2a2e39 !important;
    color: #d1d4dc !important;
    border-bottom-color: #363c4e !important;
  }

  ::v-deep .ant-table-tbody {
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-tbody > tr > td {
    background: #1e222d !important;
    color: #d1d4dc !important;
    border-bottom-color: #363c4e !important;
  }

  ::v-deep .ant-table-tbody > tr > td,
  ::v-deep .ant-table-tbody > tr > td span,
  ::v-deep .ant-table-tbody > tr > td div,
  ::v-deep .ant-table-tbody > tr > td *:not(.ant-tag) {
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-tbody > tr:hover > td {
    background: #2a2e39 !important;
  }

  ::v-deep .ant-table-placeholder {
    background: #1e222d !important;
    color: #868993 !important;
  }

  // 暗黑主题滚动条样式
  ::v-deep .ant-table-body,
  ::v-deep .ant-table-container,
  ::v-deep .ant-table-content,
  ::v-deep .ant-table-wrapper {
    scrollbar-width: thin;
    scrollbar-color: rgba(209, 212, 220, 0.3) transparent;
    &::-webkit-scrollbar {
      height: 6px;
      width: 6px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
      border-radius: 3px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(209, 212, 220, 0.3);
      border-radius: 3px;
      &:hover {
        background: rgba(209, 212, 220, 0.5);
      }
    }
  }

  ::v-deep .ant-pagination {
    .ant-pagination-item {
      background: #1e222d !important;
      border-color: #363c4e !important;

      a {
        color: #d1d4dc !important;
      }

      &:hover {
        border-color: #1890ff !important;

        a {
          color: #1890ff !important;
        }
      }
    }

    .ant-pagination-item-active {
      background: #1890ff !important;
      border-color: #1890ff !important;

      a {
        color: #fff !important;
      }
    }

    .ant-pagination-prev,
    .ant-pagination-next {
      .ant-pagination-item-link {
        background: #1e222d !important;
        border-color: #363c4e !important;
        color: #d1d4dc !important;
      }

      &:hover .ant-pagination-item-link {
        border-color: #1890ff !important;
        color: #1890ff !important;
      }
    }

    .ant-pagination-options {
      .ant-select {
        .ant-select-selector {
          background: #1e222d !important;
          border-color: #363c4e !important;
          color: #d1d4dc !important;
        }
      }
    }
  }
}
</style>

<style lang="less">
/* 暗黑主题适配 - 使用更高优先级的选择器 */
.theme-dark .trading-records,
.theme-dark .trading-records *,
body.dark .trading-records,
body.dark .trading-records *,
body.realdark .trading-records,
body.realdark .trading-records * {
  ::v-deep .ant-table {
    background: #1e222d !important;
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table table {
    background: #1e222d !important;
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-thead > tr > th {
    background: #2a2e39 !important;
    color: #d1d4dc !important;
    border-bottom-color: #363c4e !important;
  }

  ::v-deep .ant-table-tbody {
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-tbody > tr > td {
    background: #1e222d !important;
    color: #d1d4dc !important;
    border-bottom-color: #363c4e !important;
  }

  ::v-deep .ant-table-tbody > tr > td,
  ::v-deep .ant-table-tbody > tr > td span,
  ::v-deep .ant-table-tbody > tr > td div,
  ::v-deep .ant-table-tbody > tr > td *:not(.ant-tag) {
    color: #d1d4dc !important;
  }

  ::v-deep .ant-table-tbody > tr:hover > td {
    background: #2a2e39 !important;
  }

  ::v-deep .ant-table-placeholder {
    background: #1e222d !important;
    color: #868993 !important;
  }

  ::v-deep .ant-pagination {
    .ant-pagination-item {
      background: #1e222d !important;
      border-color: #363c4e !important;

      a {
        color: #d1d4dc !important;
      }

      &:hover {
        border-color: #1890ff !important;

        a {
          color: #1890ff !important;
        }
      }
    }

    .ant-pagination-item-active {
      background: #1890ff !important;
      border-color: #1890ff !important;

      a {
        color: #fff !important;
      }
    }

    .ant-pagination-prev,
    .ant-pagination-next {
      .ant-pagination-item-link {
        background: #1e222d !important;
        border-color: #363c4e !important;
        color: #d1d4dc !important;
      }

      &:hover .ant-pagination-item-link {
        border-color: #1890ff !important;
        color: #1890ff !important;
      }
    }

    .ant-pagination-options {
      .ant-select {
        .ant-select-selector {
          background: #1e222d !important;
          border-color: #363c4e !important;
          color: #d1d4dc !important;
        }
      }
    }
  }
}
</style>
