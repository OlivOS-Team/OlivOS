import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { promises as fs } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { gunzipSync } from 'node:zlib'

import libCoverage from 'istanbul-lib-coverage'
import libReport from 'istanbul-lib-report'
import reports from 'istanbul-reports'
import V8ToIstanbul from 'v8-to-istanbul'

const DEFAULT_FILES = ['app.js', 'theme.js']

function usage() {
  return [
    '用法：node tools/frontend_coverage/report.mjs [选项]',
    '  --repo-root <path>    仓库根目录，默认当前目录',
    '  --raw-dir <path>      raw V8 覆盖目录',
    '  --static-root <path>  WebUI 静态资源目录，默认 OlivOS/webUI/static',
    '  --out-dir <path>      报告输出目录',
  ].join('\n')
}

function parseArgs(argv) {
  const options = {
    repoRoot: process.cwd(),
    rawDir: 'test-results/frontend-coverage/raw',
    staticRoot: path.join('OlivOS', 'webUI', 'static'),
    outDir: 'test-results/frontend-coverage',
    files: DEFAULT_FILES,
  }
  for (let index = 2; index < argv.length; index += 1) {
    const argument = argv[index]
    if (argument === '--help' || argument === '-h') {
      process.stdout.write(usage() + '\n')
      process.exit(0)
    }
    const value = argv[index + 1]
    if (!value) throw new Error(`参数 ${argument} 缺少值`)
    if (argument === '--repo-root') options.repoRoot = value
    else if (argument === '--raw-dir') options.rawDir = value
    else if (argument === '--static-root') options.staticRoot = value
    else if (argument === '--out-dir') options.outDir = value
    else throw new Error(`未知参数：${argument}`)
    index += 1
  }
  options.repoRoot = path.resolve(options.repoRoot)
  options.rawDir = path.resolve(options.repoRoot, options.rawDir)
  options.staticRoot = path.resolve(options.repoRoot, options.staticRoot)
  options.outDir = path.resolve(options.repoRoot, options.outDir)
  return options
}

async function gzipFiles(directory) {
  let entries
  try {
    entries = await fs.readdir(directory, { withFileTypes: true })
  } catch (error) {
    if (error.code === 'ENOENT') return []
    throw error
  }
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.json.gz'))
    .map((entry) => path.join(directory, entry.name))
    .sort()
}

async function readPayload(filename) {
  const content = gunzipSync(await fs.readFile(filename))
  return JSON.parse(content.toString('utf8'))
}

function scriptName(url, files) {
  if (typeof url !== 'string') return null
  let parsed
  try {
    parsed = new URL(url)
  } catch {
    return null
  }
  if (!parsed.pathname.startsWith('/static/')) return null
  const name = parsed.pathname.split('/').pop()
  return files.includes(name) ? name : null
}

function selectCompleteScripts(scripts, files) {
  const groups = new Map()
  for (const script of scripts || []) {
    const name = scriptName(script.url, files)
    if (!name || !Array.isArray(script.functions) || !script.functions.length) continue
    const records = groups.get(name) || []
    records.push(script)
    groups.set(name, records)
  }
  const selected = []
  for (const records of groups.values()) {
    const mostFunctions = Math.max(...records.map((record) => record.functions.length))
    // 页面重载后同一 URL 可能同时出现完整脚本和残缺脚本：丢弃残缺记录，
    // 保留所有同等完整的记录，由 Istanbul 合并各自的执行范围。
    selected.push(...records.filter((record) => record.functions.length === mostFunctions))
  }
  return selected
}

function sourceName(options, name) {
  const sourcePath = path.join(options.staticRoot, name)
  return path.relative(options.repoRoot, sourcePath).split(path.sep).join('/')
}

async function convertScript(options, script) {
  const name = scriptName(script.url, options.files)
  if (!name || !Array.isArray(script.functions) || !script.functions.length) return null
  const sourcePath = path.join(options.staticRoot, name)
  const source = await fs.readFile(sourcePath, 'utf8')
  const filename = sourceName(options, name)
  const converter = new V8ToIstanbul(filename, 0, { source })
  await converter.load()
  converter.applyCoverage(script.functions)
  return {
    name,
    filename,
    sourceHash: createHash('sha256').update(source).digest('hex'),
    coverage: converter.toIstanbul(),
  }
}

function metric(data) {
  return {
    total: data.total,
    covered: data.covered,
    skipped: data.skipped,
    pct: data.pct,
  }
}

function compactSummary(summary) {
  return {
    lines: metric(summary.lines),
    statements: metric(summary.statements),
    functions: metric(summary.functions),
    branches: metric(summary.branches),
  }
}

function emptyMetric() {
  return { total: 0, covered: 0, skipped: 0, pct: 0 }
}

function emptySummary() {
  return {
    lines: emptyMetric(),
    statements: emptyMetric(),
    functions: emptyMetric(),
    branches: emptyMetric(),
  }
}

function gitHead(repoRoot) {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: repoRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      timeout: 5000,
    }).trim() || null
  } catch {
    return null
  }
}

async function writeReports(coverageMap, options, metadata) {
  await fs.mkdir(options.outDir, { recursive: true })
  const context = libReport.createContext({
    dir: options.outDir,
    coverageMap,
  })
  reports.create('json', { file: 'coverage-final.json' }).execute(context)
  reports.create('lcovonly', { file: 'lcov.info' }).execute(context)
  reports.create('html', { subdir: 'html' }).execute(context)
  reports.create('json-summary', { file: 'coverage-summary.json' }).execute(context)

  const files = {}
  for (const filename of coverageMap.files().sort()) {
    files[filename] = compactSummary(coverageMap.fileCoverageFor(filename).toSummary())
  }
  const summary = {
    schema: 1,
    generated_at: new Date().toISOString(),
    git_head: gitHead(options.repoRoot),
    ...metadata,
    totals: coverageMap.files().length ? compactSummary(coverageMap.getCoverageSummary()) : emptySummary(),
    files,
  }
  await fs.writeFile(
    path.join(options.outDir, 'frontend-coverage-summary.json'),
    JSON.stringify(summary, null, 2) + '\n',
    'utf8',
  )
  return summary
}

async function main() {
  const options = parseArgs(process.argv)
  const rawFiles = await gzipFiles(options.rawDir)

  const coverageMap = libCoverage.createCoverageMap({})
  const nodeids = new Set()
  const sourceHashes = {}
  let ignoredScriptCount = 0
  let incomplete = !rawFiles.length
  let incompleteReason = rawFiles.length ? null : `未找到 raw V8 覆盖文件：${options.rawDir}`
  let scriptCount = 0
  let duplicateScriptCount = 0

  for (const filename of rawFiles) {
    const payload = await readPayload(filename)
    nodeids.add(payload.nodeid || path.basename(filename))
    ignoredScriptCount += Number(payload.ignored_script_count) || 0
    if (payload.error || !Array.isArray(payload.scripts) || !payload.scripts.length) {
      incomplete = true
      incompleteReason = incompleteReason || payload.error || 'raw 负载中没有脚本数据'
      continue
    }
    const scripts = selectCompleteScripts(payload.scripts, options.files)
    duplicateScriptCount += Math.max(0, payload.scripts.length - scripts.length)
    for (const script of scripts) {
      const converted = await convertScript(options, script)
      if (!converted) {
        incomplete = true
        incompleteReason = incompleteReason || `无法转换脚本：${script.url || script.name || '未知脚本'}`
        continue
      }
      coverageMap.merge(converted.coverage)
      sourceHashes[converted.filename] = converted.sourceHash
      scriptCount += 1
    }
  }

  const required = sourceName(options, 'app.js')
  if (!coverageMap.files().includes(required)) {
    incomplete = true
    incompleteReason = incompleteReason || `未采集到 ${required}；请确认 Profiler 在首次导航前启动`
  }
  for (const name of options.files) {
    const source = sourceName(options, name)
    if (!coverageMap.files().includes(source)) {
      incomplete = true
      incompleteReason = incompleteReason || `未采集到 ${source}`
    }
  }

  const summary = await writeReports(coverageMap, options, {
    raw_file_count: rawFiles.length,
    nodeid_count: nodeids.size,
    script_count: scriptCount,
    duplicate_script_count: duplicateScriptCount,
    ignored_script_count: ignoredScriptCount,
    incomplete,
    incomplete_reason: incompleteReason,
    source_sha256: sourceHashes,
  })
  const state = incomplete ? `（不完整：${incompleteReason}）` : ''
  process.stdout.write(
    `WebUI JavaScript 覆盖率：${summary.totals.lines.pct}% 行，` +
    `${summary.totals.functions.pct}% 函数，${nodeids.size} 条测试节点${state}\n`,
  )
}

main().catch((error) => {
  process.stderr.write(`WebUI 覆盖率报告失败：${error.message}\n`)
  process.exitCode = 1
})
