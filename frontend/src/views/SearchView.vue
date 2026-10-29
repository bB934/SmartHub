<script setup>
import { ref } from 'vue'
import { search } from '../api/client'

const query = ref('')
const topk = ref(10)
const items = ref([])
const total = ref(0)
const loading = ref(false)
const searched = ref(false)
const error = ref('')

async function run() {
  const q = query.value.trim()
  if (!q || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const resp = await search(q, topk.value)
    items.value = resp.items
    total.value = resp.total
    searched.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>检索调试</h1>
        <p class="sub">不经过大模型，直接看召回结果与 RRF 融合分，定位“答不准”是哪一步的问题</p>
      </div>
      <span class="badge">向量 + BM25</span>
    </header>

    <div class="card search-bar">
      <input
        v-model="query"
        type="search"
        placeholder="输入问题或关键词，例如：一线城市住宿标准"
        @keydown.enter="run"
      />
      <select v-model.number="topk">
        <option :value="5">Top 5</option>
        <option :value="10">Top 10</option>
        <option :value="20">Top 20</option>
        <option :value="50">Top 50</option>
      </select>
      <button class="btn primary" type="button" :disabled="loading || !query.trim()" @click="run">
        {{ loading ? '检索中…' : '检索' }}
      </button>
    </div>

    <div v-if="error" class="alert">{{ error }}</div>

    <div class="result-head">
      <strong>召回结果</strong>
      <span class="muted">{{ searched ? `共 ${total} 条` : '尚未检索' }}</span>
    </div>

    <div v-if="!searched" class="card hint">
      <strong>提示</strong>
      <span class="muted">
        语义相关但用词不同的问法，只有向量路能召回；含专有名词或编号的问法，通常只有 BM25 路能召回。
        两路都召回不到，说明融合或索引没生效。
      </span>
    </div>

    <div v-else-if="!items.length" class="card hint">
      <strong>没有召回到内容</strong>
      <span class="muted">确认文档状态是“生效中”，或换一个问法再试。</span>
    </div>

    <div v-else class="results">
      <article v-for="(item, index) in items" :key="item.chunk_id" class="card hit">
        <div class="hit-head">
          <span class="rank">{{ index + 1 }}</span>
          <div class="hit-title">
            <strong>{{ item.doc_title || `文档 ${item.doc_id}` }}</strong>
            <span class="muted">{{ item.heading || '无标题' }}</span>
          </div>
          <span class="score">RRF {{ item.score.toFixed(4) }}</span>
        </div>
        <p class="hit-text">{{ item.text }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.search-bar {
  display: flex;
  gap: 10px;
  padding: 14px;
}

.search-bar input {
  flex: 1;
  height: 38px;
}

.search-bar select {
  height: 38px;
  padding: 0 10px;
}

.result-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 13px;
  margin-top: 4px;
}

.hint {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hit {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.hit-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rank {
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--accent-dark);
  background: var(--accent-soft);
}

.hit-title {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
  min-width: 0;
  flex: 1;
}

.hit-title strong {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hit-title span {
  font-size: 11.5px;
}

.score {
  flex: none;
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
  color: var(--muted);
  background: #f4f5f9;
  border-radius: 999px;
  padding: 3px 10px;
}

.hit-text {
  margin: 0;
  font-size: 13px;
  color: #3b4256;
  line-height: 1.7;
  white-space: pre-wrap;
}
</style>
