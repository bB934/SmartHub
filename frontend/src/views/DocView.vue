<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { deleteDoc, getTask, listDocs, reindexDoc, uploadDoc } from '../api/client'

const docs = ref([])
const loading = ref(true)
const error = ref('')
const uploading = ref(false)
const dragging = ref(false)
const fileInput = ref(null)
const file = ref(null)
const form = reactive({ title: '', visibility: 0, groups: '' })
const stages = ref({})
let timer = null

const ACCEPT = '.pdf,.md,.markdown,.txt,.docx'
const visibilityText = { 0: '全空间', 1: '指定组', 2: '私有' }
const statusMap = {
  0: { label: '构建中', cls: 'warn' },
  1: { label: '生效中', cls: 'ok' },
  2: { label: '已废弃', cls: 'off' },
}

const building = computed(() => docs.value.some((d) => d.index_status === 0))

function statusOf(doc) {
  return statusMap[doc.index_status] ?? { label: '未知', cls: 'off' }
}

function schedulePoll() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (building.value) timer = setInterval(refresh, 2500)
}

async function refresh() {
  try {
    docs.value = await listDocs()
    error.value = ''
    const pending = docs.value.filter((d) => d.index_status === 0)
    if (pending.length) {
      const tasks = await Promise.all(pending.map((d) => getTask(d.id).catch(() => null)))
      const map = {}
      pending.forEach((d, i) => {
        if (tasks[i]) map[d.id] = tasks[i].stage
      })
      stages.value = map
    } else {
      stages.value = {}
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    schedulePoll()
  }
}

function selectFile(candidate) {
  if (!candidate) return
  file.value = candidate
  if (!form.title) form.title = candidate.name.replace(/\.[^.]+$/, '')
}

function onPick(event) {
  selectFile(event.target.files?.[0])
  event.target.value = ''
}

function onDrop(event) {
  dragging.value = false
  selectFile(event.dataTransfer?.files?.[0])
}

async function submit() {
  if (!file.value || uploading.value) return
  uploading.value = true
  error.value = ''
  try {
    await uploadDoc({ file: file.value, title: form.title, visibility: form.visibility, groups: form.groups })
    file.value = null
    form.title = ''
    form.groups = ''
    await refresh()
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}

async function removeDocument(doc) {
  if (!window.confirm(`确定删除「${doc.title}」？索引与原文都会一并删除。`)) return
  try {
    await deleteDoc(doc.id)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

async function rebuild(doc) {
  try {
    await reindexDoc(doc.id)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(refresh)
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>文档管理</h1>
        <p class="sub">上传后自动解析、切片、向量化并双写 Milvus 与 ES，蓝绿切换后立即可检索</p>
      </div>
      <button class="btn" type="button" @click="refresh">刷新</button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>

    <div class="card upload">
      <div
        class="dropzone"
        :class="{ dragging }"
        @click="fileInput.click()"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <template v-if="file">
          <strong>{{ file.name }}</strong>
          <span class="muted">{{ (file.size / 1024).toFixed(1) }} KB · 点击可重新选择</span>
        </template>
        <template v-else>
          <strong>拖拽文件到此处，或点击选择</strong>
          <span class="muted">支持 PDF / Markdown / TXT / DOCX</span>
        </template>
      </div>
      <input ref="fileInput" type="file" :accept="ACCEPT" hidden @change="onPick" />

      <div class="form-row">
        <div class="field">
          <label for="title">文档标题</label>
          <input id="title" v-model="form.title" type="text" placeholder="留空则用文件名" />
        </div>
        <div class="field narrow">
          <label for="visibility">可见范围</label>
          <select id="visibility" v-model.number="form.visibility">
            <option :value="0">全空间可见</option>
            <option :value="1">指定用户组</option>
            <option :value="2">仅自己可见</option>
          </select>
        </div>
        <div v-if="form.visibility === 1" class="field narrow">
          <label for="groups">用户组 ID（逗号分隔）</label>
          <input id="groups" v-model="form.groups" type="text" placeholder="如 3,7" />
        </div>
        <button class="btn primary" type="button" :disabled="!file || uploading" @click="submit">
          {{ uploading ? '上传中…' : '上传并建库' }}
        </button>
      </div>
    </div>

    <div class="card panel">
      <div class="panel-head">
        <strong>文档列表</strong>
        <span class="muted">{{ docs.length }} 篇</span>
      </div>

      <div v-if="loading" class="panel-body">
        <div class="skeleton" />
        <div class="skeleton" style="width: 70%" />
      </div>

      <div v-else-if="!docs.length" class="panel-body empty">
        <strong>还没有文档</strong>
        <span class="muted">上传第一篇文档，构建完成后即可在问答页提问。</span>
      </div>

      <div v-else class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>标题</th>
              <th>格式</th>
              <th>可见范围</th>
              <th>分片</th>
              <th>状态</th>
              <th>版本</th>
              <th class="actions-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="doc in docs" :key="doc.id">
              <td class="title-cell">{{ doc.title }}</td>
              <td class="muted">{{ doc.source_type.toUpperCase() }}</td>
              <td class="muted">{{ visibilityText[doc.visibility] }}</td>
              <td>{{ doc.chunk_count }}</td>
              <td>
                <span class="pill" :class="statusOf(doc).cls">
                  {{ statusOf(doc).label }}
                </span>
                <span v-if="doc.index_status === 0 && stages[doc.id]" class="stage muted">
                  {{ stages[doc.id] }}
                </span>
              </td>
              <td class="muted">v{{ doc.index_version }}</td>
              <td class="actions">
                <button class="btn ghost" type="button" :disabled="doc.index_status === 0" @click="rebuild(doc)">
                  重建
                </button>
                <button class="btn ghost danger" type="button" @click="removeDocument(doc)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.upload {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 96px;
  border: 1.5px dashed #d3d8e8;
  border-radius: 12px;
  background: var(--panel-soft);
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease;
  text-align: center;
  padding: 14px;
}

.dropzone:hover,
.dropzone.dragging {
  border-color: #a5aefb;
  background: var(--accent-soft);
}

.form-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.form-row .field {
  flex: 1;
  min-width: 180px;
}

.form-row .field.narrow {
  flex: 0 0 168px;
  min-width: 140px;
}

.form-row .btn {
  height: 38px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}

.panel-body {
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-body.empty {
  align-items: center;
  text-align: center;
  gap: 4px;
  padding: 34px 16px;
  font-size: 13px;
}

.table-wrap {
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.table th,
.table td {
  padding: 11px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.table th {
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--muted);
  background: var(--panel-soft);
}

.table tbody tr:last-child td {
  border-bottom: none;
}

.table tbody tr:hover td {
  background: #fbfbff;
}

.title-cell {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
}

.stage {
  margin-left: 6px;
  font-size: 11px;
}

.actions-col {
  text-align: right;
}

.actions {
  text-align: right;
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}
</style>
