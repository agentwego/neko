#!/usr/bin/env node
const http = require('node:http')
const { URL } = require('node:url')
const { ProxyAgent, fetch } = require('undici')

const listenHost = process.env.CLIPROXY_HOST || '0.0.0.0'
const listenPort = Number(process.env.CLIPROXY_PORT || '8932')
const upstreamBaseURL = (process.env.CLIPROXY_UPSTREAM_BASE_URL || process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, '')
const upstreamAPIKey = process.env.CLIPROXY_UPSTREAM_API_KEY || process.env.OPENAI_API_KEY || ''
const localAPIKey = process.env.CLIPROXY_API_KEY || ''
const proxyServer = process.env.CLIPROXY_PROXY_SERVER || process.env.PLAYWRIGHT_MCP_PROXY_SERVER || ''
const proxyUsername = process.env.CLIPROXY_PROXY_USERNAME || process.env.PLAYWRIGHT_MCP_PROXY_USERNAME || ''
const proxyPassword = process.env.CLIPROXY_PROXY_PASSWORD || process.env.PLAYWRIGHT_MCP_PROXY_PASSWORD || ''
const maxBodyBytes = Number(process.env.CLIPROXY_MAX_BODY_BYTES || 32 * 1024 * 1024)

let dispatcher
if (proxyServer) {
  const proxyURL = proxyServer.includes('://') ? new URL(proxyServer) : new URL(`http://${proxyServer}`)
  if (proxyUsername || proxyPassword) {
    proxyURL.username = proxyUsername
    proxyURL.password = proxyPassword
  }
  dispatcher = new ProxyAgent(proxyURL.toString())
}

function redact(value) {
  if (!value) return ''
  return value.length <= 8 ? '[REDACTED]' : `${value.slice(0, 4)}...[REDACTED]`
}

function sendJSON(res, status, payload) {
  const raw = Buffer.from(JSON.stringify(payload, null, 2))
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': raw.length,
  })
  res.end(raw)
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    let size = 0
    req.on('data', (chunk) => {
      size += chunk.length
      if (size > maxBodyBytes) {
        reject(Object.assign(new Error('request body too large'), { statusCode: 413 }))
        req.destroy()
        return
      }
      chunks.push(chunk)
    })
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

function checkLocalAuth(req) {
  if (!localAPIKey) return true
  const auth = req.headers.authorization || ''
  return auth === `Bearer ${localAPIKey}`
}

const hopByHop = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
])

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`)
    if (req.method === 'GET' && (url.pathname === '/health' || url.pathname === '/v1/health')) {
      sendJSON(res, 200, {
        ok: true,
        upstream_base_url: upstreamBaseURL,
        proxy_configured: Boolean(proxyServer),
      })
      return
    }
    if (req.method === 'GET' && url.pathname === '/v1/ipinfo') {
      const target = process.env.CLIPROXY_IPINFO_URL || 'http://ipinfo.talordata.com'
      const upstream = await fetch(target, { dispatcher })
      const text = await upstream.text()
      res.writeHead(upstream.status, {
        'content-type': upstream.headers.get('content-type') || 'application/json; charset=utf-8',
      })
      res.end(text)
      return
    }
    if (!url.pathname.startsWith('/v1/')) {
      sendJSON(res, 404, { error: { message: 'not found', type: 'not_found' } })
      return
    }
    if (!checkLocalAuth(req)) {
      sendJSON(res, 401, { error: { message: 'invalid local CLIPROXY_API_KEY', type: 'unauthorized' } })
      return
    }

    const body = await readBody(req)
    const headers = {}
    for (const [key, value] of Object.entries(req.headers)) {
      if (!hopByHop.has(key.toLowerCase()) && value !== undefined) headers[key] = value
    }
    if (upstreamAPIKey) headers.authorization = `Bearer ${upstreamAPIKey}`
    const target = `${upstreamBaseURL}${url.pathname}${url.search}`
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : body,
      dispatcher,
    })

    const responseHeaders = {}
    upstream.headers.forEach((value, key) => {
      if (!hopByHop.has(key.toLowerCase())) responseHeaders[key] = value
    })
    res.writeHead(upstream.status, responseHeaders)
    if (upstream.body) {
      for await (const chunk of upstream.body) res.write(chunk)
    }
    res.end()
  } catch (error) {
    if (!res.headersSent) {
      sendJSON(res, error.statusCode || 502, {
        error: {
          message: error.message || String(error),
          type: 'cliproxy_error',
        },
      })
    } else {
      res.destroy(error)
    }
  }
})

server.listen(listenPort, listenHost, () => {
  console.log(JSON.stringify({
    service: 'neko-cliproxy',
    listen: `${listenHost}:${listenPort}`,
    upstream_base_url: upstreamBaseURL,
    upstream_api_key: redact(upstreamAPIKey),
    local_api_key: localAPIKey ? '[configured]' : '[disabled]',
    proxy_configured: Boolean(proxyServer),
  }))
})
