import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const REPORT = fileURLToPath(new URL('../report.mjs', import.meta.url))

async function fixture() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'olivos-frontend-coverage-'))
  const staticRoot = path.join(root, 'OlivOS', 'webUI', 'static')
  const rawDir = path.join(root, 'test-results', 'frontend-coverage', 'raw')
  const outDir = path.join(root, 'test-results', 'frontend-coverage')
  await fs.mkdir(staticRoot, { recursive: true })
  await fs.mkdir(rawDir, { recursive: true })

  const appSource = 'function used(x){return x+1}\nfunction unused(){return 0}\nused(1);\n'
  const firstLineEnd = appSource.indexOf('\n') + 1
  const secondLineEnd = appSource.indexOf('\n', firstLineEnd) + 1
  await fs.writeFile(path.join(staticRoot, 'app.js'), appSource, 'utf8')
  await fs.writeFile(
    path.join(staticRoot, 'theme.js'),
    'document.documentElement.dataset.theme = "light";\n',
    'utf8',
  )

  const payload = {
    schema: 1,
    nodeid: 'tests/test_example.py::test_report',
    outcome: 'passed',
    collected_at: '2026-11-25T00:00:00+00:00',
    ignored_script_count: 1,
    error: null,
    scripts: [
      {
        name: 'app.js',
        url: 'http://127.0.0.1/static/app.js',
        functions: [
          { functionName: '', isBlockCoverage: true,
            ranges: [{ startOffset: 0, endOffset: appSource.length, count: 1 }] },
          { functionName: 'used', isBlockCoverage: false,
            ranges: [{ startOffset: 0, endOffset: firstLineEnd, count: 1 }] },
          { functionName: 'unused', isBlockCoverage: false,
            ranges: [{ startOffset: firstLineEnd, endOffset: secondLineEnd, count: 0 }] },
        ],
      },
      {
        name: 'theme.js',
        url: 'http://127.0.0.1/static/theme.js',
        functions: [{
          functionName: '',
          isBlockCoverage: true,
          ranges: [{ startOffset: 0, endOffset: 55, count: 1 }],
        }],
      },
      {
        name: 'app.js',
        url: 'http://127.0.0.1/static/app.js',
        functions: [{
          functionName: '',
          isBlockCoverage: true,
          ranges: [{ startOffset: 0, endOffset: appSource.length, count: 1 }],
        }],
      },
    ],
  }
  await fs.writeFile(path.join(rawDir, 'sample.json.gz'), gzipSync(JSON.stringify(payload)))
  return { root, rawDir, outDir }
}

test('report keeps an unexecuted function line uncovered', async () => {
  const { root, rawDir, outDir } = await fixture()
  execFileSync(process.execPath, [REPORT,
    '--repo-root', root,
    '--raw-dir', rawDir,
    '--static-root', path.join('OlivOS', 'webUI', 'static'),
    '--out-dir', outDir,
  ], { stdio: 'pipe' })

  const summary = JSON.parse(
    await fs.readFile(path.join(outDir, 'frontend-coverage-summary.json'), 'utf8'),
  )
  const app = summary.files['OlivOS/webUI/static/app.js']
  assert.equal(summary.incomplete, false)
  assert.equal(summary.nodeid_count, 1)
  assert.equal(summary.duplicate_script_count, 1)
  assert.equal(app.lines.total, 3)
  assert.equal(app.lines.covered, 2)
  assert.equal(app.functions.total, 2)
  assert.equal(app.functions.covered, 1)
  await fs.access(path.join(outDir, 'html', 'index.html'))
  await fs.access(path.join(outDir, 'lcov.info'))
})
