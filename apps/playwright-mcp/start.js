#!/usr/bin/env node
const { spawn } = require('node:child_process')
const path = require('node:path')

const scriptDir = __dirname
const initScript = process.env.PLAYWRIGHT_MCP_STEALTH_INIT_SCRIPT || path.join(scriptDir, 'stealth-init.js')
const playwrightMcpCli = require.resolve('@playwright/mcp/package.json').replace(/package\.json$/, 'cli.js')
const extraArgs = []

const truthy = (value) => !['0', 'false', 'no', 'off'].includes(String(value || '').toLowerCase())

if (truthy(process.env.PLAYWRIGHT_MCP_STEALTH_ENABLED ?? 'true')) {
  extraArgs.push('--init-script', initScript)
}

const args = [playwrightMcpCli, ...extraArgs, ...process.argv.slice(2)]
const child = spawn(process.execPath, args, {
  stdio: 'inherit',
  env: process.env,
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }
  process.exit(code ?? 0)
})
