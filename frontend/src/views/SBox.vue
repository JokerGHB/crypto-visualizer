<script setup lang="ts">
/** S 盒独立页面 */
import SBoxPanel from '../components/SBoxPanel.vue';
</script>

<template>
  <div class="sbox-view">
    <SBoxPanel />
  </div>
</template>

<style scoped>
.sbox-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 20px 48px;
}
</style>