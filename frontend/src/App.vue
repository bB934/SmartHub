<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const online = ref(null)

const nav = [
  { to: '/chat', label: '知识库问答', desc: '双路召回 + 流式生成' },
  { to: '/docs', label: '文档管理', desc: '上传 / 重建 / 删除' },
  { to: '/search', label: '检索调试', desc: '召回结果与融合得分' },
]

onMounted(async () => {
  try {
    const resp = await fetch('/health')
    online.value = resp.ok
  } catch {
    online.value = false
  }
})
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="logo">SH</div>
        <div class="brand-text">
          <strong>SmartHub</strong>
          <span>企业级 RAG 知识库</span>
        </div>
      </div>

      <nav class="nav">
        <RouterLink
          v-for="(item, index) in nav"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: route.path === item.to }"
        >
          <span class="nav-index">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="nav-text">
            <strong>{{ item.label }}</strong>
            <small>{{ item.desc }}</small>
          </span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <span class="dot" :class="online === null ? 'idle' : online ? 'ok' : 'bad'" />
        <span>{{ online === null ? '检测服务…' : online ? '后端服务在线' : '后端服务离线' }}</span>
      </div>
    </aside>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>
