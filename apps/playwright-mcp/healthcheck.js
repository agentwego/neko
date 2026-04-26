const net = require('node:net')

const ports = [
  Number(process.env.PLAYWRIGHT_MCP_PORT || '8931'),
  Number(process.env.CLIPROXY_PORT || '8932'),
]
const host = process.env.PLAYWRIGHT_MCP_HEALTHCHECK_HOST || '127.0.0.1'

function checkPort(port) {
  return new Promise((resolve, reject) => {
    const socket = net.connect({ host, port })
    const fail = (error) => {
      socket.destroy()
      reject(error || new Error(`port ${port} unavailable`))
    }
    socket.setTimeout(2000)
    socket.once('connect', () => {
      socket.end()
      resolve()
    })
    socket.once('timeout', fail)
    socket.once('error', fail)
  })
}

Promise.all(ports.map(checkPort)).then(
  () => process.exit(0),
  () => process.exit(1),
)
