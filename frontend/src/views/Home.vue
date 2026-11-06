<script setup lang="ts">
/** 首页：项目简介与三入口 */
import { useRouter } from 'vue-router';

const router = useRouter();

const features = [
  {
    title: '逐步可视化',
    desc: '字节替代、行移位、列混合、轮密钥加四步逐一拆解，状态矩阵逐字节高亮。',
    to: '/playground',
    cta: '开始演示',
  },
  {
    title: '练习模式',
    desc: '三种题型即时判分，答错可直接跳回对应动画步骤复盘。',
    to: '/exercise',
    cta: '去练习',
  },
  {
    title: 'S 盒查询',
    desc: '标准 S 盒与逆 S 盒完整表格，支持悬停提示与按值反查坐标。',
    to: '/sbox',
    cta: '查看 S 盒',
  },
];
</script>

<template>
  <div class="home">
    <section class="hero">
      <h1>密码学算法可视化教学</h1>
      <p class="subtitle">把 AES 的每一步「演」出来，并用 AI 讲清它为什么这样变。</p>
      <p class="meta">
        AES-128 / 192 / 256 · 加解密双向 · 40/48/56 步完整轨迹 · 步骤级 AI 辅导
      </p>
    </section>

    <section class="cards">
      <article v-for="item in features" :key="item.title" class="feature">
        <h3>{{ item.title }}</h3>
        <p>{{ item.desc }}</p>
        <button type="button" class="btn" @click="router.push(item.to)">
          {{ item.cta }}
        </button>
      </article>
    </section>

    <section class="howto">
      <h2>它是怎么工作的</h2>
      <ol>
        <li>
          后端用自研的 AES 引擎算出完整轨迹，每一步都记录状态矩阵的前后快照与逐字节变化依据。
        </li>
        <li>
          前端只消费这份轨迹，因此播放、单步、跳转、练习判分、AI 讲解看到的数据永远一致。
        </li>
        <li>
          停在哪一步就能问哪一步，AI 回答时会拿到该步骤的具体字节与计算依据。
        </li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.home {
  max-width: 1040px;
  margin: 0 auto;
  padding: 48px 20px 64px;
}

.hero {
  text-align: center;
  margin-bottom: 44px;
}

.hero h1 {
  margin: 0 0 14px;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #111827;
}

.subtitle {
  margin: 0 0 10px;
  font-size: 15px;
  color: #4b5563;
}

.meta {
  margin: 0;
  font-size: 12.5px;
  color: #9ca3af;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 44px;
}

.feature {
  padding: 22px 20px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feature h3 {
  margin: 0;
  font-size: 15px;
  color: #111827;
}

.feature p {
  margin: 0;
  flex: 1;
  font-size: 12.5px;
  line-height: 1.75;
  color: #6b7280;
}

.btn {
  align-self: flex-start;
  padding: 7px 16px;
  border: 1px solid #4f46e5;
  border-radius: 8px;
  background: #4f46e5;
  color: #ffffff;
  font-size: 12.5px;
  cursor: pointer;
}

.btn:hover {
  background: #4338ca;
}

.howto {
  padding: 24px 26px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 14px;
}

.howto h2 {
  margin: 0 0 14px;
  font-size: 15px;
  color: #111827;
}

.howto ol {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.howto li {
  font-size: 13px;
  line-height: 1.8;
  color: #4b5563;
}
</style>