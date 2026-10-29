<script setup>
import { nextTick, reactive, ref } from 'vue'
import { streamChat } from '../api/client'

const messages = ref([])
const input = ref('')
const busy = ref(false)
const scrollRef = ref(null)

const suggestions = [
  '一线城市住宿标准是多少？',
  '出差结束后多久内提交报销单？',
  '总监能坐一等座吗？',
]

function scrollToBottom() {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function ask(text) {
  const question = (text ?? input.value).trim()
  if (!question || busy.value) return

  input.value = ''
  busy.value = true
  messages.value.push(
    reactive({ role: 'user', content: question, sources: [], stats: null, streaming: false }),
  )

  const bot = reactive({
    role: 'assistant',
    content: '',
    sources: [],
    stats: null,
    cached: false,
    noAnswer: false,
    error: '',
    streaming: true,
  })
  messages.value.push(bot)
  scrollToBottom()

  try {
    await streamChat(question, {
      sources: (list) => {
        bot.sources = Array.isArray(list) ? list : []
      },
      token: (data) => {
        bot.content += data.content ?? ''
        scrollToBottom()
      },
      error: (data) => {
        bot.error = data.message ?? '生成失败'
      },
      done: (data) => {
        bot.cached = !!data.cached
        bot.noAnswer = !!data.no_answer
        bot.stats = data
      },
    })
  } catch (e) {
    bot.error = e.message
  } finally {
    bot.streaming = false
    busy.value = false
    scrollToBottom()
  }
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    ask()
  }
}
</script>

<template>
  <section class="page chat-page">
    <header class="page-head">
      <div>
        <h1>知识库问答</h1>
        <p class="sub">向量 + BM25 双路召回，RRF 融合后流式生成，答案标注出处</p>
      </div>
      <span class="badge live">SSE 流式</span>
    </header>

    <div ref="scrollRef" class="card thread">
      <div v-if="!messages.length" class="empty">
        <div class="empty-mark">RAG</div>
        <strong>从知识库里找答案，而不是猜</strong>
        <p class="muted">上传文档后即可提问；没有资料时系统会明确说“没有相关内容”。</p>
        <div class="suggestions">
          <button
            v-for="item in suggestions"
            :key="item"
            class="suggestion"
            type="button"
            @click="ask(item)"
          >
            {{ item }}
          </button>
        </div>
      </div>

      <article v-for="(msg, index) in messages" :key="index" class="msg" :class="msg.role">
        <div class="avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>

        <div class="bubble">
          <p v-if="msg.content" class="text">{{ msg.content }}</p>
          <p v-else-if="msg.streaming" class="text muted">检索中…</p>

          <span v-if="msg.streaming" class="caret" />

          <div v-if="msg.error" class="alert">{{ msg.error }}</div>

          <div v-if="msg.sources?.length" class="sources">
            <div class="sources-head">
              <span>{{ msg.noAnswer ? '检索到的最相似片段' : '引用来源' }}</span>
              <span class="muted">{{ msg.sources.length }} 条</span>
            </div>
            <p v-if="msg.noAnswer" class="sources-tip">
              这些片段只是与问题最接近的内容，其中没有能直接回答该问题的信息，因此未被引用。
            </p>
            <div v-for="src in msg.sources" :key="src.idx" class="source">
              <span class="source-index">{{ src.idx }}</span>
              <div class="source-body">
                <strong>{{ src.heading || '无标题' }}</strong>
                <p>{{ src.snippet }}</p>
              </div>
            </div>
          </div>

          <div v-if="msg.stats" class="stats">
            <span v-if="msg.cached" class="pill ok">语义缓存命中</span>
            <span v-else class="muted">
              召回 {{ msg.stats.recalled }} 条 · 精排后 {{ msg.stats.reranked }} 条
            </span>
          </div>
        </div>
      </article>
    </div>

    <div class="card composer">
      <textarea
        v-model="input"
        rows="2"
        placeholder="输入问题，Enter 发送，Shift + Enter 换行"
        :disabled="busy"
        @keydown="onKeydown"
      />
      <button class="btn primary send" type="button" :disabled="busy || !input.trim()" @click="ask()">
        {{ busy ? '生成中…' : '发送' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.chat-page {
  height: calc(100vh - 62px);
  min-height: 540px;
}

.thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty {
  margin: auto;
  max-width: 460px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 30px 10px;
}

.empty-mark {
  width: 62px;
  height: 62px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 12px;
  color: var(--accent-dark);
  background: var(--accent-soft);
}

.empty strong {
  font-size: 15px;
}

.empty p {
  margin: 0;
  font-size: 12.5px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 6px;
}

.suggestion {
  border: 1px solid var(--border);
  background: var(--panel-soft);
  color: var(--text);
  border-radius: 999px;
  padding: 6px 13px;
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
}

.suggestion:hover {
  border-color: #c7ccf6;
  background: var(--accent-soft);
  color: var(--accent-dark);
}

.msg {
  display: flex;
  gap: 11px;
}

.msg.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: none;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-size: 11.5px;
  font-weight: 700;
  background: #eef0f8;
  color: #4b5563;
}

.msg.user .avatar {
  background: var(--accent);
  color: #fff;
}

.bubble {
  max-width: min(760px, 82%);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.msg.user .bubble {
  align-items: flex-end;
}

.text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 12px 15px;
  border-radius: 13px;
  background: var(--panel-soft);
  border: 1px solid var(--border);
  font-size: 13.5px;
  line-height: 1.75;
}

.msg.user .text {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.caret {
  width: 7px;
  height: 14px;
  background: var(--accent);
  border-radius: 2px;
  animation: blink 0.9s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

.sources {
  width: 100%;
  border: 1px dashed #dfe3f5;
  background: #fbfbff;
  border-radius: 12px;
  padding: 10px 13px 12px;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.sources-head {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--accent-dark);
  letter-spacing: 0.4px;
}

.sources-tip {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted, #8890a6);
}

.source {
  display: flex;
  gap: 9px;
  align-items: flex-start;
}

.source-index {
  flex: none;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-dark);
  background: var(--accent-soft);
  margin-top: 2px;
}

.source-body strong {
  font-size: 12.5px;
}

.source-body p {
  margin: 1px 0 0;
  font-size: 12px;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.stats {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 11.5px;
}

.composer {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 12px;
}

.composer textarea {
  flex: 1;
  resize: none;
  min-height: 46px;
  max-height: 120px;
  border-radius: 11px;
}

.send {
  height: 44px;
  min-width: 92px;
}
</style>
