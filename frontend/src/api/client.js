// 与后端 API 的唯一入口：普通 JSON 请求 + SSE 流式问答
const BASE = '/api/v1'

// 演示环境固定租户/空间/用户；接真实登录后换成 token 里的值
const TENANT_HEADERS = {
  'X-Tenant-Id': '1',
  'X-Space-Id': '1',
  'X-User-Id': '1',
}

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...TENANT_HEADERS, ...(options.headers || {}) },
  })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      // 非 JSON 响应，保留状态码
    }
    throw new Error(detail)
  }
  return resp.status === 204 ? null : resp.json()
}

export const listDocs = () => request('/doc')

export const getTask = (docId) => request(`/doc/${docId}/task`)

export const deleteDoc = (docId) => request(`/doc/${docId}`, { method: 'DELETE' })

export const reindexDoc = (docId) => request(`/doc/${docId}/reindex`, { method: 'POST' })

export const search = (query, topk = 10) =>
  request('/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, topk }),
  })

export function uploadDoc({ file, title, visibility, groups }) {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)
  form.append('visibility', String(visibility))
  form.append('groups', groups || '')
  return request('/doc/upload', { method: 'POST', body: form })
}

/**
 * SSE 流式问答。后端事件：sources / token / done / error。
 * 用 fetch + ReadableStream 而不是 EventSource：EventSource 只支持 GET。
 */
export async function streamChat(question, handlers = {}, signal) {
  const resp = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { ...TENANT_HEADERS, 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')

      let event = ''
      const dataLines = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!event || !dataLines.length) continue
      let payload
      try {
        payload = JSON.parse(dataLines.join('\n'))
      } catch {
        continue
      }
      handlers[event]?.(payload)
    }
  }
}
