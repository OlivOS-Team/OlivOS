'use strict';

const $ = (id) => document.getElementById(id);
const tokenStorageKey = 'olivos.webui.token';
const pageStorageKey = 'olivos.webui.page';

function cachedToken(value) {
  try {
    if (value === undefined) return localStorage.getItem(tokenStorageKey) || '';
    if (value) localStorage.setItem(tokenStorageKey, value);
    else localStorage.removeItem(tokenStorageKey);
  } catch {
    // 浏览器禁用本地存储时，仍允许手动登录。
  }
  return '';
}
const state = {
  token: '',
  session: '',
  page: 'dashboard',
  accounts: [],
  savedAccounts: [],
  revision: '',
  schema: null,
  plugins: {},
  pages: [],
  terminals: [],
  selected: null,
  logs: [],
  terminalLogs: [],
  limit: 500,
  dirty: false,
  showPath: false,
  editing: null,
  draft: null,
  streams: new Map(),
  frame: null,
  frameNamespace: null,
  framePath: null,
  externalPage: null,
  requests: new Set(),
  seenEvents: new Set(),
  qrURL: null,
  timer: null,
  authGeneration: 0,
  cachedLogin: false,
  checkingAuth: false,
  actions: { reload: null, update: null },
};
const titles = {
  dashboard: '仪表盘',
  accounts: '账号',
  logs: '日志',
  terminals: '终端',
  plugins: '插件',
};
const levels = {
  '-1': 'TRACE',
  0: 'DEBUG',
  1: 'NOTE',
  2: 'INFO',
  3: 'WARN',
  4: 'ERROR',
  5: 'FATAL',
};
const terminalNames = {
  napcat: 'NapCat',
  gocqhttp: 'GoCqhttp',
  walleq: 'WalleQ',
  cwcb: 'ComWeChat',
  opqbot: 'OPQBot',
  virtual_terminal: '虚拟终端',
};
const clone = (value) => JSON.parse(JSON.stringify(value));

function element(tag, text, attrs = {}) {
  const node = document.createElement(tag);
  if (text !== null && text !== undefined) node.textContent = text;
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}
function button(text, action, className = '') {
  const node = element('button', text, { type: 'button', class: className });
  node.addEventListener('click', () => Promise.resolve().then(action).catch(notifyError));
  return node;
}
let noticeTimer = null;
function hideNotice() {
  clearTimeout(noticeTimer);
  noticeTimer = null;
  $('notice').hidden = true;
  $('notice-message').textContent = '';
}
function notify(message) {
  hideNotice();
  $('notice-message').textContent = message;
  $('notice').hidden = false;
  noticeTimer = setTimeout(hideNotice, 5000);
}
function notifyError(error) {
  notify(error.message || String(error));
}
async function api(path, options = {}) {
  const generation = state.authGeneration;
  const headers = { 'X-Auth-Token': state.token, ...options.headers };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({ error: `请求失败 (${response.status})` }));
  if (generation !== state.authGeneration) throw new Error('登录状态已改变');
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      resetLogin('登录已失效，请重新输入 Token。');
    }
    const error = new Error(data.error || `请求失败 (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}
function bind(id, action, event = 'click') {
  $(id).addEventListener(event, async (ev) => {
    try {
      await action(ev);
    } catch (error) {
      notifyError(error);
    }
  });
}
function closeStream(name) {
  const entry = state.streams.get(name);
  if (entry) {
    entry.closed = true;
    clearTimeout(entry.timer);
    if (entry.socket) entry.socket.close();
  }
  state.streams.delete(name);
}
function stream(name, path, onBatch, onStatus = () => {}) {
  closeStream(name);
  const entry = { closed: false, attempts: 0, socket: null, timer: null };
  state.streams.set(name, entry);
  const connect = () => {
    if (entry.closed || !state.token) return;
    const url = new URL(path, location.href);
    url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(url, ['olivos', `token.${state.token}`]);
    entry.socket = socket;
    socket.onopen = () => {
      entry.attempts = 0;
      onStatus('已连接');
    };
    socket.onmessage = (ev) => {
      if (entry.closed) return;
      try {
        const data = JSON.parse(ev.data);
        if (data.type === 'error') {
          notify(data.error);
          return;
        }
        state.limit = data.limit || state.limit;
        onBatch(data.items || [], data.type === 'history');
      } catch (error) {
        notifyError(error);
      }
    };
    socket.onclose = () => {
      if (entry.closed) return;
      checkAuthentication();
      onStatus('连接断开，正在重连…');
      entry.timer = setTimeout(connect, Math.min(1000 * 2 ** entry.attempts++, 15000));
    };
    socket.onerror = () => onStatus('连接失败');
  };
  connect();
  return entry;
}

async function login(ev, token = null) {
  ev?.preventDefault();
  $('login-error').textContent = '';
  const submit = $('login-form').querySelector('button');
  submit.disabled = true;
  try {
    state.token = token ?? $('token').value.trim();
    const result = await api('/api/login', { method: 'POST' });
    cachedToken(state.token);
    state.cachedLogin = cachedToken() === state.token;
    state.session = result.session;
    state.schema = await api('/api/accounts/schema');
    await Promise.all([loadAccounts(), loadPlugins(), loadTerminals(), refreshStatus()]);
    await restorePage();
    $('token').value = '';
    $('login').hidden = true;
    $('loading').hidden = true;
    $('shell').hidden = false;
    if (state.page === 'logs') renderLogs();
    else if (state.page === 'terminals') {
      renderOutput($('terminal-output'), state.terminalLogs, $('terminal-scroll').checked);
    }
    stream(
      'events',
      `/ws/events?session=${encodeURIComponent(state.session)}&since=${result.cursor}`,
      eventBatch,
      (text) => {
        $('connection').textContent = text;
      },
    );
    clearInterval(state.timer);
    state.timer = setInterval(() => {
      if (state.page === 'dashboard') refreshStatus().catch(notifyError);
      else checkAuthentication();
      checkCachedLogin();
    }, 10000);
  } catch (error) {
    if (error.status === 401 || error.status === 403) cachedToken('');
    for (const name of [...state.streams.keys()]) closeStream(name);
    clearInterval(state.timer);
    state.token = '';
    state.session = '';
    $('shell').hidden = true;
    $('login').hidden = false;
    $('login-error').textContent = error.message;
  } finally {
    $('loading').hidden = true;
    submit.disabled = false;
  }
}
async function logout() {
  const pending = api('/api/logout', { method: 'POST', body: { session: state.session } }).catch(() => {});
  resetLogin();
  await pending;
}
function resetLogin(message = '') {
  state.authGeneration++;
  cachedToken('');
  state.cachedLogin = false;
  for (const name of [...state.streams.keys()]) closeStream(name);
  clearInterval(state.timer);
  state.token = '';
  state.session = '';
  state.accounts = [];
  state.savedAccounts = [];
  state.logs = [];
  state.terminalLogs = [];
  state.seenEvents.clear();
  state.dirty = false;
  state.draft = null;
  state.schema = null;
  state.plugins = {};
  state.terminals = [];
  state.selected = null;
  for (const kind of Object.keys(state.actions)) clearAction(kind);
  clearFrame();
  $('loading').hidden = true;
  $('shell').hidden = true;
  $('login').hidden = false;
  for (const dialog of document.querySelectorAll('dialog')) dialog.close();
  $('account-form').reset();
  $('account-rows').replaceChildren();
  hideNotice();
  $('token').value = '';
  $('login-error').textContent = message;
}
function checkCachedLogin() {
  if (!state.token || !state.cachedLogin) return;
  try {
    if (localStorage.getItem(tokenStorageKey) !== state.token) {
      resetLogin('登录缓存已清除或改变，请重新登录。');
    }
  } catch {
    // 存储暂不可用不等同于凭据失效。
  }
}
async function checkAuthentication() {
  if (!state.token || state.checkingAuth) return;
  state.checkingAuth = true;
  try {
    await api('/api/status');
  } catch {
    // 认证失败由 api 统一退出；网络中断保留登录状态。
  } finally {
    state.checkingAuth = false;
  }
}
window.addEventListener('storage', (ev) => {
  if (ev.key === tokenStorageKey || ev.key === null) checkCachedLogin();
});
window.addEventListener('focus', () => {
  checkCachedLogin();
  checkAuthentication();
});
function rememberPage() {
  const saved = { page: state.page };
  if (state.page === 'plugin-page') {
    saved.namespace = state.frameNamespace;
    saved.path = state.framePath;
    saved.external = state.externalPage;
  } else if (state.page === 'terminals' && state.selected) {
    saved.model = state.selected.model;
    saved.hash = state.selected.hash;
  }
  try {
    sessionStorage.setItem(pageStorageKey, JSON.stringify(saved));
  } catch {
    // 页面位置按标签页保存；浏览器禁用存储时仍可正常导航。
  }
}
async function restorePage() {
  let saved = null;
  try {
    saved = JSON.parse(sessionStorage.getItem(pageStorageKey));
  } catch {
    // 无效或不可用的缓存回到仪表盘。
  }
  if (saved?.page === 'plugin-page') {
    if (saved.external && safeURL(saved.external.url)) return openExternalPage(saved.external);
    const page = state.pages.find((item) =>
      embeddedPluginPage(item) && item.namespace === saved.namespace && item.path === saved.path,
    );
    if (page) return openPluginPage(page);
    return navigate('plugins');
  }
  if (saved?.page === 'terminals') {
    state.selected = state.terminals.find((item) => item.model === saved.model && item.hash === saved.hash) || null;
  }
  await navigate(Object.keys(titles).includes(saved?.page) ? saved.page : 'dashboard');
}
async function navigate(page) {
  state.page = page;
  document.querySelectorAll('.page').forEach((node) => {
    node.hidden = node.id !== page;
  });
  document
    .querySelectorAll('[data-page]')
    .forEach((node) => node.classList.toggle('active', node.dataset.page === page));
  $('page-title').textContent = titles[page] || '插件页面';
  if (page !== 'plugin-page') clearFrame();
  if (page !== 'logs') closeStream('logs');
  if (page !== 'terminals') closeStream('terminal');
  if (page !== 'plugin-page') rememberPage();
  if (page === 'dashboard') await refreshStatus();
  if (page === 'accounts' && !state.dirty) await loadAccounts();
  if (page === 'plugins') await loadPlugins();
  if (page === 'logs') await openLogs();
  if (page === 'terminals') {
    await loadTerminals();
    if (state.selected) openTerminal(state.selected);
  }
}
async function refreshStatus() {
  const status = await api('/api/status');
  $('status-cards').replaceChildren();
  for (const [label, value, valueClass = ''] of [
    ['版本', status.version, 'version-value'],
    ['账号', status.accounts],
    ['启用', status.enabled],
    ['在线', status.online],
  ]) {
    const card = element('div', null, { class: 'panel card' });
    card.append(element('span', label), element('strong', value, { class: valueClass }));
    $('status-cards').append(card);
  }
  const seconds = status.uptime;
  $('runtime').textContent =
    `运行时长：${Math.floor(seconds / 86400)} 天 ${Math.floor(seconds / 3600) % 24} 时 ${Math.floor(seconds / 60) % 60} 分 ${seconds % 60} 秒`;
  $('online-note').textContent = status.unknown
    ? `${status.unknown} 个启用账号尚无可用的连接状态：`
    : '';
  $('unknown-status').hidden = !status.unknown;
  $('unknown-accounts').replaceChildren();
  for (const account of status.unknown_accounts) {
    const item = element('li');
    item.append(
      element('strong', account.id),
      element('span', `${account.platform_type} / ${account.sdk_type} / ${account.model_type}`),
    );
    $('unknown-accounts').append(item);
  }
  $('update-status').textContent = status.update_available
    ? '发现可用更新。'
    : '当前未收到新版本通知。';
}

function dirty() {
  state.dirty = true;
  $('accounts-dirty').textContent = '有未应用的修改';
}
async function loadAccounts() {
  const result = await api('/api/accounts');
  state.accounts = result.account;
  state.savedAccounts = clone(result.account);
  state.revision = result.revision;
  state.dirty = false;
  $('accounts-dirty').textContent = '';
  renderAccounts();
}
function renderAccounts() {
  const rows = $('account-rows');
  rows.replaceChildren();
  if (!state.accounts.length) {
    const row = element('tr');
    row.append(element('td', '暂无账号，请新增账号。', { colspan: 5 }));
    rows.append(row);
  }
  state.accounts.forEach((account, index) => {
    const row = element('tr');
    const enabled = element('input', null, {
      type: 'checkbox',
      class: 'switch',
      role: 'switch',
      'aria-label': `启用账号 ${account.id}`,
    });
    enabled.checked = account.enable;
    enabled.onchange = () => {
      account.enable = enabled.checked;
      dirty();
    };
    const cell = element('td');
    cell.append(enabled);
    row.append(cell);
    row.append(
      element('td', account.id),
      element('td', account.platform_type),
      element('td', `${account.sdk_type} / ${account.model_type}`),
    );
    const actions = element('div', null, { class: 'actions' });
    actions.append(
      button('查看', () => viewAccount(index)),
      button('编辑', () => editAccount(index)),
      button(
        '删除',
        () => {
          if (confirm(`删除账号 ${account.id}？保存并应用后生效。`)) {
            state.accounts.splice(index, 1);
            dirty();
            renderAccounts();
          }
        },
        'danger',
      ),
    );
    const last = element('td');
    last.append(actions);
    row.append(last);
    row.ondblclick = (ev) => {
      if (!ev.target.closest('button, input')) editAccount(index);
    };
    rows.append(row);
  });
}
async function viewAccount(index) {
  const account = state.accounts[index];
  const saved = state.savedAccounts.find((row) => row.hash === account.hash);
  const sameIdentity = saved && ['id', 'sdk_type', 'platform_type'].every(
    (key) => saved[key] === account[key],
  );
  const details = $('account-details');
  details.replaceChildren();
  for (const [label, value] of [
    ['账号 ID', account.id],
    ['账号类型', presetFor(account)?.title || '自定义'],
    ['启用状态', account.enable ? '已启用' : '已停用'],
    ['连接状态', sameIdentity ? '正在读取…' : '待应用'],
    ['平台', account.platform_type],
    ['SDK', account.sdk_type],
    ['型号', account.model_type],
    ['连接类型', account.server.type],
    ['自动配置服务器', account.server.auto ? '是' : '否'],
    ['调试模式', account.debug ? '开启' : '关闭'],
    ['bot_hash', sameIdentity ? account.hash : '保存并应用后生成'],
  ]) {
    const valueNode = element('dd');
    if (label === 'bot_hash' && sameIdentity) valueNode.append(element('code', value));
    else valueNode.textContent = value;
    if (label === '连接状态') {
      valueNode.id = 'account-connection';
      valueNode.setAttribute('role', 'status');
    }
    details.append(element('dt', label), valueNode);
  }
  $('account-info-note').hidden = !state.dirty;
  $('account-info-dialog').showModal();
  if (sameIdentity) {
    const connection = $('account-connection');
    try {
      const status = await api('/api/status');
      connection.textContent = {
        online: '在线',
        offline: '离线',
        unknown: '状态未知',
        disabled: '未启用',
      }[status.account_connections[account.hash]] || '状态未知';
    } catch (error) {
      connection.textContent = '读取失败';
      throw error;
    }
  }
}
function valueAt(object, path) {
  return path.split('.').reduce((value, key) => value?.[key], object);
}
function setAt(object, path, value) {
  const parts = path.split('.');
  const key = parts.pop();
  let target = object;
  for (const part of parts) target = target[part] ||= {};
  target[key] = value;
}
function options(select, values, selected) {
  select.replaceChildren();
  for (const value of values) select.append(element('option', value, { value }));
  if (selected !== undefined && values.includes(selected)) select.value = selected;
}
function presetFor(row) {
  return state.schema.presets.find(
    (p) =>
      p.sdk_type === row.sdk_type &&
      p.platform_type === row.platform_type &&
      p.model_type === row.model_type &&
      p.server.auto === row.server.auto &&
      p.server.type === row.server.type,
  );
}
function editAccount(index) {
  state.editing = index;
  state.draft =
    index === null
      ? {
          id: '',
          password: '',
          sdk_type: 'onebot',
          platform_type: 'qq',
          model_type: 'napcat_show_new',
          server: { auto: true, type: 'post', host: '', port: '', access_token: '' },
          extends: {},
          enable: true,
          debug: false,
        }
      : clone(state.accounts[index]);
  const row = state.draft;
  (row.extends['qsign-server'] || []).forEach((item, i) => {
    item._source_index = i;
  });
  $('account-title').textContent = index === null ? '新增账号' : '编辑账号';
  $('account-error').textContent = '';
  options(
    $('account-preset'),
    [...state.schema.presets.map((p) => p.title), '自定义'],
    presetFor(row)?.title || '自定义',
  );
  options($('account-server-type'), state.schema.server_types, row.server.type);
  $('account-auto').checked = row.server.auto;
  $('account-debug').checked = row.debug;
  syncHierarchy();
  renderAccountFields();
  $('account-dialog').showModal();
}
function syncHierarchy() {
  const row = state.draft;
  const hierarchy = state.schema.hierarchy;
  // 保留已有的历史型号，即使新版本元数据已不再列出。
  const sdks = [...new Set([...Object.keys(hierarchy), row.sdk_type])];
  options($('account-sdk'), sdks, row.sdk_type);
  const platforms = [
    ...new Set([...Object.keys(hierarchy[row.sdk_type] || {}), row.platform_type]),
  ];
  options($('account-platform'), platforms, row.platform_type);
  const models = [
    ...new Set([...(hierarchy[row.sdk_type]?.[row.platform_type] || []), row.model_type]),
  ];
  options($('account-model'), models, row.model_type);
}
function collectFields() {
  const row = state.draft;
  document
    .querySelectorAll('#account-form [data-field]')
    .forEach((input) => setAt(row, input.dataset.field, input.value));
  row.server.type = $('account-server-type').value;
  row.server.auto = $('account-auto').checked;
  row.debug = $('account-debug').checked;
  const extra = JSON.parse($('account-extends').value || '{}');
  if (!extra || typeof extra !== 'object' || Array.isArray(extra))
    throw new Error('extends 必须是 JSON 对象');
  row.extends = { ...row.extends, ...extra };
  document.querySelectorAll('#account-form [data-extend]').forEach((input) => {
    row.extends[input.dataset.extend] = input.value;
  });
  if (!$('qsign-fields').hidden) {
    row.extends['qsign-server-protocal'] = $('qsign-protocol').value;
    row.extends['qsign-server'] = [...$('qsign-rows').children]
      .map((node) => ({
        addr: node.querySelector('[data-qsign="addr"]').value,
        key: node.querySelector('[data-qsign="key"]').value,
        _source_index: Number(node.dataset.source),
      }))
      .filter((item) => item.addr || item.key);
  }
}
function fieldInput(field, parent, attribute = 'data-field') {
  const label = element('label', field.title);
  const input = element('input', null, { [attribute]: field.name, autocomplete: 'off' });
  const secret = /password|access_token|secret|key$/i.test(field.name);
  input.type = secret ? 'password' : 'text';
  input.value =
    (attribute === 'data-field'
      ? valueAt(state.draft, field.name)
      : state.draft.extends[field.name]) ?? '';
  if (field.name === 'id')
    input.addEventListener('input', () => {
      if (!$('webhook-fields').hidden) refreshWebhook().catch(notifyError);
    });
  label.append(input);
  parent.append(label);
}
function renderAccountFields() {
  const preset = state.schema.presets.find((p) => p.title === $('account-preset').value);
  const fields = preset?.fields || state.schema.fields;
  $('account-fields').replaceChildren();
  $('account-extra-fields').replaceChildren();
  fields.forEach((field) => fieldInput(field, $('account-fields')));
  for (const field of state.schema.fields.filter(
    (field) => !fields.some((visible) => visible.name === field.name),
  ))
    fieldInput(field, $('account-extra-fields'));
  (preset?.extends || []).forEach((field) => fieldInput(field, $('account-fields'), 'data-extend'));
  $('account-note').textContent = preset?.note || '';
  const extra = clone(state.draft.extends);
  for (const field of preset?.extends || []) delete extra[field.name];
  if (preset?.qsign) {
    delete extra['qsign-server'];
    delete extra['qsign-server-protocal'];
  }
  $('account-extends').value = JSON.stringify(extra, null, 2);
  $('webhook-fields').hidden = !(
    state.draft.sdk_type === 'qqGuildv2_link' && state.draft.server.type === 'post'
  );
  if (!$('webhook-fields').hidden) refreshWebhook().catch(notifyError);
  $('qsign-fields').hidden = !preset?.qsign;
  options(
    $('qsign-protocol'),
    state.schema.qsign_protocols,
    state.draft.extends['qsign-server-protocal'] || 'AstralQsign',
  );
  renderQsign();
}
function renderQsign() {
  const rows = state.draft.extends['qsign-server'] || [];
  $('qsign-rows').replaceChildren();
  const local = $('qsign-protocol').value === 'AstralQsign';
  $('qsign-local-note').hidden = !local;
  $('qsign-rows').hidden = local;
  $('qsign-add').hidden = local;
  rows.forEach((entry, index) => {
    const row = element('div', null, {
      class: 'qsign-row',
      'data-source': entry._source_index ?? -1,
    });
    for (const [key, title] of [
      ['addr', '地址'],
      ['key', 'KEY'],
    ]) {
      const label = element('label', title);
      const input = element('input', null, {
        'data-qsign': key,
        type: key === 'key' ? 'password' : 'text',
        autocomplete: 'off',
      });
      input.value = entry[key] || '';
      label.append(input);
      row.append(label);
    }
    row.append(
      button('移除', () => {
        collectFields();
        state.draft.extends['qsign-server'].splice(index, 1);
        renderQsign();
      }),
    );
    $('qsign-rows').append(row);
  });
  $('qsign-add').disabled = rows.length >= state.schema.qsign_limit;
}
let webhookGeneration = 0;
async function refreshWebhook() {
  const generation = ++webhookGeneration;
  const accountId = document.querySelector('#account-form [data-field="id"]')?.value || '';
  const data = await api(`/api/accounts/webhook?id=${encodeURIComponent(accountId)}`);
  if (generation !== webhookGeneration) return;
  $('webhook-url').value = data.url;
  $('webhook-cert').textContent = `请将证书放到 ${data.certdir}/${accountId || '{AppID}'}/`;
}
async function copyWebhook() {
  await refreshWebhook();
  try {
    await navigator.clipboard.writeText($('webhook-url').value);
  } catch {
    $('webhook-url').select();
    if (!document.execCommand('copy')) throw new Error('复制失败，请手动复制回调地址');
  }
  notify('回调地址已复制');
}
async function saveAccounts() {
  if (!state.dirty) return;
  const submit = $('save-accounts');
  submit.disabled = true;
  try {
    const accounts = clone(state.accounts);
    for (const row of accounts) {
      if (row.password === '********') delete row.password;
      if (row.server.access_token === '********') delete row.server.access_token;
    }
    const result = await api('/api/accounts', {
      method: 'POST',
      body: { account: accounts, revision: state.revision },
    });
    state.accounts = result.account;
    state.savedAccounts = clone(result.account);
    state.revision = result.revision;
    state.dirty = false;
    $('accounts-dirty').textContent = '';
    renderAccounts();
    notify('账号已保存，连接配置正在热更新。');
  } finally {
    submit.disabled = false;
  }
}

function appendBounded(target, items) {
  target.push(...items);
  if (target.length > state.limit) target.splice(0, target.length - state.limit);
}
function renderOutput(container, lines, follow, logMode = false) {
  const scrollTop = container.scrollTop;
  container.replaceChildren();
  for (const line of lines) {
    let text = line.text ?? '';
    if (logMode) {
      const timestamp =
        typeof line.time === 'number'
          ? new Date(line.time * 1000).toLocaleString()
          : line.time || '';
      text = `${timestamp ? `[${timestamp}] ` : ''}[${levels[line.level] || 'INFO'}] ${text}`;
    } else if (line.name) text = `${line.name}：${text}`;
    text = String(text).replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '');
    container.append(
      element('div', text, {
        class: `log-line ${logMode ? `level-${String(line.level).replace('-', 'n')}` : ''}`,
      }),
    );
  }
  container.scrollTop = follow ? container.scrollHeight : scrollTop;
}
function selectedLogLevels() {
  return [...$('log-level-options').querySelectorAll('input[value]:checked')].map(
    (input) => Number(input.value),
  );
}
function updateLogFilter() {
  const selected = selectedLogLevels();
  const all = selected.length === Object.keys(levels).length;
  $('log-all').checked = all;
  $('log-all').indeterminate = selected.length > 0 && !all;
  const title = all ? '全部' : selected.map((level) => levels[level]).join('、') || '未选择';
  $('log-level').textContent = title;
  $('log-level').setAttribute('aria-label', `日志级别：${title}`);
}
function renderLogs() {
  const selected = selectedLogLevels();
  const lines = state.logs.filter((line) => selected.includes(line.level));
  renderOutput($('log-output'), lines, $('log-scroll').checked, true);
  $('log-count').textContent = `${lines.length} / ${state.limit} 条`;
}
let logGeneration = 0;
async function openLogs() {
  const generation = ++logGeneration;
  closeStream('logs');
  state.logs = [];
  renderLogs();
  const selected = selectedLogLevels();
  if (!selected.length) return;
  const query = `level=${encodeURIComponent(selected.length === Object.keys(levels).length ? '' : selected.join(','))}`;
  const result = await api(`/api/logs?${query}`);
  if (generation !== logGeneration || state.page !== 'logs') return;
  state.limit = result.limit;
  state.logs = result.items;
  renderLogs();
  let cursor = result.cursor;
  stream('logs', `/ws/logs?${query}&since=${result.cursor}`, (items) => {
    const fresh = items.filter((item) => item.sequence > cursor);
    if (!fresh.length) return;
    cursor = fresh[fresh.length - 1].sequence;
    appendBounded(state.logs, fresh);
    renderLogs();
  });
}
async function loadTerminals() {
  const result = await api('/api/terminals');
  state.terminals = result.items;
  state.selected =
    state.terminals.find(
      (item) => item.hash === state.selected?.hash && item.model === state.selected?.model,
    ) ||
    state.terminals[0] ||
    null;
  renderTerminals();
}
function renderTerminals() {
  $('terminal-tabs').replaceChildren();
  for (const terminal of state.terminals) {
    const tab = button(`${terminalNames[terminal.model] || terminal.model} · ${terminal.id}`, () =>
      openTerminal(terminal),
    );
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', terminal === state.selected ? 'true' : 'false');
    $('terminal-tabs').append(tab);
  }
  $('terminal-empty').hidden = !!state.selected;
  $('terminal-content').hidden = !state.selected;
  if (!state.selected) closeStream('terminal');
}
function openTerminal(terminal) {
  state.selected = terminal;
  rememberPage();
  state.terminalLogs = [];
  renderTerminals();
  $('terminal-output').replaceChildren();
  $('terminal-state').textContent = '正在连接…';
  $('terminal-qr').hidden = !(terminal.qrcode || terminal.qrcode_url);
  $('virtual-options').hidden = terminal.model !== 'virtual_terminal';
  stream(
    'terminal',
    `/ws/terminal/${encodeURIComponent(terminal.model)}/${encodeURIComponent(terminal.hash)}`,
    (items, history) => {
      if (history) state.terminalLogs = [];
      appendBounded(state.terminalLogs, items);
      renderOutput($('terminal-output'), state.terminalLogs, $('terminal-scroll').checked);
    },
    (text) => {
      $('terminal-state').textContent = text;
    },
  );
}
async function showQRCode(terminal) {
  $('qr-title').textContent = `请使用账号 ${terminal.id || terminal.hash} 扫码`;
  if (state.qrURL) URL.revokeObjectURL(state.qrURL);
  $('qr-image').hidden = !terminal.qrcode;
  $('qr-link').hidden = !terminal.qrcode_url;
  if (terminal.qrcode) {
    const response = await fetch(
      `/api/terminal/${encodeURIComponent(terminal.model)}/${encodeURIComponent(terminal.hash)}/qrcode`,
      { headers: { 'X-Auth-Token': state.token } },
    );
    if (!response.ok) throw new Error('二维码已失效或不可读取');
    state.qrURL = URL.createObjectURL(await response.blob());
    $('qr-image').src = state.qrURL;
  }
  if (terminal.qrcode_url && safeURL(terminal.qrcode_url)) $('qr-link').href = terminal.qrcode_url;
  if (!$('qr-dialog').open) $('qr-dialog').showModal();
}

function safeURL(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username;
  } catch {
    return false;
  }
}
async function loadPlugins() {
  const result = await api('/api/plugins');
  state.plugins = result.shallow_plugin_data_dict;
  state.pages = result.shallow_plugin_webui_list;
  renderPlugins();
  renderPluginNavigation();
}
function renderPlugins() {
  const header = element('tr');
  for (const text of [...(state.showPath ? ['路径'] : []), '插件', '版本', '作者', '操作'])
    header.append(element('th', text));
  $('plugin-head').replaceChildren(header);
  $('plugin-rows').replaceChildren();
  const plugins = Object.entries(state.plugins).sort((a, b) => (a[1][6] || 0) - (b[1][6] || 0));
  for (const [namespace, plugin] of plugins) {
    const row = element('tr');
    if (state.showPath)
      row.append(
        element('td', `/${plugin[5] ? `${plugin[5].replaceAll('\\', '/')}/` : ''}${namespace}`),
      );
    row.append(element('td', plugin[0]), element('td', plugin[1]), element('td', plugin[2]));
    const cell = element('td');
    cell.append(button('菜单', () => pluginMenu(namespace)));
    row.append(cell);
    row.ondblclick = () => pluginMenu(namespace);
    $('plugin-rows').append(row);
  }
  if (!plugins.length) {
    const row = element('tr');
    row.append(element('td', '暂无已加载的插件。', { colspan: state.showPath ? 5 : 4 }));
    $('plugin-rows').append(row);
  }
  $('toggle-path').textContent = state.showPath ? '隐藏路径' : '显示路径';
}
function pluginMenu(namespace) {
  const plugin = state.plugins[namespace];
  $('menu-title').textContent = plugin[0];
  $('menu-info').textContent = plugin[4];
  $('menu-items').replaceChildren();
  for (const item of plugin[3] || [])
    $('menu-items').append(
      button(item[0], async () => {
        await api('/api/plugin_event', { method: 'POST', body: { namespace, event: item[2] } });
        $('menu-dialog').close();
        notify(`已执行：${item[0]}`);
      }),
    );
  if (!plugin[3]?.length) $('menu-items').append(element('p', '此插件没有声明菜单。'));
  $('menu-dialog').showModal();
}
function embeddedPluginPage(page) {
  return page.type === 'iframe' && typeof page.path === 'string' &&
    page.path.startsWith('webui/') && !page.path.split('/').includes('..');
}
function renderPluginNavigation() {
  $('plugin-links').replaceChildren();
  for (const page of state.pages) {
    if (page.type === 'link' && safeURL(page.url))
      $('plugin-links').append(
        element('a', page.title, { href: page.url, target: '_blank', rel: 'noopener noreferrer' }),
      );
    else if (embeddedPluginPage(page)) {
      const entry = button(page.title, () => openPluginPage(page));
      entry.dataset.pluginNamespace = page.namespace;
      entry.dataset.pluginPath = page.path;
      $('plugin-links').append(entry);
    }
  }
  if (!$('plugin-links').children.length) $('plugin-links').append(element('p', '暂无插件页面'));
  if (state.frameNamespace && !state.plugins[state.frameNamespace]) {
    clearFrame();
    notify('插件页面已卸载。');
  }
  syncPluginSelection();
}
function syncPluginSelection() {
  $('plugin-links').querySelectorAll('button').forEach((entry) => {
    const active = entry.dataset.pluginNamespace === state.frameNamespace &&
      entry.dataset.pluginPath === state.framePath;
    entry.classList.toggle('active', active);
    if (active) entry.setAttribute('aria-current', 'page');
    else entry.removeAttribute('aria-current');
  });
}
function clearFrame() {
  $('plugin-frame-container').replaceChildren();
  state.frame = null;
  state.frameNamespace = null;
  state.framePath = null;
  state.externalPage = null;
  state.requests.clear();
  syncPluginSelection();
}
async function openPluginPage(page) {
  await navigate('plugin-page');
  clearFrame();
  $('page-title').textContent = page.title;
  state.frameNamespace = page.namespace;
  state.framePath = page.path;
  rememberPage();
  syncPluginSelection();
  const filename = page.path.slice('webui/'.length).split('/').map(encodeURIComponent).join('/');
  const frame = element('iframe', null, {
    title: page.title,
    src: `/plugin/${encodeURIComponent(page.namespace)}/${filename}`,
    sandbox: 'allow-scripts',
  });
  state.frame = frame;
  $('plugin-frame-container').append(frame);
}
async function openExternalPage(page) {
  await navigate('plugin-page');
  clearFrame();
  const title = page.title || '插件页面';
  state.externalPage = { url: page.url, title };
  rememberPage();
  $('page-title').textContent = title;
  $('plugin-frame-container').append(element('iframe', null, {
    src: page.url, title, sandbox: 'allow-scripts allow-forms',
  }));
}
window.addEventListener('message', async (ev) => {
  if (!state.frame || ev.source !== state.frame.contentWindow || ev.origin !== 'null') return;
  const data = ev.data;
  if (
    !data ||
    data.type !== 'olivos:plugin_event' ||
    typeof data.event !== 'string' ||
    typeof data.request_id !== 'string' ||
    data.request_id.length > 128
  )
    return;
  if (state.requests.size >= 128) {
    notify('插件页面等待回包过多，请刷新页面。');
    return;
  }
  const namespace = state.frameNamespace;
  const frame = state.frame;
  try {
    state.requests.add(data.request_id);
    await api('/api/plugin_event', {
      method: 'POST',
      body: {
        namespace,
        event: data.event,
        payload: data.payload,
        request_id: data.request_id,
        session: state.session,
      },
    });
  } catch (error) {
    state.requests.delete(data.request_id);
    frame.contentWindow.postMessage(
      { type: 'olivos:plugin_reply', request_id: data.request_id, error: error.message },
      '*',
    );
  }
});
function clearAction(kind) {
  clearTimeout(state.actions[kind]?.timer);
  state.actions[kind] = null;
  const buttons = kind === 'reload' ? ['reload-plugins', 'dashboard-reload-plugins'] : ['check-update'];
  for (const id of buttons) $(id).disabled = false;
}
function showActionResult(kind, message) {
  hideNotice();
  $('operation-title').textContent = kind === 'reload' ? '重载插件' : '检查更新';
  $('operation-message').textContent = message;
  if (!$('operation-dialog').open) $('operation-dialog').showModal();
}
function finishAction(kind, result) {
  const pending = state.actions[kind];
  if (!pending || !Number.isFinite(result.started_at)) return;
  if (!pending.result || result.started_at >= pending.result.started_at) pending.result = result;
  if (pending.startedAt === null || pending.result.started_at < pending.startedAt) return;
  const message = pending.result.message;
  clearAction(kind);
  showActionResult(kind, message);
}
async function runAction(kind, path, progress) {
  if (state.actions[kind]) return;
  const pending = { startedAt: null, result: null, timer: null };
  state.actions[kind] = pending;
  const buttons = kind === 'reload' ? ['reload-plugins', 'dashboard-reload-plugins'] : ['check-update'];
  for (const id of buttons) $(id).disabled = true;
  notify(progress);
  pending.timer = setTimeout(() => {
    clearAction(kind);
    showActionResult(kind, '等待操作完成超时，请查看日志确认结果。');
  }, 90000);
  try {
    const result = await api(path, { method: 'POST' });
    if (state.actions[kind] !== pending) return;
    pending.startedAt = result.started_at;
    if (pending.result) finishAction(kind, pending.result);
  } catch (error) {
    if (state.actions[kind] !== pending) return;
    clearAction(kind);
    if (state.token) showActionResult(kind, error.message || String(error));
  }
}
async function handleEvent(item) {
  if (item.type === 'plugins') {
    await loadPlugins();
    if (item.ready) finishAction('reload', {
      started_at: item.started_at,
      message: `插件重载完成，当前已加载 ${Object.keys(state.plugins).length} 个插件。`,
    });
  } else if (item.type === 'accounts') {
    if (!state.dirty) await loadAccounts();
    await loadTerminals();
  } else if (item.type === 'init') await loadTerminals();
  else if (item.type === 'qrcode' || item.type === 'qrcode_url') {
    await loadTerminals();
    const terminal = state.terminals.find((t) => t.hash === item.hash && t.model === item.model);
    if (terminal) await showQRCode(terminal);
  } else if (item.type === 'update') {
    notify('发现可用的 OlivOS 更新。');
    await refreshStatus();
  } else if (item.type === 'update_check_result') {
    const messages = {
      available: '检查完成，发现可用的 OlivOS 更新。',
      latest: '检查完成，当前已是最新版本。',
      error: '检查更新失败，请检查网络连接或稍后重试。',
      unsupported: '当前平台暂不支持内置更新检查，请前往 GitHub 查看最新版本。',
    };
    finishAction('update', { started_at: item.started_at, message: messages[item.status] || messages.error });
    await refreshStatus();
  } else if (
    item.type === 'plugin_reply' &&
    state.frame &&
    state.frameNamespace === item.namespace &&
    state.requests.has(item.request_id)
  ) {
    state.requests.delete(item.request_id);
    state.frame.contentWindow.postMessage(
      { type: 'olivos:plugin_reply', request_id: item.request_id, payload: item.payload },
      '*',
    );
  } else if (item.type === 'open_page' && safeURL(item.url)) {
    await openExternalPage(item);
  }
}
function eventBatch(items) {
  for (const item of items) {
    if (state.seenEvents.has(item.sequence)) continue;
    state.seenEvents.add(item.sequence);
    if (state.seenEvents.size > state.limit * 2)
      state.seenEvents.delete(state.seenEvents.values().next().value);
    handleEvent(item).catch(notifyError);
  }
}

$('login-form').addEventListener('submit', login);
bind('logout', logout);
document
  .querySelectorAll('[data-page]')
  .forEach((node) =>
    node.addEventListener('click', () => navigate(node.dataset.page).catch(notifyError)),
  );
document
  .querySelectorAll('[data-close]')
  .forEach((node) => node.addEventListener('click', () => $(node.dataset.close).close()));
bind('add-account', () => editAccount(null));
bind('refresh-accounts', () => {
  if (!state.dirty || confirm('放弃尚未应用的修改并刷新？')) return loadAccounts();
});
bind('save-accounts', saveAccounts);
bind(
  'account-preset',
  () => {
    collectFields();
    const preset = state.schema.presets.find((p) => p.title === $('account-preset').value);
    if (preset) {
      Object.assign(state.draft, {
        sdk_type: preset.sdk_type,
        platform_type: preset.platform_type,
        model_type: preset.model_type,
      });
      Object.assign(state.draft.server, preset.server);
    }
    syncHierarchy();
    $('account-auto').checked = state.draft.server.auto;
    $('account-server-type').value = state.draft.server.type;
    renderAccountFields();
  },
  'change',
);
for (const [id, key] of [
  ['account-sdk', 'sdk_type'],
  ['account-platform', 'platform_type'],
  ['account-model', 'model_type'],
])
  bind(
    id,
    () => {
      collectFields();
      state.draft[key] = $(id).value;
      const h = state.schema.hierarchy;
      if (key === 'sdk_type') state.draft.platform_type = Object.keys(h[state.draft.sdk_type])[0];
      if (key !== 'model_type')
        state.draft.model_type = h[state.draft.sdk_type][state.draft.platform_type][0];
      $('account-preset').value = '自定义';
      syncHierarchy();
      renderAccountFields();
    },
    'change',
  );
for (const id of ['account-auto', 'account-server-type'])
  bind(
    id,
    () => {
      collectFields();
      $('account-preset').value = presetFor(state.draft)?.title || '自定义';
      renderAccountFields();
    },
    'change',
  );
$('account-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  try {
    collectFields();
    if (state.editing === null) state.accounts.push(clone(state.draft));
    else state.accounts[state.editing] = clone(state.draft);
    dirty();
    renderAccounts();
    $('account-dialog').close();
  } catch (error) {
    $('account-error').textContent = error.message;
  }
});
bind('qsign-add', () => {
  collectFields();
  const rows = (state.draft.extends['qsign-server'] ||= []);
  if (rows.length < 10) rows.push({ addr: '', key: '', _source_index: -1 });
  renderQsign();
});
bind(
  'qsign-protocol',
  () => {
    collectFields();
    renderQsign();
  },
  'change',
);
bind('notice-close', hideNotice);
bind('webhook-refresh', refreshWebhook);
bind('webhook-copy', copyWebhook);
bind('log-level-options', async (ev) => {
  if (ev.target.id === 'log-all') {
    $('log-level-options').querySelectorAll('input[value]').forEach((input) => {
      input.checked = $('log-all').checked;
    });
  }
  updateLogFilter();
  await openLogs();
}, 'change');
updateLogFilter();
document.addEventListener('click', (ev) => {
  if (!$('log-filter').contains(ev.target)) $('log-filter').open = false;
});
$('log-filter').addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') {
    $('log-filter').open = false;
    $('log-level').focus();
  }
});
bind('log-scroll', renderLogs, 'change');
bind(
  'terminal-scroll',
  () => renderOutput($('terminal-output'), state.terminalLogs, $('terminal-scroll').checked),
  'change',
);
bind('terminal-qr', () => showQRCode(state.selected));
bind(
  'terminal-form',
  (ev) => {
    ev.preventDefault();
    const socket = state.streams.get('terminal')?.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) throw new Error('终端未连接，请稍后重试');
    const packet = { data: $('terminal-input').value };
    if (state.selected.model === 'virtual_terminal')
      packet.user_conf = {
        user_id: $('virtual-user').value,
        user_name: $('virtual-name').value,
        flag_group: $('virtual-type').value === 'group',
        target_id: $('virtual-group').value,
        group_role: 'member',
      };
    socket.send(JSON.stringify(packet));
    $('terminal-input').value = '';
  },
  'submit',
);
bind('toggle-path', () => {
  state.showPath = !state.showPath;
  renderPlugins();
});
for (const id of ['reload-plugins', 'dashboard-reload-plugins']) {
  bind(id, async () => {
    if (confirm('重载全部插件？')) {
      await runAction('reload', '/api/plugins/reload', '正在重载插件…');
    }
  });
}
bind('check-update', async () => {
  await runAction('update', '/api/update/check', '正在检查更新…');
});
bind('exit', async () => {
  if (confirm('退出 OlivOS 将停止所有账号与插件，确定退出？')) {
    await api('/api/exit', { method: 'POST' });
    notify('正在退出 OlivOS…');
  }
});
window.addEventListener('beforeunload', (ev) => {
  if (state.dirty) {
    ev.preventDefault();
    ev.returnValue = '';
  }
});
window.addEventListener('pagehide', () => {
  for (const name of [...state.streams.keys()]) closeStream(name);
  clearInterval(state.timer);
});
window.addEventListener('pageshow', (ev) => {
  if (ev.persisted && state.token) login(null, state.token);
});
{
  const toggle = $('plugin-navigation-toggle');
  const storageKey = 'olivos.webui.pluginsCollapsed';
  function setCollapsed(collapsed) {
    toggle.setAttribute('aria-expanded', String(!collapsed));
    $('plugin-links').hidden = collapsed;
  }
  try {
    setCollapsed(localStorage.getItem(storageKey) === 'true');
  } catch {
    // 禁用存储时仍可展开和收起。
  }
  toggle.addEventListener('click', () => {
    const collapsed = toggle.getAttribute('aria-expanded') === 'true';
    setCollapsed(collapsed);
    try {
      localStorage.setItem(storageKey, String(collapsed));
    } catch {
      // 折叠状态只在当前页面生效。
    }
  });
  const savedToken = cachedToken();
  if (savedToken) login(null, savedToken);
  else {
    $('loading').hidden = true;
    $('login').hidden = false;
  }
}
