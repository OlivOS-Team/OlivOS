import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const REPORT = fileURLToPath(new URL('../report.mjs', import.meta.url))
const APP_SOURCE = 'function used(x){return x+1}\nfunction unused(){return 0}\nused(1);\n'
const FIRST_LINE_END = APP_SOURCE.indexOf('\n') + 1
const SECOND_LINE_END = APP_SOURCE.indexOf('\n', FIRST_LINE_END) + 1

function appFunctions({ unusedCount = 0 } = {}) {
  return [
    { functionName: '', isBlockCoverage: true,
      ranges: [{ startOffset: 0, endOffset: APP_SOURCE.length, count: 1 }] },
    { functionName: 'used', isBlockCoverage: false,
      ranges: [{ startOffset: 0, endOffset: FIRST_LINE_END, count: 1 }] },
    { functionName: 'unused', isBlockCoverage: false,
      ranges: [{ startOffset: FIRST_LINE_END, endOffset: SECOND_LINE_END, count: unusedCount }] },
  ]
}

function appPayload(functions, overrides = {}) {
  return {
    schema: 1,
    nodeid: 'tests/test_example.py::test_report',
    outcome: 'passed',
    collected_at: '2026-11-25T00:00:00+00:00',
    ignored_script_count: 1,
    error: null,
    scripts: [
      { name: 'app.js', url: 'http://127.0.0.1/static/app.js', functions },
      {
        name: 'theme.js',
        url: 'http://127.0.0.1/static/theme.js',
        functions: [{
          functionName: '',
          isBlockCoverage: true,
          ranges: [{ startOffset: 0, endOffset: 55, count: 1 }],
        }],
      },
    ],
    ...overrides,
  }
}

async function fixture(payloads) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'olivos-frontend-coverage-'))
  const staticRoot = path.join(root, 'OlivOS', 'webUI', 'static')
  const rawDir = path.join(root, 'test-results', 'frontend-coverage', 'raw')
  const outDir = path.join(root, 'test-results', 'frontend-coverage')
  await fs.mkdir(staticRoot, { recursive: true })
  await fs.mkdir(rawDir, { recursive: true })
  await fs.writeFile(path.join(staticRoot, 'app.js'), APP_SOURCE, 'utf8')
  await fs.writeFile(
    path.join(staticRoot, 'theme.js'),
    'document.documentElement.dataset.theme = "light";\n',
    'utf8',
  )
  const records = payloads ?? [appPayload(appFunctions())]
  for (const [index, payload] of records.entries()) {
    await fs.writeFile(
      path.join(rawDir, `sample-${index}.json.gz`),
      gzipSync(JSON.stringify(payload)),
    )
  }
  return { root, rawDir, outDir }
}

function runReport({ root, rawDir, outDir }) {
  execFileSync(process.execPath, [REPORT,
    '--repo-root', root,
    '--raw-dir', rawDir,
    '--static-root', path.join('OlivOS', 'webUI', 'static'),
    '--out-dir', outDir,
  ], { stdio: 'pipe' })
}

async function readSummary(outDir) {
  return JSON.parse(await fs.readFile(
    path.join(outDir, 'frontend-coverage-summary.json'),
    'utf8',
  ))
}

test('report keeps an unexecuted function line uncovered', async () => {
  const payload = appPayload(appFunctions())
  payload.scripts.push({
    name: 'app.js',
    url: 'http://127.0.0.1/static/app.js',
    functions: [{
      functionName: '',
      isBlockCoverage: true,
      ranges: [{ startOffset: 0, endOffset: APP_SOURCE.length, count: 1 }],
    }],
  })
  const context = await fixture([payload])
  runReport(context)

  const summary = await readSummary(context.outDir)
  const app = summary.files['OlivOS/webUI/static/app.js']
  assert.equal(summary.incomplete, false)
  assert.equal(summary.nodeid_count, 1)
  assert.equal(summary.duplicate_script_count, 1)
  assert.equal(app.lines.total, 3)
  assert.equal(app.lines.covered, 2)
  assert.equal(app.functions.total, 2)
  assert.equal(app.functions.covered, 1)
  await fs.access(path.join(context.outDir, 'html', 'index.html'))
  await fs.access(path.join(context.outDir, 'lcov.info'))
})

test('report merges equal-size duplicate scripts instead of dropping later runs', async () => {
  const first = appPayload(appFunctions({ unusedCount: 0 }))
  const second = appPayload(appFunctions({ unusedCount: 1 }))
  const context = await fixture([first, second])
  runReport(context)

  const summary = await readSummary(context.outDir)
  const app = summary.files['OlivOS/webUI/static/app.js']
  assert.equal(summary.incomplete, false)
  assert.equal(summary.duplicate_script_count, 0)
  assert.equal(app.lines.total, 3)
  assert.equal(app.lines.covered, 3)
  assert.equal(app.functions.total, 2)
  assert.equal(app.functions.covered, 2)
})

test('report marks a payload without scripts as incomplete', async () => {
  const context = await fixture([appPayload([], {
    scripts: [],
    error: '未采集到 WebUI 脚本；请确认 Profiler 已在首次导航前启动',
  })])
  runReport(context)

  const summary = await readSummary(context.outDir)
  assert.equal(summary.incomplete, true)
  assert.match(summary.incomplete_reason, /未采集到 WebUI 脚本/)
  assert.deepEqual(summary.files, {})
  assert.equal(summary.totals.lines.pct, 0)
  assert.equal(summary.totals.functions.pct, 0)
})

test('report marks a missing app.js as incomplete instead of failing', async () => {
  const themeOnly = [{
    name: 'theme.js',
    url: 'http://127.0.0.1/static/theme.js',
    functions: [{
      functionName: '',
      isBlockCoverage: true,
      ranges: [{ startOffset: 0, endOffset: 55, count: 1 }],
    }],
  }]
  const context = await fixture([appPayload([], { scripts: themeOnly })])
  runReport(context)

  const summary = await readSummary(context.outDir)
  assert.equal(summary.incomplete, true)
  assert.match(summary.incomplete_reason, /app\.js/)
  assert.ok(summary.files['OlivOS/webUI/static/theme.js'])
})

test('report still writes an incomplete summary when there is no raw data', async () => {
  const context = await fixture([])
  runReport(context)

  const summary = await readSummary(context.outDir)
  assert.equal(summary.incomplete, true)
  assert.match(summary.incomplete_reason, /未找到 raw V8 覆盖文件/)
  assert.deepEqual(summary.files, {})
  assert.equal(summary.raw_file_count, 0)
  assert.equal(summary.totals.lines.pct, 0)
})
