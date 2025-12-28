
<template>
  <div class="dashboard-container" :class="{ 'theme-dark': isDarkTheme }">
    <!-- 顶部卡片区域 -->
    <a-row :gutter="[12, 12]">
      <!-- 总权益 -->
      <a-col :xs="12" :sm="12" :md="6">
        <div class="dashboard-card primary-card">
          <div class="card-icon">
            <a-icon type="wallet" />
          </div>
          <div class="card-content">
            <div class="card-label">{{ $t('dashboard.totalEquity') }}</div>
            <div class="card-value">
              <span class="currency">$</span>
              <span class="number">{{ formatNumber(summary.total_equity) }}</span>
            </div>
            <!-- <div class="card-trend">
              <span class="trend-label">Daily Change</span>
              <span class="trend-value positive">+2.4%</span>
            </div> -->
          </div>
        </div>
      </a-col>

      <!-- 总盈亏 -->
      <a-col :xs="12" :sm="12" :md="6">
        <div class="dashboard-card" :class="summary.total_pnl >= 0 ? 'success-card' : 'danger-card'">
          <div class="card-icon">
            <a-icon type="line-chart" />
          </div>
          <div class="card-content">
            <div class="card-label">{{ $t('dashboard.totalPnL') }}</div>
            <div class="card-value">
              <span class="currency">$</span>
              <span class="number">{{ formatNumber(summary.total_pnl) }}</span>
            </div>
          </div>
        </div>
      </a-col>

      <!-- 运行中 AI 策略 -->
      <a-col :xs="12" :sm="12" :md="6">
        <div class="dashboard-card info-card clickable-card" @click="$router.push('/ai-trading-assistant')">
          <div class="card-icon">
            <a-icon type="thunderbolt" theme="filled" />
          </div>
          <div class="card-content">
            <div class="card-label">{{ $t('dashboard.aiStrategies') }}</div>
            <div class="card-value">
              <span class="number">{{ summary.ai_strategy_count }}</span>
              <span class="unit">{{ $t('dashboard.running') }}</span>
            </div>
          </div>
        </div>
      </a-col>

      <!-- 运行中 指标策略 -->
      <a-col :xs="12" :sm="12" :md="6">
        <div class="dashboard-card warning-card clickable-card" @click="$router.push('/trading-assistant')">
          <div class="card-icon">
            <a-icon type="bar-chart" />
          </div>
          <div class="card-content">
            <div class="card-label">{{ $t('dashboard.indicatorStrategies') }}</div>
            <div class="card-value">
              <span class="number">{{ summary.indicator_strategy_count }}</span>
              <span class="unit">{{ $t('dashboard.running') }}</span>
            </div>
          </div>
        </div>
      </a-col>
    </a-row>

    <!-- 图表区域 -->
    <a-row :gutter="[24, 24]" style="margin-top: 24px;">
      <!-- 历史盈亏曲线 -->
      <a-col :xs="24" :lg="16">
        <a-card :bordered="false" class="chart-card" :title="$t('dashboard.pnlHistory')">
          <div ref="pnlChart" style="height: 350px;"></div>
        </a-card>
      </a-col>

      <!-- 策略盈亏占比 -->
      <a-col :xs="24" :lg="8">
        <a-card :bordered="false" class="chart-card" :title="$t('dashboard.strategyPerformance')">
          <div ref="pieChart" style="height: 350px;"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 最近交易记录 & 当前持仓 -->
    <a-row :gutter="[24, 24]" style="margin-top: 24px;">
      <!-- 当前持仓 -->
      <a-col :xs="24" :lg="12">
        <a-card :bordered="false" class="table-card" :title="$t('dashboard.currentPositions')">
          <a-table
            :columns="positionColumns"
            :data-source="summary.current_positions"
            rowKey="id"
            :pagination="false"
            size="small"
            :scroll="{ x: 'max-content' }"
          >
            <template slot="symbol" slot-scope="text, record">
              <div>{{ text }}</div>
              <div style="font-size: 12px; color: #999;">{{ record.strategy_name }}</div>
            </template>
            <template slot="side" slot-scope="text">
              <a-tag :color="text === 'long' ? 'green' : 'red'">
                {{ text.toUpperCase() }}
              </a-tag>
            </template>
            <template slot="unrealized_pnl" slot-scope="text, record">
              <div :class="text >= 0 ? 'text-success' : 'text-danger'">
                {{ text >= 0 ? '+' : '' }}{{ formatNumber(text) }}
              </div>
              <div :class="record.pnl_percent >= 0 ? 'text-success' : 'text-danger'" style="font-size: 12px;">
                {{ record.pnl_percent >= 0 ? '+' : '' }}{{ formatNumber(record.pnl_percent) }}%
              </div>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <!-- 最近交易 -->
      <a-col :xs="24" :lg="12">
        <a-card :bordered="false" class="table-card" :title="$t('dashboard.recentTrades')">
          <a-table
            :columns="columns"
            :data-source="summary.recent_trades"
            rowKey="id"
            :pagination="{ pageSize: 10 }"
            size="small"
            :scroll="{ x: 'max-content' }"
          >
            <template slot="type" slot-scope="text">
              <a-tag :color="getTypeColor(text)">
                {{ text.toUpperCase() }}
              </a-tag>
            </template>
            <template slot="profit" slot-scope="text">
              <span :class="text >= 0 ? 'text-success' : 'text-danger'">
                {{ text >= 0 ? '+' : '' }}{{ formatNumber(text) }}
              </span>
            </template>
            <template slot="time" slot-scope="text">
              {{ formatTime(text) }}
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <!-- 订单执行记录 -->
    <a-row :gutter="[24, 24]" style="margin-top: 24px;">
      <a-col :xs="24">
        <a-card :bordered="false" class="table-card" :title="$t('dashboard.pendingOrders')">
          <a-table
            :columns="orderColumns"
            :data-source="pendingOrders"
            rowKey="id"
            :pagination="{
              current: ordersPagination.current,
              pageSize: ordersPagination.pageSize,
              total: ordersPagination.total,
              showSizeChanger: true,
              showTotal: (total) => $t('dashboard.totalOrders', { total })
            }"
            size="small"
            :loading="ordersLoading"
            :scroll="{ x: 1200 }"
            @change="handleOrdersTableChange"
          >
            <template slot="strategy_name" slot-scope="text, record">
              <div>{{ text || '-' }}</div>
              <div style="font-size: 12px; color: #999;">ID: {{ record.strategy_id }}</div>
            </template>
            <template slot="symbol" slot-scope="text">
              <a-tag color="blue">{{ text }}</a-tag>
            </template>
            <template slot="signal_type" slot-scope="text">
              <a-tag :color="getSignalTypeColor(text)">
                {{ getSignalTypeText(text) }}
              </a-tag>
            </template>
            <template slot="exchange" slot-scope="text, record">
              <a-tag
                v-if="(record && (record.exchange_display || record.exchange_id || text))"
                :color="getExchangeTagColor(record.exchange_display || record.exchange_id || text)"
              >
                {{ String(record.exchange_display || record.exchange_id || text).toUpperCase() }}
              </a-tag>
              <span v-else style="color: #999;">-</span>
              <div v-if="record && record.market_type" style="font-size: 12px; color: #999;">
                {{ String(record.market_type).toUpperCase() }}
              </div>
            </template>
            <template slot="notify" slot-scope="text, record">
              <div>
                <template v-for="ch in (record && record.notify_channels ? record.notify_channels : [])">
                  <a-tooltip :key="`${record.id}-${ch}`" :title="String(ch)">
                    <a-icon :type="getNotifyIconType(ch)" style="margin-right: 8px; color: #8c8c8c;" />
                  </a-tooltip>
                </template>
                <span v-if="!record || !record.notify_channels || record.notify_channels.length === 0" style="color: #999;">-</span>
              </div>
            </template>
            <template slot="status" slot-scope="text, record">
              <a-tag :color="getStatusColor(text)">
                {{ getStatusText(text) }}
              </a-tag>
              <div v-if="text === 'failed' && record.error_message" style="margin-top: 4px;">
                <a-tooltip :title="record.error_message">
                  <a-icon type="exclamation-circle" style="color: #f5222d;" />
                  <span style="font-size: 12px; color: #f5222d; margin-left: 4px;">{{ $t('dashboard.viewError') }}</span>
                </a-tooltip>
              </div>
            </template>
            <template slot="amount" slot-scope="text, record">
              <div>{{ formatNumber(text, 8) }}</div>
              <div v-if="record.filled_amount" style="font-size: 12px; color: #999;">
                {{ $t('dashboard.filled') }}: {{ formatNumber(record.filled_amount, 8) }}
              </div>
            </template>
            <template slot="price" slot-scope="text, record">
              <div v-if="record.filled_price">
                {{ formatNumber(record.filled_price) }}
              </div>
              <div v-else style="color: #999;">-</div>
            </template>
            <template slot="created_at" slot-scope="text">
              {{ formatTime(text) }}
            </template>
            <template slot="executed_at" slot-scope="text">
              <span v-if="text">{{ formatTime(text) }}</span>
              <span v-else style="color: #999;">-</span>
            </template>
            <template slot="actions" slot-scope="text, record">
              <a-popconfirm
                :title="$t('dashboard.orderTable.deleteConfirm')"
                :okText="$t('dashboard.orderTable.delete')"
                :cancelText="$t('cancel')"
                @confirm="handleDeletePendingOrder(record)"
              >
                <a-button
                  type="link"
                  size="small"
                  :disabled="record && String(record.status).toLowerCase() === 'processing'"
                >
                  <a-icon type="delete" />
                  {{ $t('dashboard.orderTable.delete') }}
                </a-button>
              </a-popconfirm>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import { getDashboardSummary, getPendingOrders, deletePendingOrder } from '@/api/dashboard'
import { mapState } from 'vuex'

export default {
  name: 'Dashboard',
  data () {
    return {
      summary: {
        ai_strategy_count: 0,
        indicator_strategy_count: 0,
        total_equity: 0,
        total_pnl: 0,
        daily_pnl_chart: [],
        strategy_pnl_chart: [],
        recent_trades: [],
        current_positions: []
      },
      pnlChart: null,
      pieChart: null,
      pendingOrders: [],
      ordersLoading: false,
      ordersPagination: {
        current: 1,
        pageSize: 20,
        total: 0
      }
    }
  },
  computed: {
    ...mapState({
      navTheme: state => state.app.theme
    }),
    isDarkTheme () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    },
    orderStrategyFilters () {
      const list = Array.isArray(this.pendingOrders) ? this.pendingOrders : []
      const map = new Map()
      for (const item of list) {
        const id = item && item.strategy_id
        if (id === undefined || id === null || map.has(String(id))) continue
        const name = (item && item.strategy_name) ? String(item.strategy_name) : ''
        const text = name ? `${name} (ID: ${id})` : `ID: ${id}`
        map.set(String(id), { text, value: String(id) })
      }
      return Array.from(map.values()).sort((a, b) => String(a.text).localeCompare(String(b.text)))
    },
    columns () {
      return [
        {
          title: this.$t('dashboard.table.time'),
          // Backend returns `created_at` (unix timestamp). Use it to avoid empty "-".
          dataIndex: 'created_at',
          scopedSlots: { customRender: 'time' },
          width: 150
        },
        {
          title: this.$t('dashboard.table.symbol'),
          dataIndex: 'symbol'
        },
        {
          title: this.$t('dashboard.table.type'),
          dataIndex: 'type',
          scopedSlots: { customRender: 'type' }
        },
        {
          title: this.$t('dashboard.table.price'),
          dataIndex: 'price',
          customRender: (text) => this.formatNumber(text)
        },
        {
          title: this.$t('dashboard.table.profit'),
          dataIndex: 'profit',
          scopedSlots: { customRender: 'profit' },
          align: 'right'
        }
      ]
    },
    positionColumns () {
      return [
        {
          title: this.$t('dashboard.table.symbol'),
          dataIndex: 'symbol',
          scopedSlots: { customRender: 'symbol' }
        },
        {
          title: this.$t('dashboard.table.side'),
          dataIndex: 'side',
          scopedSlots: { customRender: 'side' }
        },
        {
          title: this.$t('dashboard.table.size'),
          dataIndex: 'size',
          customRender: (text) => this.formatNumber(text, 4)
        },
        {
          title: this.$t('dashboard.table.entryPrice'),
          dataIndex: 'entry_price',
          customRender: (text) => this.formatNumber(text)
        },
        {
          title: this.$t('dashboard.table.pnl'),
          dataIndex: 'unrealized_pnl',
          scopedSlots: { customRender: 'unrealized_pnl' },
          align: 'right'
        }
      ]
    },
    orderColumns () {
      return [
        {
          title: this.$t('dashboard.orderTable.time'),
          dataIndex: 'created_at',
          scopedSlots: { customRender: 'created_at' },
          width: 160
        },
        {
          title: this.$t('dashboard.orderTable.strategy'),
          dataIndex: 'strategy_name',
          scopedSlots: { customRender: 'strategy_name' },
          filters: this.orderStrategyFilters,
          filterMultiple: true,
          onFilter: (value, record) => String(record && record.strategy_id) === String(value),
          width: 150
        },
        {
          title: this.$t('dashboard.orderTable.exchange'),
          dataIndex: 'exchange_id',
          scopedSlots: { customRender: 'exchange' },
          width: 120
        },
        {
          title: this.$t('dashboard.orderTable.notify'),
          dataIndex: 'notify_channels',
          scopedSlots: { customRender: 'notify' },
          width: 140
        },
        {
          title: this.$t('dashboard.orderTable.symbol'),
          dataIndex: 'symbol',
          scopedSlots: { customRender: 'symbol' },
          width: 120
        },
        {
          title: this.$t('dashboard.orderTable.signalType'),
          dataIndex: 'signal_type',
          scopedSlots: { customRender: 'signal_type' },
          width: 120
        },
        {
          title: this.$t('dashboard.orderTable.amount'),
          dataIndex: 'amount',
          scopedSlots: { customRender: 'amount' },
          width: 140
        },
        {
          title: this.$t('dashboard.orderTable.price'),
          dataIndex: 'filled_price',
          scopedSlots: { customRender: 'price' },
          width: 120
        },
        {
          title: this.$t('dashboard.orderTable.status'),
          dataIndex: 'status',
          scopedSlots: { customRender: 'status' },
          width: 150
        },
        {
          title: this.$t('dashboard.orderTable.executedAt'),
          dataIndex: 'executed_at',
          scopedSlots: { customRender: 'executed_at' },
          width: 160
        },
        {
          title: this.$t('dashboard.orderTable.actions'),
          key: 'actions',
          scopedSlots: { customRender: 'actions' },
          width: 110,
          fixed: 'right'
        }
      ]
    }
  },
  mounted () {
    this.fetchData()
    this.fetchPendingOrders()
    window.addEventListener('resize', this.handleResize)
  },
  beforeDestroy () {
    window.removeEventListener('resize', this.handleResize)
    if (this.pnlChart) this.pnlChart.dispose()
    if (this.pieChart) this.pieChart.dispose()
  },
  methods: {
    async fetchData () {
      try {
        const res = await getDashboardSummary()
        if (res.code === 1) {
          this.summary = res.data
          this.$nextTick(() => {
            this.initCharts()
          })
        }
      } catch (e) {
      }
    },
    async fetchPendingOrders (page, pageSize) {
      this.ordersLoading = true
      try {
        const current = page || this.ordersPagination.current || 1
        const size = pageSize || this.ordersPagination.pageSize || 20
        const res = await getPendingOrders({ page: current, pageSize: size })
        if (res.code === 1) {
          const data = res.data || {}
          this.pendingOrders = data.list || []
          this.ordersPagination.current = Number(data.page || current || 1)
          this.ordersPagination.pageSize = Number(data.pageSize || size || 20)
          this.ordersPagination.total = Number(data.total || 0)
        }
      } catch (e) {
        console.error('获取订单列表失败:', e)
      } finally {
        this.ordersLoading = false
      }
    },
    handleOrdersTableChange (pagination) {
      // ant-design-vue Table change: (pagination, filters, sorter, extra)
      const current = (pagination && pagination.current) ? pagination.current : 1
      const pageSize = (pagination && pagination.pageSize) ? pagination.pageSize : (this.ordersPagination.pageSize || 20)
      this.ordersPagination.current = current
      this.ordersPagination.pageSize = pageSize
      this.fetchPendingOrders(current, pageSize)
    },
    getSignalTypeColor (type) {
      if (!type) return 'default'
      type = type.toLowerCase()
      if (type.includes('open_long') || type.includes('add_long')) return 'green'
      if (type.includes('open_short') || type.includes('add_short')) return 'red'
      if (type.includes('close_long')) return 'orange'
      if (type.includes('close_short')) return 'purple'
      return 'blue'
    },
    getSignalTypeText (type) {
      if (!type) return '-'
      const typeMap = {
        'open_long': this.$t('dashboard.signalType.openLong'),
        'open_short': this.$t('dashboard.signalType.openShort'),
        'close_long': this.$t('dashboard.signalType.closeLong'),
        'close_short': this.$t('dashboard.signalType.closeShort'),
        'add_long': this.$t('dashboard.signalType.addLong'),
        'add_short': this.$t('dashboard.signalType.addShort')
      }
      return typeMap[type.toLowerCase()] || type.toUpperCase()
    },
    getStatusColor (status) {
      const colorMap = {
        'pending': 'orange',
        'processing': 'blue',
        'completed': 'green',
        'failed': 'red',
        'cancelled': 'default'
      }
      return colorMap[status] || 'default'
    },
    getStatusText (status) {
      if (!status) return '-'
      const statusMap = {
        'pending': this.$t('dashboard.status.pending'),
        'processing': this.$t('dashboard.status.processing'),
        'completed': this.$t('dashboard.status.completed'),
        'failed': this.$t('dashboard.status.failed'),
        'cancelled': this.$t('dashboard.status.cancelled')
      }
      return statusMap[status.toLowerCase()] || status.toUpperCase()
    },
    getNotifyIconType (channel) {
      const c = String(channel || '').trim().toLowerCase()
      const map = {
        browser: 'bell',
        webhook: 'link',
        // Use stable built-in icons (avoid missing icon names in older antd icon sets).
        discord: 'comment',
        telegram: 'message',
        tg: 'message',
        tele: 'message',
        email: 'mail',
        phone: 'phone'
      }
      return map[c] || 'notification'
    },
    getExchangeTagColor (exchange) {
      const ex = String(exchange || '').trim().toLowerCase()
      const map = {
        binance: 'gold',
        okx: 'purple',
        bitget: 'cyan',
        signal: 'geekblue'
      }
      return map[ex] || 'blue'
    },
    async handleDeletePendingOrder (record) {
      try {
        const id = record && record.id
        if (!id) return
        const res = await deletePendingOrder(id)
        if (res && res.code === 1) {
          this.$message.success(this.$t('dashboard.orderTable.deleteSuccess'))
          // Refresh current page (best-effort)
          this.fetchPendingOrders(this.ordersPagination.current, this.ordersPagination.pageSize)
        } else {
          this.$message.error((res && res.msg) ? String(res.msg) : this.$t('dashboard.orderTable.deleteFailed'))
        }
      } catch (e) {
        this.$message.error(this.$t('dashboard.orderTable.deleteFailed'))
      }
    },
    formatNumber (num, digits = 2) {
      if (num === undefined || num === null) return '0.00'
      return Number(num).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    },
    formatTime (timestamp) {
      if (!timestamp) return '-'
      try {
        // Accept seconds or milliseconds, number or numeric string.
        const raw = typeof timestamp === 'string' ? parseInt(timestamp, 10) : Number(timestamp)
        if (!raw || Number.isNaN(raw)) return '-'
        const ms = raw < 1e12 ? raw * 1000 : raw
        const d = new Date(ms)
        if (isNaN(d.getTime())) return '-'
        return d.toLocaleString()
      } catch (e) {
        return '-'
      }
    },
    getTypeColor (type) {
      if (!type) return 'default'
      type = type.toLowerCase()
      if (type.includes('buy') || type.includes('long')) return 'green'
      if (type.includes('sell') || type.includes('short')) return 'red'
      return 'blue'
    },
    initCharts () {
      this.initPnlChart()
      this.initPieChart()
    },
    initPnlChart () {
      const chartDom = this.$refs.pnlChart
      if (!chartDom) return
      this.pnlChart = echarts.init(chartDom)

      const dates = this.summary.daily_pnl_chart.map(item => item.date)
      const values = this.summary.daily_pnl_chart.map(item => item.profit)

      const option = {
        tooltip: {
          trigger: 'axis'
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLine: {
            lineStyle: { color: this.isDarkTheme ? '#555' : '#ccc' }
          }
        },
        yAxis: {
          type: 'value',
          splitLine: {
            lineStyle: { color: this.isDarkTheme ? '#333' : '#eee' }
          }
        },
        series: [
          {
            name: 'P&L',
            type: 'line',
            data: values,
            smooth: true,
            areaStyle: {
              opacity: 0.3
            },
            itemStyle: {
              color: '#1890ff'
            }
          }
        ]
      }
      this.pnlChart.setOption(option)
    },
    initPieChart () {
      const chartDom = this.$refs.pieChart
      if (!chartDom) return
      this.pieChart = echarts.init(chartDom)

      const data = this.summary.strategy_pnl_chart

      const option = {
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)'
        },
        legend: {
          top: 'bottom',
          left: 'center',
          textStyle: {
            color: this.isDarkTheme ? '#ccc' : '#333'
          }
        },
        series: [
          {
            name: 'Profit by Strategy',
            type: 'pie',
            radius: ['45%', '70%'],
            center: ['50%', '45%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 8,
              borderColor: this.isDarkTheme ? '#1e222d' : '#fff',
              borderWidth: 2
            },
            label: {
              show: false,
              position: 'center'
            },
            emphasis: {
              label: {
                show: true,
                fontSize: 16,
                fontWeight: 'bold',
                color: this.isDarkTheme ? '#fff' : '#333'
              },
              scale: true,
              scaleSize: 10
            },
            labelLine: {
              show: false
            },
            data: data.length > 0 ? data : [{ value: 0, name: 'No Data' }]
          }
        ]
      }
      this.pieChart.setOption(option)
    },
    handleResize () {
      if (this.pnlChart) this.pnlChart.resize()
      if (this.pieChart) this.pieChart.resize()
    }
  }
}
</script>

<style lang="less" scoped>
.dashboard-container {
  padding: 24px;
  background: #f0f2f5;
  min-height: 100vh;

  &.theme-dark {
    background: #131722;

    .dashboard-card {
      background: #1e222d;
      border: 1px solid #2a2e39;

      .card-label { color: #868993; }
      .card-value { color: #d1d4dc; }

      &.primary-card {
        background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
        border: none;
        .card-label, .card-value { color: #fff; }
        .card-icon { color: rgba(255,255,255,0.3); }
      }
    }

    .chart-card, .table-card {
      background: #1e222d;

      ::v-deep .ant-card-head {
        border-bottom: 1px solid #2a2e39;
        color: #d1d4dc;

        .ant-card-head-title {
          color: #d1d4dc;
        }
      }
      ::v-deep .ant-card-body {
        color: #d1d4dc;
      }
      ::v-deep .ant-table {
        color: #d1d4dc;
        background: #1e222d;

        .ant-table-placeholder {
          background: #1e222d;
          border-bottom: 1px solid #2a2e39;
          .ant-empty-description {
            color: #868993;
          }
        }
      }
      ::v-deep .ant-table-body {
        overflow-x: auto;
      }
      ::v-deep .ant-table-scroll {
        .ant-table-body {
          overflow-x: auto;
        }
      }
      ::v-deep .ant-table-thead > tr > th {
        background: #262a35;
        color: #868993;
        border-bottom: 1px solid #2a2e39;
      }
      ::v-deep .ant-table-tbody > tr > td {
        border-bottom: 1px solid #2a2e39;
        color: #d1d4dc;
      }
      ::v-deep .ant-table-tbody > tr:hover > td {
        background: #262a35;
      }
      ::v-deep .ant-pagination {
        color: #d1d4dc;

        .ant-pagination-total-text {
          color: #d1d4dc;
        }
        .ant-pagination-item {
          background: #1e222d;
          border-color: #2a2e39;

          a {
            color: #d1d4dc;
          }

          &:hover {
            border-color: #1890ff;
            a {
              color: #1890ff;
            }
          }

          &.ant-pagination-item-active {
            background: #1890ff;
            border-color: #1890ff;

            a {
              color: #fff;
            }
          }
        }
        .ant-pagination-prev,
        .ant-pagination-next {
          .ant-pagination-item-link {
            background: #1e222d;
            border-color: #2a2e39;
            color: #d1d4dc;

            &:hover {
              border-color: #1890ff;
              color: #1890ff;
            }
          }
        }
        .ant-pagination-options {
          .ant-pagination-options-size-changer {
            .ant-select {
              .ant-select-selector {
                background: #1e222d;
                border-color: #2a2e39;
                color: #d1d4dc;
              }
              .ant-select-selection-item {
                color: #d1d4dc;
              }
            }
          }
          .ant-pagination-options-quick-jumper {
            color: #d1d4dc;

            input {
              background: #1e222d;
              border-color: #2a2e39;
              color: #d1d4dc;

              &::placeholder {
                color: #868993;
              }
            }
          }
        }
      }
    }
  }

  .dashboard-card {
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    display: flex;
    align-items: center;
    position: relative;
    overflow: hidden;
    transition: all 0.3s;
    height: 140px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);

    &.clickable-card {
      cursor: pointer;
      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
      }
      &:active {
        transform: translateY(-2px);
      }
    }

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
    }

    .card-icon {
      position: absolute;
      right: -20px;
      bottom: -20px;
      font-size: 100px;
      opacity: 0.1;
      transform: rotate(-15deg);
    }

    .card-content {
      position: relative;
      z-index: 1;

      .card-label {
        font-size: 14px;
        color: #8c8c8c;
        margin-bottom: 8px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .card-value {
        font-size: 32px;
        font-weight: bold;
        color: #262626;
        display: flex;
        align-items: baseline;

        .currency {
          font-size: 20px;
          margin-right: 4px;
        }

        .unit {
          font-size: 14px;
          color: #8c8c8c;
          margin-left: 8px;
          font-weight: normal;
        }
      }
    }

    &.primary-card {
      background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);

      .card-label { color: rgba(255,255,255,0.8); }
      .card-value { color: #fff; .unit { color: rgba(255,255,255,0.8); } }
      .card-icon { color: #fff; opacity: 0.2; }
    }

    &.success-card {
      border-left: 4px solid #52c41a;
      .card-value { color: #52c41a; }
    }

    &.danger-card {
      border-left: 4px solid #f5222d;
      .card-value { color: #f5222d; }
    }

    &.warning-card {
      border-left: 4px solid #faad14;
      .card-value { color: #faad14; }
    }

    &.info-card {
      border-left: 4px solid #1890ff;
      .card-value { color: #1890ff; }
    }
  }

  .chart-card {
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  }

  .table-card {
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);

    ::v-deep .ant-card-body {
      overflow-x: auto;
    }
    ::v-deep .ant-table-wrapper {
      overflow-x: auto;
    }
    ::v-deep .ant-table-body {
      overflow-x: auto;
      min-width: 100%;
    }
  }

  .text-success { color: #52c41a; }
  .text-danger { color: #f5222d; }

  // 手机端适配
  @media (max-width: 768px) {
    ::v-deep.dashboard-container {
      padding: 0px!important;
    }

    .dashboard-card {
      height: auto;
      min-height: 100px;
      padding: 12px;
      margin-bottom: 0;

      .card-value {
        font-size: 18px;
        flex-wrap: wrap;

        .currency {
          font-size: 14px;
        }

        .number {
          word-break: break-all;
        }

        .unit {
          font-size: 12px;
          margin-left: 4px;
        }
      }

      .card-label {
        font-size: 12px;
        margin-bottom: 4px;
      }

      .card-icon {
        font-size: 60px;
        right: -10px;
        bottom: -10px;
      }
    }

    .chart-card, .table-card {
      margin-bottom: 12px;

      ::v-deep .ant-card-head {
        padding: 0 16px;
        min-height: 48px;

        .ant-card-head-title {
          padding: 12px 0;
          font-size: 16px;
        }
      }

      ::v-deep .ant-card-body {
        padding: 12px;
      }
    }
  }
}
</style>
