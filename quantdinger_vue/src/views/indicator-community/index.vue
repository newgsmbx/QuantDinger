<template>
  <div class="indicator-community-iframe">
    <iframe
      class="community-iframe"
      :src="url"
      title="Indicator Community"
      frameborder="0"
      referrerpolicy="no-referrer-when-downgrade"
      allow="clipboard-read; clipboard-write; fullscreen"
    />
  </div>
</template>

<script>
export default {
  name: 'IndicatorCommunity',
  data () {
    return {
      url: 'https://www.quantdinger.com'
    }
  }
}
</script>

<style lang="less" scoped>
.indicator-community-iframe {
  position: relative;
  left: -24px;
  top: -24px;
  width: calc(100% + 48px);
  height: calc(100vh - 120px + 48px);
}

.community-iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: transparent;
}
</style>
