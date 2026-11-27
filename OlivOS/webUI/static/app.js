'use strict';

const $ = (id) => document.getElementById(id);
const tokenStorageKey = 'olivos.webui.token';
const pageStorageKey = 'olivos.webui.page';
const sidebarStorageKey = 'olivos.webui.sidebarCollapsed';
const mobileSidebarQuery = window.matchMedia('(max-width: 800px), (orientation: portrait)');
const performanceNavMobileQuery = window.matchMedia('(max-width: 800px)');
const performanceFactColumnsQuery = window.matchMedia('(max-width: 1030px)');

// 托盘凭证不进入 HTTP URL，读取后立即从浏览器地址/当前历史条目移除。
function takeLoginTicket() {
  const ticket = new URLSearchParams(location.hash.slice(1)).get('login_ticket');
  if (ticket !== null) {
    const cleanUrl = location.pathname + location.search;
    history.replaceState(history.state, '', cleanUrl);
  }
  return ticket;
}
const startupTicket = takeLoginTicket();

function registerServiceWorker() {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
  navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => {
    // 安装/离线能力不可用时不影响 WebUI 在线使用。
  });
}

// 插件页沙箱能力，必须与 pageAPI.py 的 PLUGIN_SANDBOX 保持一致 —— CSP 头的 sandbox
// 指令与 iframe 的 sandbox 属性是两套独立机制，浏览器取更严格的那个，漏一处就失效。
// 刻意不含 allow-same-origin（插件页与宿主 WebUI 同源，给了等于取消沙箱）与
// allow-top-navigation（会把宿主 WebUI 整页导航走）。
// 注意 iframe 的 sandbox 属性只认 HTML 规范里的那几个 token：
// allow-downloads-without-user-activation 只属于 CSP 指令，写在这里浏览器会直接报
// 「is an invalid sandbox flag」。
const pluginSandbox = [
  'allow-scripts', 'allow-forms', 'allow-modals', 'allow-downloads',
  'allow-popups', 'allow-popups-to-escape-sandbox', 'allow-pointer-lock',
  'allow-orientation-lock', 'allow-presentation',
  'allow-top-navigation-by-user-activation', 'allow-storage-access-by-user-activation',
].join(' ');
// 外部页面是独立站点，与宿主本就跨源，可以保留真实源而不削弱隔离。
const externalSandbox = [
  'allow-scripts', 'allow-forms', 'allow-modals', 'allow-downloads',
  'allow-popups', 'allow-popups-to-escape-sandbox', 'allow-same-origin',
  'allow-pointer-lock', 'allow-orientation-lock', 'allow-presentation',
  'allow-top-navigation-by-user-activation',
].join(' ');

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
  navigationGeneration: 0,
  accounts: [],
  savedAccounts: [],
  accountConnections: {},
  selectedAccounts: new Set(),
  accountDragging: null,
  revision: '',
  schema: null,
  plugins: {},
  pluginOrder: [],
  pluginPriority: {},
  priorityRevision: '',
  priorityError: '',
  scheduleSettings: null,
  scheduleRequest: 0,
  scheduleSaving: false,
  tkBridgeSettings: null,
  tkBridgeRequest: 0,
  tkBridge: null,
  // 当前菜单弹窗展示的 namespace，用于优先级变更后同步刷新弹窗内容。
  menuNamespace: '',
  pages: [],
  collapsedPluginGroups: new Set(),
  terminals: [],
  selected: null,
  logs: [],
  logMessageMode: 'op',
  terminalLogs: [],
  limit: 500,
  dirty: false,
  accountEditGeneration: 0,
  showPath: false,
  editing: null,
  draft: null,
  streams: new Map(),
  frames: new Map(),
  frameOrder: [],
  frameCacheLimit: 10,
  frame: null,
  frameNamespace: null,
  framePath: null,
  externalPage: null,
  externalFrame: null,
  requests: new Map(),
  seenEvents: new Set(),
  qr: null,
  timer: null,
  uptimeFrame: null,
  uptimeSnapshot: null,
  uptimeClock: null,
  statistics: null,
  performanceStatistics: null,
  performanceProcesses: null,
  performanceProcessDetails: {},
  performanceProcessOpen: {},
  performanceProcessDetailGroups: {},
  performanceCategory: 'overview',
  performanceWindow: '1m',
  performanceNavOpen: false,
  dashboardTimer: null,
  authGeneration: 0,
  cachedLogin: false,
  checkingAuth: false,
  sessionRefresh: null,
  sessionCheckedAt: 0,
  sidebarCollapsed: false,
  sidebarOpen: false,
  actions: { reload: null, update: null },
  pluginReload: null,
  pluginListGeneration: 0,
  pluginEventChain: Promise.resolve(),
};
const titles = {
  dashboard: '仪表盘',
  performance: '性能',
  accounts: '账号',
  logs: '日志',
  terminals: '终端',
  plugins: '插件',
};
function isStatusPage(page) {
  return page === 'dashboard' || page === 'performance';
}
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
  if (error.authHandled || error.authObsolete) return;
  notify(error.message || String(error));
}
async function api(path, options = {}, discardObsolete = null) {
  const generation = state.authGeneration;
  const { authMessage, jsonText, ...requestOptions } = options;
  const headers = { 'X-Auth-Token': state.token, ...requestOptions.headers };
  if (jsonText !== undefined || requestOptions.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    requestOptions.body = jsonText ?? JSON.stringify(requestOptions.body);
  }
  let response;
  try {
    response = await fetch(path, { ...requestOptions, headers });
  } catch (error) {
    if (generation !== state.authGeneration) error.authObsolete = true;
    throw error;
  }
  const data = await response.json().catch(() => ({ error: `请求失败 (${response.status})` }));
  // 旧登录状态的响应不再改变当前页面，避免覆盖失效提示或打断重新登录。
  if (generation !== state.authGeneration) {
    if (response.ok && discardObsolete) discardObsolete(data);
    throw Object.assign(new Error('登录状态已改变'), { authObsolete: true });
  }
  if (!response.ok) {
    const authHandled = response.status === 401 || response.status === 403;
    let message = data.error || `请求失败 (${response.status})`;
    if (authHandled) {
      // 登录请求展示具体原因；其他请求认证失效时静默退回登录页。
      if (path !== '/api/login') {
        message = '';
      }
      if (authMessage !== undefined && authMessage !== null) {
        message = authMessage;
      }
      resetLogin(message);
    }
    const error = new Error(message);
    error.status = response.status;
    error.code = data.code;
    error.authHandled = authHandled;
    throw error;
  }
  return data;
}
// 版本信息在登录前也需要可见；health 是唯一无需认证的 API。
async function loadPublicVersion() {
  const version = $('login-version');
  if (!version) return;
  try {
    const response = await fetch('/api/health', { headers: { Accept: 'application/json' } });
    if (!response.ok) return;
    const data = await response.json();
    const number = typeof data.version === 'string' ? data.version.trim() : '';
    const slogan = typeof data.version_slogan === 'string' ? data.version_slogan.trim() : '';
    if (!number) return;
    version.querySelector('[data-version-number]').textContent = number;
    const sloganElement = version.querySelector('[data-version-slogan]');
    const separator = version.querySelector('[data-version-separator]');
    sloganElement.textContent = slogan;
    sloganElement.hidden = !slogan;
    separator.hidden = !slogan;
    version.title = slogan ? number + ' · ' + slogan : number;
    version.hidden = false;
  } catch {
    // 版本信息只用于展示，接口不可用时保持隐藏，不影响登录。
  }
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
let sidebarReturnFocus = null;
function sidebarIsMobile() {
  return mobileSidebarQuery.matches;
}
function performanceNavIsMobile() {
  return performanceNavMobileQuery.matches;
}
function toggleSidebar() {
  if (sidebarIsMobile()) setSidebarOpen(!state.sidebarOpen);
  else setSidebarCollapsed(!state.sidebarCollapsed);
}
function updateSidebarToggle() {
  const sidebar = $('sidebar');
  const mobile = sidebarIsMobile();
  const expanded = mobile ? state.sidebarOpen : !state.sidebarCollapsed;
  const label = mobile
    ? state.sidebarOpen ? '关闭侧边栏' : '打开侧边栏'
    : state.sidebarCollapsed ? '展开侧边栏' : '收起侧边栏';
  document.querySelectorAll('[data-sidebar-toggle]').forEach((toggle) => {
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
  });
  if (mobile) sidebar.setAttribute('aria-hidden', String(!state.sidebarOpen));
  else sidebar.removeAttribute('aria-hidden');
}
function setSidebarCollapsed(collapsed, persist = true) {
  state.sidebarCollapsed = collapsed;
  $('shell').dataset.sidebarCollapsed = String(collapsed);
  if (persist) {
    try {
      localStorage.setItem(sidebarStorageKey, String(collapsed));
    } catch {
      // 禁用存储时只在当前页面保留折叠状态。
    }
  }
  updateSidebarToggle();
}
function setSidebarOpen(open, { restoreFocus = true } = {}) {
  open = sidebarIsMobile() && open;
  if (!open) closeSelectMenu();
  if (state.sidebarOpen === open) {
    updateSidebarToggle();
    return;
  }
  if (open) {
    if (state.performanceNavOpen) setPerformanceNavOpen(false, { restoreFocus: false });
    sidebarReturnFocus = document.activeElement;
  }
  state.sidebarOpen = open;
  $('shell').dataset.sidebarOpen = String(open);
  document.body.classList.toggle('sidebar-open', open);
  updateSidebarToggle();
  if (open) {
    $('sidebar-close').focus({ preventScroll: true });
  } else if (restoreFocus && sidebarReturnFocus?.focus) {
    sidebarReturnFocus.focus({ preventScroll: true });
  }
  if (!open) sidebarReturnFocus = null;
}
function syncSidebarMode() {
  if (!sidebarIsMobile()) setSidebarOpen(false, { restoreFocus: false });
  updateSidebarToggle();
}
function syncPerformanceNavMode() {
  if (!performanceNavIsMobile()) {
    setPerformanceNavOpen(false, { restoreFocus: false });
  }
}
function initializeSidebar() {
  let collapsed = false;
  try {
    collapsed = localStorage.getItem(sidebarStorageKey) === 'true';
  } catch {
    // 禁用存储时保持默认展开。
  }
  setSidebarCollapsed(collapsed, false);
  setSidebarOpen(false, { restoreFocus: false });
  if (mobileSidebarQuery.addEventListener) {
    mobileSidebarQuery.addEventListener('change', syncSidebarMode);
  } else {
    mobileSidebarQuery.addListener(syncSidebarMode);
  }
  if (performanceNavMobileQuery.addEventListener) {
    performanceNavMobileQuery.addEventListener('change', syncPerformanceNavMode);
  } else {
    performanceNavMobileQuery.addListener(syncPerformanceNavMode);
  }
}
let performanceNavReturnFocus = null;
function setPerformanceNavOpen(open, { restoreFocus = true } = {}) {
  open = performanceNavIsMobile() && open;
  const toggle = $('performance-nav-toggle');
  if (state.performanceNavOpen === open) {
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    return;
  }
  if (open) {
    if (state.sidebarOpen) setSidebarOpen(false, { restoreFocus: false });
    performanceNavReturnFocus = document.activeElement;
  }
  state.performanceNavOpen = open;
  document.body.classList.toggle('performance-nav-open', open);
  if (toggle) toggle.setAttribute('aria-expanded', String(open));
  const drawer = $('performance-nav-drawer');
  if (drawer) {
    if (open) {
      drawer.setAttribute('role', 'dialog');
      drawer.setAttribute('aria-modal', 'true');
      drawer.setAttribute('aria-labelledby', 'performance-nav-title');
    } else {
      drawer.removeAttribute('role');
      drawer.removeAttribute('aria-modal');
      drawer.removeAttribute('aria-labelledby');
    }
  }
  if (open) {
    const selected = document.querySelector(`[data-performance-category="${state.performanceCategory}"]`);
    window.requestAnimationFrame(() => {
      if (!state.performanceNavOpen) return;
      revealPerformanceCategory(selected);
      selected?.focus({ preventScroll: true });
    });
  } else if (restoreFocus && performanceNavReturnFocus?.focus) {
    performanceNavReturnFocus.focus({ preventScroll: true });
  }
  if (!open) performanceNavReturnFocus = null;
}
function performanceNavFocusable() {
  const drawer = $('performance-nav-drawer');
  if (!drawer) return [];
  return [...drawer.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  )].filter((node) => !node.disabled && node.tabIndex !== -1 && node.getClientRects().length > 0);
}
function trapPerformanceNavFocus(event) {
  if (event.key !== 'Tab' || !state.performanceNavOpen) return;
  const focusable = performanceNavFocusable();
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;
  if (!focusable.includes(active)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus({ preventScroll: true });
    return;
  }
  if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus({ preventScroll: true });
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus({ preventScroll: true });
  }
}
function togglePerformanceNav() {
  setPerformanceNavOpen(!state.performanceNavOpen);
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
  const connect = async () => {
    if (entry.closed || !state.token) return;
    if (name === 'events') {
      try {
        await ensureSession();
      } catch {
        if (!entry.closed) entry.timer = setTimeout(connect, 5000);
        return;
      }
      if (entry.closed || !state.token) return;
    }
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

async function login(ev, token = null, ticket = null) {
  ev?.preventDefault();
  const generation = ++state.authGeneration;
  state.sessionRefresh = null;
  $('login-error').textContent = '';
  const submit = $('login-form').querySelector('button[type=submit]');
  submit.disabled = true;
  try {
    state.token = token ?? '';
    const loginOptions = { method: 'POST' };
    if (token !== null) {
      // 缓存凭据已放入认证头；失效时静默退回登录页。
      loginOptions.authMessage = '';
    } else if (ticket !== null) {
      // 托盘打开网页时，兑换一次性凭证。
      loginOptions.body = { ticket };
    } else {
      // 手动登录按原样提交密码，保留用户输入的空格。
      loginOptions.body = { password: $('token').value };
    }
    const result = await api('/api/login', loginOptions);
    state.token = result.browser_token;
    cachedToken(state.token);
    state.cachedLogin = cachedToken() === state.token;
    state.session = result.session;
    state.sessionCheckedAt = Date.now();
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
    startEventStream(result.cursor);
    clearInterval(state.timer);
    state.timer = setInterval(() => {
      if (!isStatusPage(state.page)) {
        checkAuthentication();
        if (state.page === 'logs') loadLogDisplay().catch(notifyError);
        // 账号页要跟着连接状态变，不能只在进入页面那一刻刷一次。
        if (state.page === 'accounts') refreshStatus().then(() => ensureSession()).catch(notifyError);
      }
      checkCachedLogin();
    }, 10000);
    clearInterval(state.dashboardTimer);
    state.dashboardTimer = setInterval(() => {
      if (isStatusPage(state.page) && !document.hidden) {
        refreshStatus().then(() => ensureSession()).catch(notifyError);
      }
    }, 3000);
    if (state.page === 'dashboard') startUptimeLoop();
  } catch (error) {
    if (error.authHandled || error.authObsolete) return;
    for (const name of [...state.streams.keys()]) closeStream(name);
    clearInterval(state.timer);
    clearInterval(state.dashboardTimer);
    stopUptimeLoop();
    state.uptimeSnapshot = null;
    state.uptimeClock = null;
    state.token = '';
    state.session = '';
    $('shell').hidden = true;
    $('login').hidden = false;
    $('login-error').textContent = error.message;
  } finally {
    if (generation === state.authGeneration) {
      $('loading').hidden = true;
      submit.disabled = false;
    }
  }
}
async function logout() {
  const removal = closeQRCode();
  if (removal) await removal;
  const pending = api('/api/logout', {
    method: 'POST',
    body: { session: state.session },
  }).catch(() => {});
  resetLogin();
  await pending;
}
function resetLogin(message = '') {
  closeQRCode();
  closeAccountMenu();
  finishAccountDrag(false, false);
  revokeExportBlobUrls();
  state.selectedAccounts.clear();
  state.authGeneration++;
  state.navigationGeneration++;
  setSidebarOpen(false, { restoreFocus: false });
  cachedToken('');
  state.cachedLogin = false;
  for (const name of [...state.streams.keys()]) closeStream(name);
  clearInterval(state.timer);
  clearInterval(state.dashboardTimer);
  stopUptimeLoop();
  state.uptimeSnapshot = null;
  state.uptimeClock = null;
  state.statistics = null;
  state.performanceStatistics = null;
  state.performanceProcesses = null;
  state.performanceProcessDetails = {};
  state.performanceProcessOpen = {};
  state.performanceProcessDetailGroups = {};
  state.token = '';
  state.session = '';
  state.sessionRefresh = null;
  state.sessionCheckedAt = 0;
  state.accounts = [];
  state.savedAccounts = [];
  state.logs = [];
  state.logMessageMode = 'op';
  state.terminalLogs = [];
  state.seenEvents.clear();
  state.dirty = false;
  state.draft = null;
  state.schema = null;
  state.plugins = {};
  state.pages = [];
  state.pluginReload = null;
  state.pluginListGeneration++;
  state.scheduleSettings = null;
  state.scheduleRequest++;
  state.scheduleSaving = false;
  closeSelectMenu();
  renderScheduleSettings();
  state.tkBridgeSettings = null;
  state.tkBridgeRequest++;
  finishTkPreview(false);
  renderTkBridgeSettings();
  state.terminals = [];
  state.selected = null;
  for (const kind of Object.keys(state.actions)) clearAction(kind);
  destroyFrames();
  $('loading').hidden = true;
  $('shell').hidden = true;
  $('login').hidden = false;
  for (const dialog of document.querySelectorAll('dialog')) dialog.close();
  $('account-form').reset();
  $('account-rows').replaceChildren();
  hideNotice();
  $('token').value = '';
  $('login-error').textContent = message;
  $('login-form').querySelector('button[type=submit]').disabled = false;
}
function checkCachedLogin() {
  if (!state.token || !state.cachedLogin) return;
  try {
    if (localStorage.getItem(tokenStorageKey) !== state.token) {
      resetLogin();
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
    if (state.session) await ensureSession();
  } catch {
    // 认证失败由 api 统一退出；网络中断保留登录状态。
  } finally {
    state.checkingAuth = false;
  }
}
function startEventStream(cursor) {
  stream(
    'events',
    `/ws/events?session=${encodeURIComponent(state.session)}&since=${cursor}`,
    eventBatch,
    (text) => {
      $('connection').textContent = text;
    },
  );
}
async function ensureSession(force = false) {
  if (state.sessionRefresh) return state.sessionRefresh;
  if (!force && state.session && Date.now() - state.sessionCheckedAt < 60000) return;
  const pending = api('/api/session', {
    method: 'POST',
    body: { session: state.session },
  }).then((result) => {
    const changed = state.session !== result.session;
    state.session = result.session;
    state.sessionCheckedAt = Date.now();
    // 会话被回收时重新订阅；保留已有 iframe、表单和滚动状态。
    if (changed && state.streams.has('events')) startEventStream(result.cursor);
  });
  state.sessionRefresh = pending;
  try {
    await pending;
  } finally {
    if (state.sessionRefresh === pending) state.sessionRefresh = null;
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
    state.selected =
      state.terminals.find(
        (item) => item.model === saved.model && item.hash === saved.hash,
      ) || null;
  }
  await navigate(Object.keys(titles).includes(saved?.page) ? saved.page : 'dashboard');
}
function setPageTitle(title) {
  $('page-title').textContent = title;
}
async function navigate(page) {
  closeSelectMenu();
  closeAccountMenu();
  if (page !== state.page) {
    finishAccountDrag(false, false);
    $('account-import-dialog').close();
    $('account-copy-fallback-dialog').close();
    closeQRCode();
    if ($('account-dialog').open) $('account-dialog').close();
  }
  state.navigationGeneration++;
  if (state.sidebarOpen) setSidebarOpen(false);
  if (state.performanceNavOpen) setPerformanceNavOpen(false, { restoreFocus: false });
  state.page = page;
  document.querySelectorAll('.page').forEach((node) => {
    node.hidden = node.id !== page;
  });
  document
    .querySelectorAll('[data-page]')
    .forEach((node) => {
      const active = node.dataset.page === page;
      node.classList.toggle('active', active);
      if (active) node.setAttribute('aria-current', 'page');
      else node.removeAttribute('aria-current');
    });
  setPageTitle(titles[page] || '插件页面');
  if (page !== 'plugin-page') hideFrames();
  if (page !== 'logs') closeStream('logs');
  if (page !== 'terminals') closeStream('terminal');
  if (page !== 'plugin-page') rememberPage();
  if (page === 'dashboard') startUptimeLoop();
  else stopUptimeLoop();
  if (isStatusPage(page)) await refreshStatus();
  if (page === 'accounts') {
    if (!state.dirty) await loadAccounts();
    await refreshStatus();
  }
  if (page === 'plugins') await Promise.all([loadPlugins(), loadTkBridgeSettings(), loadScheduleSettings()]);
  if (page === 'logs') await openLogs();
  if (page === 'terminals') {
    await loadTerminals();
    if (state.selected) openTerminal(state.selected);
  }
}
// 版本简称标识大版本，与版本号分两行显示；横向空间不够时简称按省略号截断，
// 完整内容留在 title 上，窄屏也不会把卡片撑破。
function versionCard(version, slogan) {
  const card = element('div', null, { class: 'panel card card-version' });
  card.append(element('span', '版本'));
  card.append(element('strong', version, { class: 'version-value' }));
  if (slogan) card.append(element('span', slogan, { class: 'version-slogan', title: slogan }));
  return card;
}
function formatCount(value) {
  const number = Number(value);
  return (Number.isFinite(number) ? Math.max(0, number) : 0).toLocaleString('zh-CN');
}
function formatSignedCount(value) {
  const number = Number(value);
  return Number.isFinite(number) ? String(Math.trunc(number)) : '—';
}
function formatBytes(value) {
  let number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return '0 B';
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let unit = 0;
  while (number >= 1024 && unit < units.length - 1) {
    number /= 1024;
    unit += 1;
  }
  return `${number.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}
function formatRate(value) {
  return `${formatBytes(value)}/s`;
}
function formatPercent(value) {
  const number = Number(value);
  return `${(Number.isFinite(number) ? Math.max(0, number) : 0).toFixed(1)}%`;
}
function formatCpuTime(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return '0 ms';
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${seconds.toFixed(2)} s`;
  return `${Math.floor(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`;
}
function formatDuration(value) {
  const total = Math.max(0, Math.floor(Number(value) || 0));
  const days = Math.floor(total / 86400);
  const hours = String(Math.floor((total % 86400) / 3600)).padStart(2, '0');
  const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const seconds = String(total % 60).padStart(2, '0');
  return days ? `${days} 天 ${hours}:${minutes}:${seconds}` : `${hours}:${minutes}:${seconds}`;
}
function formatDateTime(timestamp) {
  const date = new Date(Number(timestamp) * 1000);
  if (!Number.isFinite(date.getTime())) return '—';
  return date.toLocaleString('zh-CN', { hour12: false });
}
function formatOptionalPercent(value) {
  return value === null || value === undefined ? '—' : formatPercent(value);
}
function sampledAtText(timestamp) {
  const date = new Date(Number(timestamp) * 1000);
  if (!Number.isFinite(date.getTime())) return '';
  return `更新于 ${date.toLocaleTimeString('zh-CN', { hour12: false })}`;
}
function metricChart(options = {}) {
  return element('div', null, {
    id: options.id,
    class: 'statistics-chart metric-card-chart',
    role: 'img',
    'aria-label': options.label || '',
  });
}
function metricCard(label, value, detail, options = {}) {
  const card = element('div', null, {
    class: options.chart ? 'metric-card metric-chart-card' : 'metric-card',
  });
  card.append(
    element('span', label, { class: 'metric-label' }),
    element('strong', value, { class: 'metric-value' }),
  );
  if (options.chart) {
    const visual = element('div', null, { class: 'metric-card-visual' });
    visual.append(metricChart(options.chart));
    card.append(visual);
  }
  card.append(element('span', detail, { class: 'metric-detail' }));
  return card;
}
function svgNode(tag, attrs = {}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}
function clampPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.min(100, Math.max(0, number));
}
function ringMetricCard(label, percent, detail, tone = 'cpu', options = {}) {
  const value = clampPercent(percent);
  const card = element('div', null, {
    class: `metric-card metric-ring-card metric-ring-${tone}` +
      (options.chart ? ' metric-chart-card' : ''),
    'data-ring': tone,
  });
  const ring = element('div', null, {
    class: 'metric-ring',
    'data-percent': String(value),
  });
  const svg = svgNode('svg', {
    viewBox: '0 0 100 100',
    'aria-hidden': 'true',
    focusable: 'false',
  });
  svg.append(
    svgNode('circle', { class: 'metric-ring-track', cx: '50', cy: '50', r: '42' }),
    svgNode('circle', {
      class: 'metric-ring-progress',
      cx: '50',
      cy: '50',
      r: '42',
      pathLength: '100',
      'stroke-dasharray': '100',
      'stroke-dashoffset': String(100 - value),
      transform: 'rotate(-90 50 50)',
    }),
  );
  if (options.secondaryPercent !== undefined && options.secondaryPercent !== null) {
    const secondary = clampPercent(options.secondaryPercent);
    ring.dataset.secondaryPercent = String(secondary);
    svg.append(svgNode('circle', {
      class: 'metric-ring-secondary',
      cx: '50',
      cy: '50',
      r: '32',
      pathLength: '100',
      'stroke-dasharray': '100',
      'stroke-dashoffset': String(100 - secondary),
      transform: 'rotate(-90 50 50)',
    }));
  }
  ring.append(svg, element('strong', formatPercent(value), { class: 'metric-value metric-ring-value' }));
  card.append(element('span', label, { class: 'metric-label' }));
  if (options.chart) {
    const visual = element('div', null, {
      class: 'metric-card-visual metric-card-visual-overlay',
    });
    visual.append(metricChart(options.chart), ring);
    card.append(visual);
  } else {
    card.append(ring);
  }
  card.append(element('span', detail, { class: 'metric-detail' }));
  return card;
}
function formatOptionalCount(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? formatCount(number) : '—';
}
function formatOptionalText(value) {
  return value === null || value === undefined || value === '' ? '—' : String(value);
}
function formatLoad(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : '—';
}
function formatCpuCores(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? `${(Math.max(0, number) / 100).toFixed(2)} 核心` : '—';
}
function formatOptionalBytes(value) {
  return value === null || value === undefined ? '—' : formatBytes(value);
}
function formatOptionalDecimal(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : '—';
}
function formatOptionalPerSecond(value, unit = '个') {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)} ${unit}/秒` : '—';
}
function formatOptionalLatency(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(2)} ms` : '—';
}
function formatFrequency(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number)} MHz` : '—';
}
function failureRatePercent(traffic) {
  const failed = Number(traffic?.failed_per_minute);
  const events = Number(traffic?.event_per_minute);
  if (!Number.isFinite(failed) || failed <= 0) return 0;
  if (!Number.isFinite(events) || events <= 0) return 100;
  return Math.min(100, failed * 100 / events);
}
const performanceWindowLabels = {
  '1m': '1 分钟',
  '5m': '5 分钟',
  '15m': '15 分钟',
  '1h': '1 小时',
  '6h': '6 小时',
  '24h': '24 小时',
};
const performanceWindowKeys = ['1m', '5m', '15m', '1h', '6h', '24h'];
const performanceWindowUsesDate = new Set(['6h', '24h']);
function trafficWindowHistory(windowData) {
  const timestamps = Array.isArray(windowData?.timestamps) ? windowData.timestamps : [];
  return timestamps.map((timestamp, index) => ({
    ts: timestamp,
    inbound: windowData.inbound?.[index] || 0,
    outbound: windowData.outbound?.[index] || 0,
    events: windowData.events?.[index] || 0,
    failed: windowData.failed?.[index] || 0,
  }));
}
function tcpStatesText(states) {
  if (!states || typeof states !== 'object') return '—';
  const items = Object.entries(states)
    .filter(([, count]) => Number.isFinite(Number(count)))
    .sort((left, right) => Number(right[1]) - Number(left[1]));
  return items.length
    ? items.map(([state, count]) => `${state} ${formatCount(count)}`).join(' · ')
    : '—';
}
function trafficBucketValues(traffic, key, history = null) {
  const source = Array.isArray(history) ? history : (traffic?.history || []);
  return source.map((item) => {
    const number = Number(item?.[key]);
    return Number.isFinite(number) ? Math.max(0, number) : 0;
  });
}
function formatBucketInterval(seconds) {
  const number = Number(seconds);
  if (!Number.isFinite(number) || number <= 0) return '';
  if (number < 60) return `${Math.round(number)} 秒`;
  const minutes = number / 60;
  return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)} 分钟`;
}
function formatTrafficBucket(value, intervalSeconds = null) {
  const count = `${formatCount(value)} 条`;
  const interval = formatBucketInterval(intervalSeconds);
  return interval ? `${count} / ${interval}` : count;
}
function chartTimeText(timestamp, slotFromRight, options = {}) {
  if (timestamp !== null && timestamp !== undefined) {
    const date = new Date(Number(timestamp) * 1000);
    if (Number.isFinite(date.getTime())) {
      if (options.includeDate) {
        return date.toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        });
      }
      return date.toLocaleTimeString('zh-CN', { hour12: false });
    }
  }
  return `第 ${slotFromRight} 个采样点`;
}
function setMetrics(container, items) {
  container.replaceChildren(...items.map(([label, value, detail, options = {}]) => (
    options.ring
      ? ringMetricCard(label, value, detail, options.tone, options)
      : metricCard(label, value, detail, options)
  )));
}
const chartHoverState = new WeakMap();
// 性能序列的空桶沿用相邻有效值，不用 0 伪造数据；流量计数序列仍按 0 补空桶。
function resampleTrendValues(values, capacity, { zeroPadding = false } = {}) {
  const size = Math.max(2, Math.floor(Number(capacity)) || 2);
  const recent = (Array.isArray(values) ? values : []).slice(-size);
  const numeric = recent.map((value) => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, number) : null;
  });
  const rawValues = new Array(Math.max(0, size - numeric.length)).fill(null).concat(numeric);
  const actual = rawValues.map((value) => value !== null);
  if (zeroPadding) {
    return {
      values: rawValues.map((value) => (value === null ? 0 : value)),
      actual,
      rawValues,
      hasData: actual.some(Boolean),
    };
  }
  const filled = rawValues.slice();
  const firstIndex = actual.indexOf(true);
  if (firstIndex >= 0) {
    let last = rawValues[firstIndex];
    for (let index = 0; index < filled.length; index += 1) {
      if (rawValues[index] !== null) last = rawValues[index];
      else filled[index] = last;
    }
  }
  return {values: filled, actual, rawValues, hasData: firstIndex >= 0};
}
function renderTrend(container, series, fixedMaximum = null, capacity = null, options = {}) {
  if (!container) return;
  const width = 100;
  const height = 40;
  const padding = 2;
  const plotWidth = width;
  const plotHeight = height - padding * 2;
  const rawSeries = (series || []).map((item) => ({
    className: item.className || '',
    legendClass: item.legendClass || '',
    label: item.label || '',
    percentage: item.percentage === true,
    zeroPadding: item.zeroPadding === true,
    formatValue: typeof item.formatValue === 'function' ? item.formatValue : formatCount,
    values: Array.isArray(item.values) ? item.values : [],
  }));
  const maxLength = rawSeries.reduce((maximum, item) => Math.max(maximum, item.values.length), 0);
  const requestedCapacity = Number(capacity);
  const effectiveCapacity = Number.isFinite(requestedCapacity)
    ? Math.max(2, Math.floor(requestedCapacity))
    : Math.max(2, maxLength);
  const sourceTimestamps = Array.isArray(options.timestamps) ? options.timestamps : [];
  const timestampPadding = Math.max(0, effectiveCapacity - sourceTimestamps.length);
  const timestamps = new Array(timestampPadding).fill(null)
    .concat(sourceTimestamps.slice(-effectiveCapacity));
  const cleaned = rawSeries.map((item) => ({
    ...item,
    ...resampleTrendValues(item.values, effectiveCapacity, {
      zeroPadding: item.zeroPadding,
    }),
  }));
  const allValues = cleaned.flatMap((item) => item.values)
    .filter((value) => value !== null);
  const hasPercentageSeries = cleaned.some((item) => item.percentage);
  const fixed = fixedMaximum === null ? null : Math.max(1, Number(fixedMaximum) || 1);
  const maximum = fixed !== null
    ? fixed
    : (hasPercentageSeries ? 100 : Math.max(1, ...allValues));
  const logarithmic = options.scale === 'log';
  const scaleValue = (value) => (
    logarithmic ? Math.log10(1 + Math.max(0, value)) : value
  );
  const scaleMaximum = Math.max(Number.EPSILON, scaleValue(maximum));
  const seriesMaximum = (item) => {
    if (item.percentage) return 100;
    if (hasPercentageSeries) return Math.max(1, ...item.values);
    return maximum;
  };
  const seriesScaleMaximum = (item) => (
    Math.max(Number.EPSILON, scaleValue(seriesMaximum(item)))
  );
  // 刻线使用固定参考量程，仅用于区分线性与对数标尺，不随数据最大值变化。
  const gridReferenceMaximum = 100;
  const gridScaleMaximum = Math.max(Number.EPSILON, scaleValue(gridReferenceMaximum));
  const svg = svgNode('svg', {
    viewBox: `0 0 ${width} ${height}`,
    preserveAspectRatio: 'none',
    'aria-hidden': 'true',
  });
  svg.dataset.capacity = String(effectiveCapacity);
  svg.dataset.samples = String(effectiveCapacity);
  svg.dataset.seriesCount = String(cleaned.length);
  svg.dataset.scale = logarithmic ? 'log' : 'linear';
  svg.dataset.maximum = String(maximum);
  const defs = svgNode('defs');
  svg.append(defs);
  const denominator = Math.max(1, effectiveCapacity - 1);
  const xForIndex = (index) => plotWidth * (index / denominator);
  const yForValue = (value, itemScaleMaximum = scaleMaximum) => (
    height - padding - plotHeight * Math.min(1, scaleValue(value) / itemScaleMaximum)
  );
  for (const ratio of [0, 0.25, 0.5, 0.75, 1]) {
    const value = gridReferenceMaximum * ratio;
    const y = height - padding - plotHeight * Math.min(1, scaleValue(value) / gridScaleMaximum);
    const gridline = svgNode('line', {
      class: 'chart-grid',
      x1: '0',
      x2: String(width),
      y1: String(y),
      y2: String(y),
    });
    gridline.dataset.gridRatio = String(ratio);
    gridline.dataset.gridValue = String(value);
    svg.append(gridline);
  }
  for (const [index, item] of cleaned.entries()) {
    if (!item.hasData && !item.zeroPadding) continue;
    const itemScaleMaximum = seriesScaleMaximum(item);
    const points = item.values.map((value, index) => (
      `${xForIndex(index).toFixed(2)},${yForValue(value, itemScaleMaximum).toFixed(2)}`
    ));
    if (options.area) {
      const gradientId = `${container.id || 'trend'}-area-${index}`;
      const gradient = svgNode('linearGradient', {
        id: gradientId,
        x1: '0',
        y1: '0',
        x2: '0',
        y2: '1',
        class: `chart-gradient ${item.className.replace(/^chart-series-/, 'chart-gradient-')}`,
      });
      gradient.append(
        svgNode('stop', { offset: '0%', class: 'chart-gradient-stop chart-gradient-start' }),
        svgNode('stop', { offset: '100%', class: 'chart-gradient-stop chart-gradient-end' }),
      );
      defs.append(gradient);
      const baseline = height - padding;
      const areaPoints = [
        `${xForIndex(0).toFixed(2)},${baseline}`,
        ...points,
        `${xForIndex(item.values.length - 1).toFixed(2)},${baseline}`,
      ];
      const area = svgNode('path', {
        class: 'chart-area',
        d: `M ${areaPoints.join(' L ')} Z`,
        fill: `url(#${gradientId})`,
      });
      area.dataset.series = item.className;
      svg.append(area);
    }
    const polyline = svgNode('polyline', {
      class: `chart-series ${item.className}`,
      points: points.join(' '),
    });
    polyline.dataset.series = item.className;
    polyline.dataset.maximum = String(seriesMaximum(item));
    polyline.dataset.percentage = item.percentage ? 'true' : 'false';
    polyline.dataset.scale = logarithmic ? 'log' : 'linear';
    svg.append(polyline);
  }
  const cursor = svgNode('line', {
    class: 'chart-cursor',
    x1: '0',
    x2: '0',
    y1: String(padding),
    y2: String(height - padding),
  });
  cursor.style.display = 'none';
  svg.append(cursor);
  const tooltip = element('div', null, {
    class: 'chart-tooltip',
    'aria-hidden': 'true',
  });
  tooltip.hidden = true;
  container.replaceChildren(svg, tooltip);

  function hideHover() {
    cursor.style.display = 'none';
    tooltip.hidden = true;
    tooltip.replaceChildren();
  }
  function positionTooltip(x) {
    const ratio = x / width;
    if (ratio < 0.24) {
      tooltip.style.left = '4px';
      tooltip.style.right = 'auto';
      tooltip.style.transform = 'none';
    } else if (ratio > 0.76) {
      tooltip.style.left = 'auto';
      tooltip.style.right = '4px';
      tooltip.style.transform = 'none';
    } else {
      tooltip.style.left = `${(ratio * 100).toFixed(2)}%`;
      tooltip.style.right = 'auto';
      tooltip.style.transform = 'translateX(-50%)';
    }
  }
  function showHover(index) {
    const slot = Math.max(0, Math.min(effectiveCapacity - 1, Math.floor(index)));
    const x = xForIndex(slot);
    cursor.setAttribute('x1', String(x));
    cursor.setAttribute('x2', String(x));
    cursor.style.display = '';
    const hasData = cleaned.some((item) => item.actual[slot]);
    tooltip.replaceChildren();
    if (hasData) {
      tooltip.append(element('span', chartTimeText(
        timestamps[slot], effectiveCapacity - slot,
        { includeDate: options.includeDate === true },
      ), {
        class: 'chart-tooltip-time',
      }));
      for (const item of cleaned) {
        const row = element('div', null, { class: 'chart-tooltip-row' });
        const dot = element('i', null, {
          class: `legend-dot ${item.legendClass}`.trim(),
        });
        const value = item.actual[slot] ? item.formatValue(item.rawValues[slot]) : '—';
        row.append(
          dot,
          element('span', item.label, { class: 'chart-tooltip-label' }),
          element('strong', value, { class: 'chart-tooltip-value' }),
        );
        tooltip.append(row);
      }
    } else {
      tooltip.append(element('span', '暂无历史采样', { class: 'chart-tooltip-empty' }));
    }
    positionTooltip(x);
    tooltip.hidden = false;
  }
  function slotFromEvent(event) {
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return null;
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const plotRatio = Math.max(0, Math.min(1, (ratio * width) / plotWidth));
    return Math.round(plotRatio * (effectiveCapacity - 1));
  }
  function handlePointer(event) {
    const slot = slotFromEvent(event);
    if (slot === null) return;
    chartHoverState.set(container, slot);
    showHover(slot);
  }
  container.onpointerenter = handlePointer;
  container.onpointermove = handlePointer;
  container.onpointerleave = () => {
    chartHoverState.delete(container);
    hideHover();
  };
  const previous = chartHoverState.get(container);
  if (previous !== undefined && container.matches(':hover')) showHover(previous);
  else if (!container.matches(':hover')) {
    chartHoverState.delete(container);
    hideHover();
  }
}
function showStatisticsUnavailable(reason) {
  state.statistics = null;
  $('statistics-content').hidden = true;
  $('statistics-note').hidden = false;
  $('statistics-note').textContent = reason === 'statistics_warming_up'
    ? '监测组件正在启动，稍后自动重试。'
    : '性能与流量统计暂不可用，不影响其他功能。';
  $('statistics-sampled').textContent = '';
}
function renderStatistics(data) {
  if (!data?.available || !data.performance || !data.traffic) {
    showStatisticsUnavailable(data?.reason);
    return;
  }
  state.statistics = data;
  $('statistics-content').hidden = false;
  $('statistics-note').hidden = true;
  $('statistics-note').textContent = '';
  $('statistics-sampled').textContent = sampledAtText(data.sampled_at);

  const performance = data.performance;
  const traffic = data.traffic;
  const cpu = performance.cpu || {};
  const memory = performance.memory || {};
  const disk = performance.disk || {};
  const network = performance.network || {};
  const process = performance.process || {};
  const diskDetail = [
    `${formatBytes(disk.used)} / ${formatBytes(disk.total)}`,
    Number.isFinite(Number(disk.volume_count)) && Number(disk.volume_count) > 0
      ? `${formatCount(disk.volume_count)} 个卷`
      : '',
    `读取 ${formatRate(disk.read_bps)} · 写入 ${formatRate(disk.write_bps)}`,
  ].filter(Boolean).join(' · ');
  const loadValue = formatLoad(cpu.load_1);
  const load = loadValue === '—' ? '' : ` · 负载 ${loadValue}`;
  const threadDetail = process.threads === null || process.threads === undefined
    ? '— 线程'
    : `${formatCount(process.threads)} 线程`;
  const cpuCount = Number(cpu.count);
  const processCpuValue = Number(process.cpu_percent);
  const processCpuShare = process.cpu_percent !== null && process.cpu_percent !== undefined &&
    Number.isFinite(cpuCount) && cpuCount > 0 && Number.isFinite(processCpuValue)
    ? Math.max(0, processCpuValue) / cpuCount
    : null;
  const processCpu = process.cpu_percent === null || process.cpu_percent === undefined
    ? ''
    : ` · ${formatCpuCores(processCpuValue)}`;
  const cpuDetail = `${formatCount(cpu.count)} 逻辑核心${load} | ` +
    `OlivOS ${formatOptionalCount(process.count)} 进程 · ${threadDetail}${processCpu}`;
  const memoryTotal = Number(memory.total);
  const processMemoryPercent = Number.isFinite(memoryTotal) && memoryTotal > 0
    ? Math.max(0, Number(process.rss) || 0) * 100 / memoryTotal
    : 0;
  const memoryDetail = `${formatBytes(memory.used)} / ${formatBytes(memory.total)} | ` +
    `OlivOS ${formatBytes(process.rss)} (${formatPercent(processMemoryPercent)})`;
  setMetrics($('performance-metrics'), [
    ['CPU', cpu.percent, cpuDetail, {
      ring: true, tone: 'cpu', secondaryPercent: processCpuShare,
      chart: { id: 'dashboard-cpu-chart', label: 'CPU 使用率趋势' },
    }],
    ['内存', memory.percent, memoryDetail, {
      ring: true, tone: 'memory', secondaryPercent: processMemoryPercent,
      chart: { id: 'dashboard-memory-chart', label: '内存占用趋势' },
    }],
    ['磁盘', disk.percent, diskDetail, {
      ring: true, tone: 'disk',
      chart: { id: 'dashboard-disk-chart', label: '磁盘读取与写入速率趋势' },
    }],
    ['网络', `↓ ${formatRate(network.recv_bps)} · ↑ ${formatRate(network.sent_bps)}`,
      `下行 ${formatCount(network.packets_recv_per_second)} 包/秒 · ` +
      `上行 ${formatCount(network.packets_sent_per_second)} 包/秒`, {
        chart: { id: 'dashboard-network-chart', label: '网络下行与上行速率趋势' },
      }],
    ['收发消息',
      `↓ ${formatCount(traffic.inbound_per_minute)} 条/分钟 · ` +
      `↑ ${formatCount(traffic.outbound_per_minute)} 条/分钟`,
      `累计 收 ${formatCount(traffic.inbound_total)} · 发 ${formatCount(traffic.outbound_total)}`, {
        chart: { id: 'dashboard-traffic-chart', label: '收发消息趋势' },
      }],
    ['失败事件', `${formatCount(traffic.failed_per_minute)} 条/分钟`,
      `累计 ${formatCount(traffic.failed_total)} 条`, {
        chart: { id: 'dashboard-failure-chart', label: '失败事件趋势' },
      }],
  ]);
  const history = performance.history || {};
  renderTrend($('dashboard-cpu-chart'), [
    {
      className: 'chart-series-cpu', legendClass: 'legend-cpu', label: 'CPU 使用率',
      formatValue: formatPercent, values: history.cpu_percent || [], percentage: true,
    },
  ], 100, history.capacity, { timestamps: history.timestamps || [], area: true });
  renderTrend($('dashboard-memory-chart'), [
    {
      className: 'chart-series-memory', legendClass: 'legend-memory', label: '内存使用率',
      formatValue: formatPercent, values: history.memory_percent || [], percentage: true,
    },
  ], 100, history.capacity, { timestamps: history.timestamps || [], area: true });
  renderTrend($('dashboard-disk-chart'), [
    {
      className: 'chart-series-disk-read', legendClass: 'legend-disk-read', label: '读取',
      formatValue: formatRate, values: history.disk_read_bps || [],
    },
    {
      className: 'chart-series-disk-write', legendClass: 'legend-disk-write', label: '写入',
      formatValue: formatRate, values: history.disk_write_bps || [],
    },
  ], null, history.capacity, {
    timestamps: history.timestamps || [], area: true, scale: 'log',
  });
  renderTrend($('dashboard-network-chart'), [
    {
      className: 'chart-series-network-down', legendClass: 'legend-network-down', label: '网络下行',
      formatValue: formatRate, values: history.network_recv_bps || [],
    },
    {
      className: 'chart-series-network-up', legendClass: 'legend-network-up', label: '网络上行',
      formatValue: formatRate, values: history.network_sent_bps || [],
    },
  ], null, history.capacity, {
    timestamps: history.timestamps || [], area: true, scale: 'log',
  });
  const trafficHistory = traffic.history || [];
  renderTrend($('dashboard-traffic-chart'), [
    {
      className: 'chart-series-inbound', legendClass: 'legend-inbound', label: '收',
      formatValue: formatTrafficBucket, zeroPadding: true,
      values: trafficBucketValues(traffic, 'inbound'),
    },
    {
      className: 'chart-series-outbound', legendClass: 'legend-outbound', label: '发',
      formatValue: formatTrafficBucket, zeroPadding: true,
      values: trafficBucketValues(traffic, 'outbound'),
    },
  ], null, traffic.history_capacity, {
    timestamps: trafficHistory.map((item) => item.ts),
    area: true,
  });
  renderTrend($('dashboard-failure-chart'), [
    {
      className: 'chart-series-failed', legendClass: 'legend-failed', label: '失败',
      formatValue: formatTrafficBucket, zeroPadding: true,
      values: trafficBucketValues(traffic, 'failed'),
    },
  ], null, traffic.history_capacity, {
    timestamps: trafficHistory.map((item) => item.ts),
    area: true,
  });
}
function setPerformanceReadout(id, text) {
  const node = $(id);
  if (node) node.textContent = text;
}
const performanceCategories = [
  'overview', 'cpu', 'memory', 'disk', 'network', 'traffic', 'processes',
];
function setPerformanceSummary(category, value) {
  document.querySelectorAll(`[data-performance-summary="${category}"]`).forEach((node) => {
    node.textContent = value;
  });
}
function setPerformanceStat(name, value) {
  document.querySelectorAll(`[data-performance-stat="${name}"]`).forEach((node) => {
    node.textContent = value;
  });
}
function syncPerformanceWindowControls(data) {
  const performanceWindows = data?.performance?.windows || {};
  const trafficWindows = data?.traffic?.windows || {};
  document.querySelectorAll('[data-performance-window]').forEach((button) => {
    const key = button.dataset.performanceWindow;
    const available = Boolean(performanceWindows[key] || trafficWindows[key]);
    const active = key === state.performanceWindow;
    button.disabled = !available;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}
function renderPerformanceCores(values) {
  const container = $('performance-cpu-cores');
  if (!container) return;
  const rows = Array.isArray(values) ? values : [];
  if (!rows.length) {
    container.replaceChildren(element('p', '当前平台未提供每核心使用率。', {
      class: 'performance-list-empty',
    }));
    return;
  }
  container.replaceChildren(...rows.map((value, index) => {
    const percent = clampPercent(value);
    const item = element('div', null, { class: 'performance-core-item', role: 'listitem' });
    const head = element('div', null, { class: 'performance-core-head' });
    head.append(
      element('span', `核心 ${index + 1}`, { class: 'performance-core-name' }),
      element('span', formatPercent(percent), { class: 'performance-core-value' }),
    );
    const meter = element('div', null, { class: 'performance-meter', 'aria-hidden': 'true' });
    const fill = element('div', null, { class: 'performance-meter-fill' });
    fill.style.width = `${percent}%`;
    meter.append(fill);
    item.append(head, meter);
    return item;
  }));
}
function renderPerformanceVolumes(volumes) {
  const container = $('performance-disk-volumes');
  if (!container) return;
  const rows = Array.isArray(volumes) ? volumes : [];
  if (!rows.length) {
    container.replaceChildren(element('p', '暂无可用卷信息。', {
      class: 'performance-list-empty',
    }));
    return;
  }
  container.replaceChildren(...rows.map((volume) => {
    const percent = clampPercent(volume?.percent);
    const total = Math.max(0, Number(volume?.total) || 0);
    const used = Math.max(0, Number(volume?.used) || 0);
    const name = volume?.mountpoint || volume?.device || '卷';
    const item = element('div', null, { class: 'performance-volume-item' });
    const head = element('div', null, { class: 'performance-volume-head' });
    head.append(
      element('span', name, { class: 'performance-volume-name', title: name }),
      element('span', formatPercent(percent), { class: 'performance-volume-value' }),
    );
    const meter = element('div', null, { class: 'performance-meter', 'aria-hidden': 'true' });
    const fill = element('div', null, { class: 'performance-meter-fill' });
    fill.style.width = `${percent}%`;
    meter.append(fill);
    const device = volume?.device && volume.device !== name ? ` · ${volume.device}` : '';
    item.append(
      head,
      meter,
      element('div',
        `${formatBytes(used)} / ${formatBytes(total)} · 剩余 ${formatBytes(Math.max(0, total - used))}` +
          device,
        { class: 'performance-volume-meta' }),
    );
    return item;
  }));
}
function renderPerformanceInterfaces(interfaces) {
  const container = $('performance-network-interfaces');
  if (!container) return;
  const rows = Array.isArray(interfaces) ? interfaces.slice(0, 16) : [];
  if (!rows.length) {
    container.replaceChildren(element('p', '暂无可用网卡吞吐数据。', {
      class: 'performance-list-empty',
    }));
    return;
  }
  container.replaceChildren(...rows.map((networkInterface) => {
    const name = networkInterface?.name || '网卡';
    const item = element('div', null, { class: 'performance-interface-item' });
    const head = element('div', null, { class: 'performance-interface-head' });
    head.append(
      element('span', name, { class: 'performance-interface-name', title: name }),
      element('span',
        `↓ ${formatRate(networkInterface?.recv_bps)} · ↑ ${formatRate(networkInterface?.sent_bps)}`,
        { class: 'performance-interface-value' }),
    );
    const details = [];
    if (networkInterface?.errin_per_second !== null || networkInterface?.errout_per_second !== null) {
      details.push(`错误 收 ${formatOptionalPerSecond(networkInterface?.errin_per_second)} / ` +
        `发 ${formatOptionalPerSecond(networkInterface?.errout_per_second)}`);
    }
    if (networkInterface?.dropin_per_second !== null || networkInterface?.dropout_per_second !== null) {
      details.push(`丢包 收 ${formatOptionalPerSecond(networkInterface?.dropin_per_second)} / ` +
        `发 ${formatOptionalPerSecond(networkInterface?.dropout_per_second)}`);
    }
    if (details.length) {
      item.append(element('div', details.join(' · '), { class: 'performance-interface-meta' }));
    }
    item.prepend(head);
    return item;
  }));
}
function syncPerformanceFactGrids() {
  for (const grid of document.querySelectorAll('.performance-fact-grid')) {
    for (const child of [...grid.children]) {
      if (child.classList.contains('performance-fact-empty')) child.remove();
    }
    const columns = Math.max(
      1,
      Number(getComputedStyle(grid).getPropertyValue('--performance-fact-columns')) || 3,
    );
    const count = [...grid.children].filter(
      (child) => child.classList.contains('performance-fact') && !child.hidden,
    ).length;
    const missing = (columns - (count % columns)) % columns;
    for (let index = 0; index < missing; index += 1) {
      grid.append(element('div', null, {
        class: 'performance-fact performance-fact-empty',
        'aria-hidden': 'true',
      }));
    }
  }
}
let performanceFactSyncFrame = null;
function schedulePerformanceFactGridSync() {
  if (performanceFactSyncFrame !== null) {
    cancelAnimationFrame(performanceFactSyncFrame);
  }
  performanceFactSyncFrame = requestAnimationFrame(() => {
    performanceFactSyncFrame = null;
    syncPerformanceFactGrids();
  });
}
function revealPerformanceCategory(button) {
  if (!button) return;
  const categories = button.closest('.performance-categories');
  if (!categories ||
      (categories.scrollWidth <= categories.clientWidth &&
       categories.scrollHeight <= categories.clientHeight)) {
    return;
  }
  const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ? 'auto' : 'smooth';
  button.scrollIntoView({block: 'nearest', inline: 'nearest', behavior});
}
function setPerformanceCategory(category, { refreshProcesses = false, reveal = false } = {}) {
  const selected = performanceCategories.includes(category) ? category : 'overview';
  const previous = state.performanceCategory;
  state.performanceCategory = selected;
  document.querySelectorAll('[data-performance-category]').forEach((button) => {
    const active = button.dataset.performanceCategory === selected;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
    button.tabIndex = active ? 0 : -1;
  });
  const activeButton = document.querySelector(`[data-performance-category="${selected}"]`);
  const current = $('performance-nav-current');
  if (current) {
    current.textContent =
      activeButton?.querySelector('.performance-category-name')?.textContent || selected;
  }
  if (reveal) revealPerformanceCategory(activeButton);
  document.querySelectorAll('[data-performance-view]').forEach((view) => {
    view.hidden = view.dataset.performanceView !== selected;
  });
  if (selected === 'processes') {
    if (previous !== selected) renderProcessTree(state.performanceProcesses);
    if (refreshProcesses) refreshPerformanceProcesses().catch(notifyError);
  }
}
const threadStateLabels = {
  R: '运行', S: '睡眠', D: '不可中断', Z: '僵尸', T: '停止', t: '跟踪停止',
  X: '结束', I: '空闲', K: '内核', W: '换出', P: '停放',
};
const processMemoryLabels = {
  rss: 'RSS', vms: 'VMS', shared: '共享', text: '代码', lib: '库', data: '数据',
  dirty: '脏页', uss: '独占', pss: '比例', swap: '交换', private: '私有',
  peak_wset: '峰值工作集', wset: '工作集', peak_paged_pool: '峰值分页池',
  paged_pool: '分页池', peak_nonpaged_pool: '峰值非分页池', nonpaged_pool: '非分页池',
  pagefile: '页面文件', peak_pagefile: '峰值页面文件', num_page_faults: '缺页',
  pfaults: '缺页', pageins: '换入页',
};
const processMemoryByteKeys = new Set([
  'rss', 'vms', 'shared', 'text', 'lib', 'data', 'dirty', 'uss', 'pss', 'swap',
  'private', 'peak_wset', 'wset', 'peak_paged_pool', 'paged_pool',
  'peak_nonpaged_pool', 'nonpaged_pool', 'pagefile', 'peak_pagefile',
]);
function processDetailKey(process) {
  const createTime = Number(process && process.create_time);
  return `${process.pid}:${Number.isFinite(createTime) ? createTime.toFixed(3) : '0.000'}`;
}
function processFact(label, value) {
  const fact = element('span', null, { class: 'process-fact' });
  fact.append(
    element('span', label, { class: 'process-fact-label' }),
    element('span', value, { class: 'process-fact-value' }),
  );
  return fact;
}
function processCommand(label, value) {
  const row = element('div', null, { class: 'process-command' });
  row.append(
    element('span', label, { class: 'process-command-label' }),
    element('span', value || '—', { class: 'process-command-value' }),
  );
  return row;
}
function formatAffinity(value) {
  if (!Array.isArray(value) || !value.length) return '—';
  const numbers = [...new Set(value.map((item) => Number(item)).filter(Number.isFinite))]
    .sort((left, right) => left - right);
  if (!numbers.length) return '—';
  const ranges = [];
  let start = numbers[0];
  let end = start;
  for (const number of numbers.slice(1)) {
    if (number === end + 1) {
      end = number;
      continue;
    }
    ranges.push(start === end ? String(start) : `${start}-${end}`);
    start = number;
    end = number;
  }
  ranges.push(start === end ? String(start) : `${start}-${end}`);
  return `${ranges.join(', ')}（${numbers.length}）`;
}
function formatContextSwitches(value) {
  if (!value) return '—';
  return `自愿 ${formatCount(value.voluntary)} / 非自愿 ${formatCount(value.involuntary)}`;
}
function formatIoCounters(value) {
  if (!value) return '—';
  const parts = [];
  if (value.read_bytes !== undefined) {
    parts.push(`读 ${formatBytes(value.read_bytes)}（${formatCount(value.read_count)} 次）`);
  }
  if (value.write_bytes !== undefined) {
    parts.push(`写 ${formatBytes(value.write_bytes)}（${formatCount(value.write_count)} 次）`);
  }
  if (value.other_bytes !== undefined) {
    parts.push(`其他 ${formatBytes(value.other_bytes)}（${formatCount(value.other_count)} 次）`);
  }
  return parts.length ? parts.join(' · ') : '—';
}
function formatIoPriority(value) {
  if (!value || value.class === null || value.class === undefined) return '—';
  return value.value === null || value.value === undefined
    ? `等级 ${value.class}` : `等级 ${value.class}:${value.value}`;
}
function processThreadKey(thread) {
  const id = thread && thread.id !== null && thread.id !== undefined ? thread.id : '?';
  const start = thread && thread.start_time !== null && thread.start_time !== undefined
    ? thread.start_time : '';
  return `${id}:${start}`;
}
function processThreadElement(thread) {
  const row = element('li', null, {
    class: 'process-thread',
    'data-thread-key': processThreadKey(thread),
  });
  const names = [];
  if (thread.name) names.push(thread.name);
  if (thread.python_name && thread.python_name !== thread.name) names.push(thread.python_name);
  const name = names.length ? ` · ${names.join(' / ')}` : '';
  row.append(element('span', `线程 ${formatCount(thread.id)}${name}`, {
    class: 'process-thread-id',
  }));
  if (thread.state) {
    row.append(element('span', threadStateLabels[thread.state] || thread.state, {
      class: 'process-thread-state',
      title: `状态 ${thread.state}`,
    }));
  }
  const meta = [];
  if (thread.cpu_percent !== null && thread.cpu_percent !== undefined) {
    meta.push(`CPU ${formatPercent(thread.cpu_percent)}`);
  }
  meta.push(`用户 ${formatCpuTime(thread.user)}`);
  meta.push(`内核 ${formatCpuTime(thread.system)}`);
  if (thread.priority !== null && thread.priority !== undefined) {
    meta.push(`优先级 ${formatSignedCount(thread.priority)}`);
  }
  if (thread.nice !== null && thread.nice !== undefined) {
    meta.push(`Nice ${formatSignedCount(thread.nice)}`);
  }
  if (thread.processor !== null && thread.processor !== undefined) {
    meta.push(`处理器 ${formatCount(thread.processor)}`);
  }
  if (thread.ctx_switches) meta.push(`切换 ${formatContextSwitches(thread.ctx_switches)}`);
  if (thread.wchan) meta.push(`等待 ${thread.wchan}`);
  if (thread.start_time !== null && thread.start_time !== undefined) {
    meta.push(`启动 ${formatDateTime(thread.start_time)}`);
  }
  if (thread.start_module) meta.push(`起始 ${thread.start_module}`);
  row.append(element('span', meta.join(' · '), { class: 'process-thread-cpu' }));
  return row;
}
function processNodeElement(process, level, rootPid, sampledAt) {
  const processKey = processDetailKey(process);
  const node = element('li', null, {
    class: 'process-node',
    role: 'treeitem',
    'aria-level': String(level),
    'data-process-key': processKey,
  });
  const branch = element('details', null, {
    class: 'process-branch',
    'data-process-branch': processKey,
  });
  const branchOpen = state.performanceProcessOpen[processKey];
  branch.open = branchOpen === undefined ? true : Boolean(branchOpen);
  branch.addEventListener('toggle', () => {
    state.performanceProcessOpen[processKey] = branch.open;
  });
  const row = element('summary', null, { class: 'process-row' });
  row.append(element('span', process.name || `PID ${formatCount(process.pid)}`, {
    class: 'process-name',
  }));
  if (process.pid === rootPid) {
    row.append(element('span', 'OlivOS 主进程', { class: 'process-root-badge' }));
  }
  row.append(element('span', `PID ${formatCount(process.pid)}`, { class: 'process-pid' }));
  const meta = [
    process.status || '',
    process.thread_count === null || process.thread_count === undefined
      ? '线程 —'
      : `${formatCount(process.thread_count)} 线程`,
    `CPU ${formatPercent(process.cpu_percent)}`,
    `内存 ${formatBytes(process.memory_rss)}`,
  ].filter(Boolean);
  if (process.memory_percent !== null && process.memory_percent !== undefined) {
    meta.push(`${formatPercent(process.memory_percent)} 内存占比`);
  }
  if (process.handles !== null && process.handles !== undefined) {
    meta.push(`句柄 ${formatCount(process.handles)}`);
  }
  if (process.num_fds !== null && process.num_fds !== undefined) {
    meta.push(`文件描述符 ${formatCount(process.num_fds)}`);
  }
  row.append(element('span', meta.join(' · '), { class: 'process-meta' }));
  const body = element('div', null, { class: 'process-body' });
  const facts = element('div', null, {
    class: 'process-facts',
    'data-process-section': 'facts',
  });
  const createTime = Number(process.create_time);
  const uptime = Number.isFinite(createTime) ? Math.max(0, Number(sampledAt) - createTime) : 0;
  facts.append(
    processFact('父进程', process.ppid ? formatCount(process.ppid) : '—'),
    processFact('用户', process.username || '—'),
    processFact('启动', formatDateTime(process.create_time)),
    processFact('运行', formatDuration(uptime)),
    processFact('虚拟内存', formatBytes(process.memory_vms)),
    processFact('内存占比', formatOptionalPercent(process.memory_percent)),
    processFact('CPU 时间',
      `用户 ${formatCpuTime(process.cpu_user)} / 内核 ${formatCpuTime(process.cpu_system)}`),
  );
  if (process.memory_peak !== null && process.memory_peak !== undefined) {
    facts.append(processFact('峰值内存', formatBytes(process.memory_peak)));
  }
  if (process.memory_private !== null && process.memory_private !== undefined) {
    facts.append(processFact('私有内存', formatBytes(process.memory_private)));
  }
  if (process.memory_shared !== null && process.memory_shared !== undefined) {
    facts.append(processFact('共享内存', formatBytes(process.memory_shared)));
  }
  if (process.cpu_children_user !== null || process.cpu_children_system !== null) {
    facts.append(processFact('子进程 CPU',
      `用户 ${formatCpuTime(process.cpu_children_user)} / ` +
      `内核 ${formatCpuTime(process.cpu_children_system)}`));
  }
  if (process.cpu_iowait !== null && process.cpu_iowait !== undefined) {
    facts.append(processFact('I/O 等待', formatCpuTime(process.cpu_iowait)));
  }
  if (process.nice !== null && process.nice !== undefined) {
    facts.append(processFact('优先级', formatSignedCount(process.nice)));
  }
  if (process.io_priority) facts.append(processFact('I/O 优先级', formatIoPriority(process.io_priority)));
  if (process.cpu_affinity) facts.append(processFact('CPU 亲和性', formatAffinity(process.cpu_affinity)));
  if (process.ctx_switches) {
    facts.append(processFact('上下文切换', formatContextSwitches(process.ctx_switches)));
  }
  if (process.io) facts.append(processFact('磁盘 I/O', formatIoCounters(process.io)));
  body.append(facts);
  if (process.exe) {
    const command = processCommand('可执行文件', process.exe);
    command.dataset.processSection = 'exe';
    body.append(command);
  }
  if (process.cmdline) {
    const command = processCommand('命令行', process.cmdline);
    command.dataset.processSection = 'cmdline';
    body.append(command);
  }
  if (Array.isArray(process.threads)) {
    if (process.threads.length) {
      const threads = element('ul', null, {
        class: 'process-threads',
        role: 'group',
        'aria-label': `PID ${formatCount(process.pid)} 的线程`,
        'data-process-section': 'threads',
      });
      for (const thread of process.threads) threads.append(processThreadElement(thread));
      body.append(threads);
      if (process.threads_truncated) {
        body.append(element('p', '部分线程的扩展信息未读取。', {
          class: 'process-empty',
          'data-process-section': 'threads-truncated',
        }));
      }
    } else {
      body.append(element('p', '未读取到线程。', {
        class: 'process-empty',
        'data-process-section': 'threads-empty',
      }));
    }
  } else {
    body.append(element('p', '线程信息不可用。', {
      class: 'process-empty',
      'data-process-section': 'threads-unavailable',
    }));
  }
  const detail = element('div', null, {
    class: 'process-detail',
    'data-process-detail': processKey,
    'data-process-section': 'detail',
  });
  body.append(detail);
  renderProcessDetail(detail, process);
  if (Array.isArray(process.children) && process.children.length) {
    const children = element('ul', null, {
      class: 'process-children',
      role: 'group',
      'aria-label': `PID ${formatCount(process.pid)} 的子进程`,
      'data-process-section': 'children',
    });
    for (const child of process.children) {
      children.append(processNodeElement(child, level + 1, rootPid, sampledAt));
    }
    body.append(children);
  }
  branch.append(row, body);
  node.append(branch);
  return node;
}
function formatProcessAddress(value) {
  if (!value || !value.ip) return '—';
  return `${value.ip}:${value.port === null || value.port === undefined ? '—' : value.port}`;
}
function processDetailList(process, groupKey, title, collection, itemText) {
  const processKey = processDetailKey(process);
  const groupStates = state.performanceProcessDetailGroups[processKey] || {};
  const group = element('details', null, {
    class: 'process-detail-group',
    'data-process-detail-group': groupKey,
  });
  group.open = Boolean(groupStates[groupKey]);
  group.addEventListener('toggle', () => {
    groupStates[groupKey] = group.open;
    state.performanceProcessDetailGroups[processKey] = groupStates;
  });
  group.append(element('summary', `${title}（${formatCount(collection ? collection.count : 0)}）`));
  if (!collection) {
    group.append(element('p', '不可用', { class: 'process-empty' }));
    return group;
  }
  if (!collection.items.length) {
    group.append(element('p', '无', { class: 'process-empty' }));
    return group;
  }
  const list = element('ul', null, { class: 'process-detail-list' });
  for (const item of collection.items) list.append(element('li', itemText(item)));
  if (collection.truncated) {
    list.append(element('li', `仅显示前 ${formatCount(collection.items.length)} 项`, {
      class: 'process-empty',
    }));
  }
  group.append(list);
  return group;
}
function renderProcessDetail(container, process) {
  const entry = state.performanceProcessDetails[processDetailKey(process)];
  if (!entry) {
    container.replaceChildren(button(
      '读取文件、连接与内存详情',
      () => loadProcessDetail(process, container),
      'process-detail-button',
    ));
    return;
  }
  if (entry.loading) {
    container.replaceChildren(element('p', '正在读取进程详情…', { class: 'process-empty' }));
    return;
  }
  if (entry.error) {
    container.replaceChildren(
      element('p', `读取进程详情失败：${entry.error}`, { class: 'process-empty' }),
      button('重试', () => loadProcessDetail(process, container), 'process-detail-button'),
    );
    return;
  }
  const data = entry.data;
  if (!data || !data.available) {
    const message = data && data.reason === 'process_changed'
      ? '进程已重启或 PID 已复用，请刷新进程树。'
      : data && data.reason === 'process_not_found' ? '进程已退出。' : '进程详情暂不可用。';
    container.replaceChildren(element('p', message, { class: 'process-empty' }));
    return;
  }
  const summary = element('div', null, { class: 'process-detail-summary' });
  summary.append(
    element('span', `打开文件 ${formatCount(data.open_files ? data.open_files.count : 0)}`),
    element('span', `网络连接 ${formatCount(data.connections ? data.connections.count : 0)}`),
    element('span', `内存映射 ${formatCount(data.memory_maps ? data.memory_maps.count : 0)}`),
  );
  container.replaceChildren(summary);
  if (data.memory_full) {
    const facts = element('div', null, { class: 'process-facts process-detail-facts' });
    for (const [key, value] of Object.entries(data.memory_full)) {
      if (!processMemoryLabels[key] || (value === 0 && key !== 'rss' && key !== 'vms')) continue;
      facts.append(processFact(
        processMemoryLabels[key],
        processMemoryByteKeys.has(key) ? formatBytes(value) : formatCount(value),
      ));
    }
    if (facts.childElementCount) container.append(facts);
  }
  container.append(processDetailList(process, 'files', '打开的文件', data.open_files, (item) => {
    const fd = item.fd === null || item.fd === undefined ? '' : ` · FD ${formatCount(item.fd)}`;
    const mode = item.mode ? ` · ${item.mode}` : '';
    return `${item.path || '—'}${fd}${mode}`;
  }));
  container.append(processDetailList(process, 'connections', '网络连接', data.connections, (item) => {
    const status = item.status ? ` · ${item.status}` : '';
    return `${formatProcessAddress(item.laddr)} → ${formatProcessAddress(item.raddr)}${status}`;
  }));
  container.append(processDetailList(process, 'maps', '内存映射', data.memory_maps, (item) => {
    const metrics = item.metrics || {};
    const rss = metrics.rss === undefined ? '—' : formatBytes(metrics.rss);
    const size = metrics.size === undefined ? '—' : formatBytes(metrics.size);
    return `${item.path || '[匿名]'} · RSS ${rss} · 大小 ${size}`;
  }));
  if (Array.isArray(data.errors) && data.errors.length) {
    container.append(element('p', `部分详情不可用：${data.errors.join('、')}`, {
      class: 'process-empty',
    }));
  }
  container.append(button(
    '重新读取',
    () => loadProcessDetail(process, container),
    'process-detail-button',
  ));
}
async function loadProcessDetail(process, container) {
  const key = processDetailKey(process);
  state.performanceProcessDetails[key] = { loading: true };
  const initial = document.querySelector(`[data-process-detail="${key}"]`) || container;
  renderProcessDetail(initial, process);
  try {
    const query = new URLSearchParams({ create_time: String(process.create_time ?? '') });
    const data = await api(`/api/performance/processes/${process.pid}?${query.toString()}`);
    state.performanceProcessDetails[key] = { data };
  } catch (error) {
    if (error.authHandled || error.authObsolete) throw error;
    state.performanceProcessDetails[key] = { error: error.message || '网络请求失败' };
  }
  const current = document.querySelector(`[data-process-detail="${key}"]`) || initial;
  renderProcessDetail(current, process);
}
function cleanupProcessDetails(data) {
  const valid = new Set();
  const walk = (nodes) => {
    for (const process of nodes || []) {
      valid.add(processDetailKey(process));
      walk(process.children);
    }
  };
  walk(data && data.roots);
  for (const key of Object.keys(state.performanceProcessDetails)) {
    if (!valid.has(key)) delete state.performanceProcessDetails[key];
  }
  for (const key of Object.keys(state.performanceProcessOpen)) {
    if (!valid.has(key)) delete state.performanceProcessOpen[key];
  }
  for (const key of Object.keys(state.performanceProcessDetailGroups)) {
    if (!valid.has(key)) delete state.performanceProcessDetailGroups[key];
  }
}
function processTreeNodeKey(node) {
  if (node.nodeType !== Node.ELEMENT_NODE) return null;
  if (node.dataset.processKey !== undefined) return node.dataset.processKey;
  if (node.dataset.threadKey !== undefined) return node.dataset.threadKey;
  if (node.dataset.processSection !== undefined) return node.dataset.processSection;
  if (node.dataset.processDetailGroup !== undefined) return node.dataset.processDetailGroup;
  return null;
}
function mergeProcessElement(existing, desired) {
  // details 的 open 是用户刚操作的实时状态；toggle 事件可能还在排队，不能按旧快照回写。
  const preserveOpen = existing.tagName === 'DETAILS';
  for (const attr of [...desired.attributes]) {
    if (preserveOpen && attr.name === 'open') continue;
    if (existing.getAttribute(attr.name) !== attr.value) existing.setAttribute(attr.name, attr.value);
  }
  for (const attr of [...existing.attributes]) {
    if (preserveOpen && attr.name === 'open') continue;
    if (!desired.hasAttribute(attr.name)) existing.removeAttribute(attr.name);
  }
}
function reconcileProcessNode(current, desired) {
  if (desired.nodeType === Node.TEXT_NODE) {
    if (current && current.nodeType === Node.TEXT_NODE) {
      if (current.nodeValue !== desired.nodeValue) current.nodeValue = desired.nodeValue;
      return current;
    }
    return desired;
  }
  if (desired.nodeType !== Node.ELEMENT_NODE) return desired;
  if (!current || current.nodeType !== Node.ELEMENT_NODE || current.tagName !== desired.tagName) {
    return desired;
  }
  mergeProcessElement(current, desired);
  reconcileProcessChildNodes(current, [...desired.childNodes]);
  return current;
}
function syncProcessChildNodes(parent, next) {
  const keep = new Set(next);
  for (const child of [...parent.childNodes]) {
    if (!keep.has(child)) child.remove();
  }
  let reference = parent.firstChild;
  for (const child of next) {
    if (child === reference) {
      reference = reference.nextSibling;
      continue;
    }
    parent.insertBefore(child, reference);
  }
}
function reconcileProcessChildNodes(parent, desired) {
  const current = [...parent.childNodes];
  // 详情容器同时包含有 key 的分组和无 key 的摘要、按钮；有 key 的子节点必须始终按 key 复用，
  // 否则内存信息增减会让分组的事件处理器绑定到其他分组的状态键。
  const keyed = new Map();
  const unkeyed = [];
  for (const node of current) {
    const key = processTreeNodeKey(node);
    if (key === null) unkeyed.push(node);
    else if (!keyed.has(key)) keyed.set(key, node);
  }
  let unkeyedIndex = 0;
  const next = desired.map((candidate) => {
    const key = processTreeNodeKey(candidate);
    if (key !== null) {
      const live = keyed.get(key);
      if (!live) return candidate;
      keyed.delete(key);
      return reconcileProcessNode(live, candidate);
    }
    const live = unkeyed[unkeyedIndex];
    unkeyedIndex += 1;
    return live ? reconcileProcessNode(live, candidate) : candidate;
  });
  syncProcessChildNodes(parent, next);
}
function reconcileProcessNodes(parent, desired) {
  reconcileProcessChildNodes(parent, desired);
}
function renderProcessTree(data) {
  const container = $('performance-process-tree');
  if (!container) return;
  const note = $('performance-processes-note');
  const readout = $('performance-processes-readout');
  if (!data) {
    if (note) {
      note.hidden = false;
      note.textContent = '正在读取 OlivOS 进程树…';
    }
    if (readout) readout.textContent = '';
    container.replaceChildren();
    return;
  }
  if (!data.available || !Array.isArray(data.roots) || !data.roots.length) {
    if (note) {
      note.hidden = false;
      note.textContent = data.reason === 'statistics_unavailable'
        ? '统计组件暂不可用，无法读取进程树。'
        : 'OlivOS 进程树暂不可用。';
    }
    if (readout) readout.textContent = '';
    container.replaceChildren();
    return;
  }
  if (note) {
    note.hidden = true;
    note.textContent = '';
  }
  if (readout) {
    readout.textContent = `${formatCount(data.process_count)} 个进程 · ` +
      `${formatCount(data.thread_count)} 个线程 · ${sampledAtText(data.sampled_at)}`;
  }
  let list = container.querySelector('.process-tree-list');
  if (!list) {
    list = element('ul', null, {
      class: 'process-tree-list',
      role: 'group',
      'aria-label': 'OlivOS 进程与线程树',
    });
    container.replaceChildren(list);
  }
  reconcileProcessNodes(list, data.roots.map(
    (process) => processNodeElement(process, 1, data.root_pid, data.sampled_at)));
}
let processTreeRequestId = 0;
async function refreshPerformanceProcesses() {
  const requestId = ++processTreeRequestId;
  let data;
  try {
    data = await api('/api/performance/processes');
  } catch (error) {
    if (requestId === processTreeRequestId && !error.authHandled && !error.authObsolete) {
      state.performanceProcesses = {
        available: false,
        reason: 'statistics_unavailable',
        roots: [],
      };
      if (state.page === 'performance' && state.performanceCategory === 'processes') {
        renderProcessTree(state.performanceProcesses);
      }
    }
    throw error;
  }
  if (requestId !== processTreeRequestId) return;
  state.performanceProcesses = data;
  cleanupProcessDetails(data);
  if (state.page === 'performance' && state.performanceCategory === 'processes') {
    renderProcessTree(data);
  }
}
function renderPerformanceMini(container, values, { zeroPadding = false, capacity = 60 } = {}) {
  if (!container) return;
  const width = 100;
  const height = 22;
  const padding = 2;
  const windowCapacity = Math.max(2, Math.floor(Number(capacity)) || 60);
  const sampled = resampleTrendValues(values, windowCapacity, { zeroPadding });
  if (!sampled.hasData && !zeroPadding) {
    container.replaceChildren();
    return;
  }
  const numeric = sampled.values;
  const percentage = ['cpu', 'memory', 'disk'].includes(container.dataset.performanceMini);
  const maximum = percentage ? 100 : Math.max(1, ...numeric);
  const xFor = (index) => padding + (width - padding * 2) * (index / (windowCapacity - 1));
  const yFor = (value) => (
    height - padding - (height - padding * 2) * Math.min(1, value / maximum)
  );
  const points = numeric.map((value, index) => (
    `${xFor(index).toFixed(2)},${yFor(value).toFixed(2)}`
  ));
  const svg = svgNode('svg', {
    viewBox: `0 0 ${width} ${height}`,
    preserveAspectRatio: 'none',
    'aria-hidden': 'true',
  });
  svg.dataset.maximum = String(maximum);
  const baseline = height - padding;
  const area = svgNode('path', {
    class: 'mini-area',
    d: `M ${padding.toFixed(2)},${baseline.toFixed(2)} L ${points.join(' L ')} ` +
      `L ${xFor(numeric.length - 1).toFixed(2)},${baseline.toFixed(2)} Z`,
  });
  const line = svgNode('polyline', { class: 'mini-line', points: points.join(' ') });
  svg.append(area, line);
  container.replaceChildren(svg);
}
function showPerformanceStatisticsUnavailable(reason) {
  state.performanceStatistics = null;
  if (state.performanceNavOpen) setPerformanceNavOpen(false);
  const content = $('performance-content');
  const note = $('performance-statistics-note');
  const sampled = $('performance-sampled');
  if (content) content.hidden = true;
  if (note) {
    note.hidden = false;
    note.textContent = reason === 'statistics_warming_up'
      ? '监测组件正在启动，稍后自动重试。'
      : '性能与流量统计暂不可用，不影响其他功能。';
  }
  if (sampled) sampled.textContent = '';
}
function renderPerformanceStatistics(data) {
  if (!data?.available || !data.performance || !data.traffic) {
    showPerformanceStatisticsUnavailable(data?.reason);
    return;
  }
  state.performanceStatistics = data;
  const content = $('performance-content');
  const note = $('performance-statistics-note');
  const sampled = $('performance-sampled');
  if (content) content.hidden = false;
  if (note) {
    note.hidden = true;
    note.textContent = '';
  }

  const performance = data.performance;
  const traffic = data.traffic;
  const system = performance.system || {};
  const cpu = performance.cpu || {};
  const memory = performance.memory || {};
  const disk = performance.disk || {};
  const network = performance.network || {};
  const process = performance.process || {};
  const selectedPerformanceWindow = performance.windows?.[state.performanceWindow] || null;
  const selectedTrafficWindow = traffic.windows?.[state.performanceWindow] || null;
  const history = selectedPerformanceWindow || performance.history || {};
  const timestamps = history.timestamps || [];
  const trafficHistory = selectedTrafficWindow
    ? trafficWindowHistory(selectedTrafficWindow)
    : (traffic.history || []);
  const trafficCapacity = selectedTrafficWindow?.capacity ?? traffic.history_capacity;
  const performanceMiniCapacity = Number(history.capacity) || 60;
  const trafficMiniCapacity = Number(trafficCapacity) || 60;
  const trafficInterval = Number(
    selectedTrafficWindow?.interval ?? traffic.bucket_seconds);
  const includeDate = performanceWindowUsesDate.has(state.performanceWindow);
  const trafficFormatValue = (value) => formatTrafficBucket(value, trafficInterval);
  syncPerformanceWindowControls(data);
  if (sampled) {
    sampled.textContent = sampledAtText(data.sampled_at);
  }
  const loadValue = formatLoad(cpu.load_1);
  const loadText = [cpu.load_1, cpu.load_5, cpu.load_15].map(formatLoad).join(' / ');
  const systemLoad = loadValue === '—' ? '' : ` · 负载 ${loadValue}`;
  const processCpu = formatCpuCores(process.cpu_percent);
  const swap = memory.swap_percent === null || memory.swap_percent === undefined
    ? '—'
    : formatPercent(memory.swap_percent);
  const processSummary = `${formatCount(process.count)} 进程 · ` +
    `${formatOptionalCount(process.threads)} 线程`;
  const processScaleItems = [processSummary];
  if (process.handles !== null && process.handles !== undefined) {
    processScaleItems.push(`${formatCount(process.handles)} 句柄`);
  }
  if (process.num_fds !== null && process.num_fds !== undefined) {
    processScaleItems.push(`${formatCount(process.num_fds)} 文件描述符`);
  }
  const processScale = processScaleItems.join(' · ');
  const physicalCount = formatOptionalCount(cpu.physical_count);
  const frequency = formatFrequency(cpu.frequency_mhz);
  const failedRate = failureRatePercent(traffic);
  const overviewSummary = [
    [system.os, system.os_release].filter(Boolean).join(' '),
    system.architecture,
    [system.python_implementation, system.python_version].filter(Boolean).join(' '),
  ].filter(Boolean).join(' · ');

  setPerformanceReadout('performance-overview-readout', overviewSummary || '—');
  setPerformanceReadout('performance-cpu-readout',
    `${formatPercent(cpu.percent)} · ${formatCount(cpu.count)} 逻辑核心 · ` +
    `${physicalCount} 物理核心 · ${frequency}${systemLoad}`);
  setPerformanceReadout('performance-memory-readout',
    `${formatPercent(memory.percent)} · ${formatBytes(memory.used)} / ${formatBytes(memory.total)} · Swap ${swap}`);
  setPerformanceReadout('performance-disk-usage-readout',
    `${formatPercent(disk.percent)} · ${formatBytes(disk.used)} / ${formatBytes(disk.total)} · ` +
    `${formatCount(disk.volume_count)} 个卷`);
  setPerformanceReadout('performance-disk-io-readout',
    `读取 ${formatRate(disk.read_bps)}（${formatOptionalPerSecond(disk.read_iops, '次')}，` +
    `${formatOptionalLatency(disk.read_latency_ms)}） · ` +
    `写入 ${formatRate(disk.write_bps)}（${formatOptionalPerSecond(disk.write_iops, '次')}，` +
    `${formatOptionalLatency(disk.write_latency_ms)}）`);
  setPerformanceReadout('performance-network-readout',
    `下行 ${formatRate(network.recv_bps)} · 上行 ${formatRate(network.sent_bps)}`);
  setPerformanceReadout('performance-load-readout',
    `OlivOS 负载 ${processCpu} · ${processScale}`);
  setPerformanceReadout('performance-process-count-readout', processSummary);
  setPerformanceReadout('performance-process-memory-readout',
    `${formatBytes(process.rss)} · ${processScale}`);
  setPerformanceReadout('performance-traffic-readout',
    `入站 ${formatCount(traffic.inbound_per_minute)} 条/分钟 · ` +
    `出站 ${formatCount(traffic.outbound_per_minute)} 条/分钟 · ` +
    `失败 ${formatCount(traffic.failed_per_minute)} 条/分钟`);

  setPerformanceSummary('cpu', formatPercent(cpu.percent));
  setPerformanceSummary('overview', `${formatCount(cpu.count)} 核 · ${formatBytes(memory.total)}`);
  setPerformanceSummary('memory', formatPercent(memory.percent));
  setPerformanceSummary('disk', formatPercent(disk.percent));
  setPerformanceSummary('network', `↓ ${formatRate(network.recv_bps)}`);
  setPerformanceReadout('performance-network-value',
    `↓ ${formatRate(network.recv_bps)} · ↑ ${formatRate(network.sent_bps)}`);
  setPerformanceSummary('traffic',
    `↓ ${formatCount(traffic.inbound_per_minute)} / ↑ ${formatCount(traffic.outbound_per_minute)}`);
  setPerformanceSummary('processes', processSummary);
  setPerformanceSummary('processes-detail', processScale);

  setPerformanceStat('cpu-model', formatOptionalText(system.cpu_model));
  setPerformanceStat('cpu-logical', formatCount(cpu.count));
  setPerformanceStat('system-cpu-model', formatOptionalText(system.cpu_model));
  setPerformanceStat('system-os', formatOptionalText(system.os));
  setPerformanceStat('system-os-release', formatOptionalText(system.os_release));
  setPerformanceStat('system-os-version', formatOptionalText(system.os_version));
  setPerformanceStat('system-architecture', formatOptionalText(system.architecture));
  setPerformanceStat('system-hostname', formatOptionalText(system.hostname));
  setPerformanceStat('system-python-version', formatOptionalText(system.python_version));
  setPerformanceStat('system-python-implementation', formatOptionalText(system.python_implementation));
  setPerformanceStat('system-cpu-logical', formatCount(cpu.count));
  setPerformanceStat('system-cpu-physical', physicalCount);
  setPerformanceStat('system-memory-total', formatBytes(memory.total));
  setPerformanceStat('system-working-directory', formatOptionalText(system.working_directory));
  setPerformanceStat('cpu-physical', physicalCount);
  setPerformanceStat('cpu-frequency', frequency);
  setPerformanceStat('cpu-machine-load', loadText);
  setPerformanceStat('cpu-load', processCpu);
  setPerformanceStat('cpu-processes', formatOptionalCount(process.count));
  setPerformanceStat('cpu-threads', formatOptionalCount(process.threads));
  const handlesFact = $('performance-fact-handles');
  if (handlesFact) {
    const handlesHidden = process.handles === null || process.handles === undefined;
    if (handlesFact.hidden !== handlesHidden) {
      handlesFact.hidden = handlesHidden;
      schedulePerformanceFactGridSync();
    }
  }
  setPerformanceStat('cpu-handles', formatOptionalCount(process.handles));
  setPerformanceStat('memory-used', formatBytes(memory.used));
  setPerformanceStat('memory-available', formatBytes(memory.available));
  setPerformanceStat('memory-total', formatBytes(memory.total));
  setPerformanceStat('memory-free', formatOptionalBytes(memory.free));
  setPerformanceStat('memory-cached', formatOptionalBytes(memory.cached));
  setPerformanceStat('memory-buffers', formatOptionalBytes(memory.buffers));
  setPerformanceStat('memory-shared', formatOptionalBytes(memory.shared));
  setPerformanceStat('memory-swap', swap);
  setPerformanceStat('memory-swap-total', formatOptionalBytes(memory.swap_total));
  setPerformanceStat('memory-swap-used', formatOptionalBytes(memory.swap_used));
  setPerformanceStat('memory-swap-free', formatOptionalBytes(memory.swap_free));
  setPerformanceStat('memory-swap-in', formatRate(memory.swap_in_bps));
  setPerformanceStat('memory-swap-out', formatRate(memory.swap_out_bps));
  setPerformanceStat('disk-percent', formatPercent(disk.percent));
  setPerformanceStat('disk-used', formatBytes(disk.used));
  setPerformanceStat('disk-total', formatBytes(disk.total));
  setPerformanceStat('disk-volumes', `${formatCount(disk.volume_count)} 个卷`);
  setPerformanceStat('disk-read', formatRate(disk.read_bps));
  setPerformanceStat('disk-write', formatRate(disk.write_bps));
  setPerformanceStat('disk-read-iops', formatOptionalPerSecond(disk.read_iops, '次'));
  setPerformanceStat('disk-write-iops', formatOptionalPerSecond(disk.write_iops, '次'));
  setPerformanceStat('disk-read-latency', formatOptionalLatency(disk.read_latency_ms));
  setPerformanceStat('disk-write-latency', formatOptionalLatency(disk.write_latency_ms));
  setPerformanceStat('network-recv', formatRate(network.recv_bps));
  setPerformanceStat('network-sent', formatRate(network.sent_bps));
  setPerformanceStat('network-packets-recv',
    `${formatCount(network.packets_recv_per_second)} 个/秒`);
  setPerformanceStat('network-packets-sent',
    `${formatCount(network.packets_sent_per_second)} 个/秒`);
  setPerformanceStat('network-errors',
    `收 ${formatOptionalPerSecond(network.errin_per_second)} / ` +
    `发 ${formatOptionalPerSecond(network.errout_per_second)}`);
  setPerformanceStat('network-drops',
    `收 ${formatOptionalPerSecond(network.dropin_per_second)} / ` +
    `发 ${formatOptionalPerSecond(network.dropout_per_second)}`);
  setPerformanceStat('network-connections', formatOptionalCount(network.connection_count));
  setPerformanceStat('network-tcp-states', tcpStatesText(network.tcp_states));
  setPerformanceStat('traffic-in', `${formatCount(traffic.inbound_per_minute)} 条/分钟`);
  setPerformanceStat('traffic-out', `${formatCount(traffic.outbound_per_minute)} 条/分钟`);
  setPerformanceStat('traffic-in-total', formatCount(traffic.inbound_total));
  setPerformanceStat('traffic-out-total', formatCount(traffic.outbound_total));
  setPerformanceStat('traffic-events', `${formatCount(traffic.event_per_minute)} 条/分钟`);
  setPerformanceStat('traffic-failed', `${formatCount(traffic.failed_per_minute)} 条/分钟`);
  setPerformanceStat('traffic-failed-rate', formatPercent(failedRate));
  setPerformanceStat('traffic-failed-total', formatCount(traffic.failed_total));

  renderPerformanceCores(cpu.per_cpu_percent);
  renderPerformanceVolumes(disk.volumes);
  renderPerformanceInterfaces(network.interfaces);

  renderPerformanceMini(
    document.querySelector('[data-performance-mini="cpu"]'), history.cpu_percent || [],
    {capacity: performanceMiniCapacity});
  renderPerformanceMini(
    document.querySelector('[data-performance-mini="memory"]'), history.memory_percent || [],
    {capacity: performanceMiniCapacity});
  renderPerformanceMini(
    document.querySelector('[data-performance-mini="disk"]'), history.disk_percent || [],
    {capacity: performanceMiniCapacity});
  renderPerformanceMini(
    document.querySelector('[data-performance-mini="network"]'), history.network_recv_bps || [],
    {capacity: performanceMiniCapacity});
  renderPerformanceMini(
    document.querySelector('[data-performance-mini="traffic"]'),
    trafficBucketValues(traffic, 'inbound', trafficHistory),
    {zeroPadding: true, capacity: trafficMiniCapacity});
  renderPerformanceMini(
    document.querySelector('[data-performance-mini="processes"]'), history.process_threads || [],
    {capacity: performanceMiniCapacity});

  renderTrend($('performance-cpu-chart'), [
    {
      className: 'chart-series-cpu', legendClass: 'legend-cpu', label: 'CPU 使用率',
      formatValue: formatPercent, values: history.cpu_percent || [], percentage: true,
    },
    {
      className: 'chart-series-machine-load', legendClass: 'legend-machine-load', label: '负载',
      formatValue: formatLoad, values: history.load_1 || [],
    },
  ], null, history.capacity, { timestamps, includeDate });
  renderTrend($('performance-memory-chart'), [
    {
      className: 'chart-series-memory', legendClass: 'legend-memory', label: '内存使用率',
      formatValue: formatPercent, values: history.memory_percent || [], percentage: true,
    },
    {
      className: 'chart-series-swap', legendClass: 'legend-swap', label: 'Swap 使用率',
      formatValue: formatPercent, values: history.swap_percent || [], percentage: true,
    },
    {
      className: 'chart-series-swap-in', legendClass: 'legend-swap-in', label: '换入',
      formatValue: formatRate, values: history.swap_in_bps || [],
    },
    {
      className: 'chart-series-swap-out', legendClass: 'legend-swap-out', label: '换出',
      formatValue: formatRate, values: history.swap_out_bps || [],
    },
  ], null, history.capacity, { timestamps, includeDate, scale: 'log' });
  renderTrend($('performance-disk-usage-chart'), [
    {
      className: 'chart-series-disk', legendClass: 'legend-disk', label: '磁盘占用率',
      formatValue: formatPercent, values: history.disk_percent || [], percentage: true,
    },
  ], 100, history.capacity, { timestamps, includeDate });
  renderTrend($('performance-disk-io-chart'), [
    {
      className: 'chart-series-disk-read', legendClass: 'legend-disk-read', label: '读取',
      formatValue: formatRate, values: history.disk_read_bps || [],
    },
    {
      className: 'chart-series-disk-write', legendClass: 'legend-disk-write', label: '写入',
      formatValue: formatRate, values: history.disk_write_bps || [],
    },
  ], null, history.capacity, { timestamps, includeDate, scale: 'log' });
  renderTrend($('performance-network-chart'), [
    {
      className: 'chart-series-network-down', legendClass: 'legend-network-down', label: '网络下行',
      formatValue: formatRate, values: history.network_recv_bps || [],
    },
    {
      className: 'chart-series-network-up', legendClass: 'legend-network-up', label: '网络上行',
      formatValue: formatRate, values: history.network_sent_bps || [],
    },
  ], null, history.capacity, { timestamps, includeDate, scale: 'log' });
  renderTrend($('performance-load-chart'), [
    {
      className: 'chart-series-load', legendClass: 'legend-load', label: 'OlivOS 负载',
      formatValue: formatCpuCores, values: history.process_cpu_percent || [],
    },
  ], null, history.capacity, { timestamps, includeDate });
  renderTrend($('performance-process-count-chart'), [
    {
      className: 'chart-series-process-count', legendClass: 'legend-process-count', label: '进程数',
      formatValue: formatCount, values: history.process_count || [],
    },
    {
      className: 'chart-series-process-thread-count', legendClass: 'legend-process-thread-count',
      label: '线程数', formatValue: formatCount, values: history.process_threads || [],
    },
  ], null, history.capacity, { timestamps, includeDate });
  renderTrend($('performance-process-memory-chart'), [
    {
      className: 'chart-series-process-memory', legendClass: 'legend-process-memory',
      label: 'OlivOS 进程内存', formatValue: formatBytes, values: history.process_rss || [],
    },
  ], null, history.capacity, { timestamps, includeDate });
  renderTrend($('performance-traffic-chart'), [
    {
      className: 'chart-series-inbound', legendClass: 'legend-inbound', label: '入站',
      formatValue: trafficFormatValue, zeroPadding: true,
      values: trafficBucketValues(traffic, 'inbound', trafficHistory),
    },
    {
      className: 'chart-series-outbound', legendClass: 'legend-outbound', label: '出站',
      formatValue: trafficFormatValue, zeroPadding: true,
      values: trafficBucketValues(traffic, 'outbound', trafficHistory),
    },
  ], null, trafficCapacity, {
    timestamps: trafficHistory.map((item) => item.ts),
    includeDate,
  });
  renderTrend($('performance-failure-chart'), [
    {
      className: 'chart-series-failed', legendClass: 'legend-failed', label: '失败事件',
      formatValue: trafficFormatValue, zeroPadding: true,
      values: trafficBucketValues(traffic, 'failed', trafficHistory),
    },
  ], null, trafficCapacity, {
    timestamps: trafficHistory.map((item) => item.ts),
    includeDate,
  });
  setPerformanceCategory(state.performanceCategory);
}
function uptimeText(milliseconds) {
  const total = Math.max(0, Math.floor(milliseconds / 1000));
  const days = Math.floor(total / 86400);
  const hours = Math.floor(total / 3600) % 24;
  const minutes = Math.floor(total / 60) % 60;
  const seconds = total % 60;
  const pad = (value) => String(value).padStart(2, '0');
  return `运行时长：${days} 天 ${pad(hours)} 时 ${pad(minutes)} 分 ${pad(seconds)} 秒`;
}
// 服务端 uptime 只有整数秒，把它视为区间下界；本地用 performance.now() 推进，
// 新心跳只收紧区间，超出区间时以有界速率追赶，避免回退、跳秒和抖动。
function applyUptimeStatus(status, startedAt, receivedAt) {
  const seconds = Math.max(0, Math.floor(Number(status.uptime) || 0));
  const rtt = Math.max(0, receivedAt - startedAt);
  const lower = seconds * 1000 + rtt / 2;
  const upper = (seconds + 1) * 1000 + rtt / 2;
  const previous = state.uptimeSnapshot;
  const reset = state.uptimeClock === null || (
    previous && (
      seconds + 3 < previous.seconds
      || state.uptimeClock.valueMs > upper + 2000
    )
  );
  state.uptimeSnapshot = { seconds, receivedAt, rtt, lower, upper };
  if (reset) {
    state.uptimeClock = {
      valueMs: lower + 500,
      updatedAt: receivedAt,
      sampleAt: receivedAt,
      lower,
      upper,
    };
  } else {
    state.uptimeClock.sampleAt = receivedAt;
    state.uptimeClock.lower = lower;
    state.uptimeClock.upper = upper;
  }
}
function updateUptime(now = performance.now()) {
  if (state.page !== 'dashboard' || !state.uptimeClock) return;
  const clock = state.uptimeClock;
  const delta = Math.max(0, now - clock.updatedAt);
  clock.updatedAt = now;
  const elapsed = Math.max(0, now - clock.sampleAt);
  const lower = clock.lower + elapsed;
  const upper = clock.upper + elapsed;
  const rate = clock.valueMs < lower ? 1.08 : clock.valueMs > upper ? 0.92 : 1;
  clock.valueMs += delta * rate;
  const text = uptimeText(clock.valueMs);
  if ($('runtime').textContent !== text) $('runtime').textContent = text;
}
function startUptimeLoop() {
  if (state.uptimeFrame !== null) return;
  const step = () => {
    state.uptimeFrame = null;
    if (!state.token || state.page !== 'dashboard') return;
    updateUptime(performance.now());
    state.uptimeFrame = requestAnimationFrame(step);
  };
  state.uptimeFrame = requestAnimationFrame(step);
}
function stopUptimeLoop() {
  if (state.uptimeFrame === null) return;
  cancelAnimationFrame(state.uptimeFrame);
  state.uptimeFrame = null;
}
let statusRequestId = 0;
async function refreshStatus() {
  const requestId = ++statusRequestId;
  const startedAt = performance.now();
  const status = await api(state.page === 'performance'
    ? '/api/status?windows=1'
    : '/api/status');
  const receivedAt = performance.now();
  // 请求可能重叠：先发的后到会覆盖更新的状态，晚到的旧响应直接丢弃。
  if (requestId !== statusRequestId) return;
  if (Number.isInteger(status.plugin_page_cache)) {
    state.frameCacheLimit = Math.max(1, status.plugin_page_cache);
    trimFrames();
  }
  const cards = $('status-cards');
  cards.replaceChildren();
  cards.append(versionCard(status.version, status.version_slogan));
  for (const [label, value] of [
    ['账号', status.accounts],
    ['启用', status.enabled],
    ['在线', status.online],
  ]) {
    const card = element('div', null, { class: 'panel card' });
    card.append(element('span', label), element('strong', value));
    cards.append(card);
  }
  applyUptimeStatus(status, startedAt, receivedAt);
  updateUptime(receivedAt);
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
  if (state.page === 'performance') {
    renderPerformanceStatistics(status.statistics);
    if (state.performanceCategory === 'processes') {
      refreshPerformanceProcesses().catch(notifyError);
    }
  } else if (state.page === 'dashboard') {
    renderStatistics(status.statistics);
  }
  state.accountConnections = status.account_connections || {};
  if (state.page === 'accounts' && !state.accountDragging) renderAccounts();
}

const accountRowIds = new WeakMap();
const replacedAccounts = new WeakSet();
let lastAccountRowId = 0;

function accountRowId(account) {
  if (!accountRowIds.has(account)) accountRowIds.set(account, ++lastAccountRowId);
  return accountRowIds.get(account);
}

function replaceAccount(index, account) {
  const old = state.accounts[index];
  accountRowIds.set(account, accountRowId(old));
  if (replacedAccounts.has(old)) replacedAccounts.add(account);
  state.accounts[index] = account;
}

function updateAccountSelection() {
  const count = state.selectedAccounts.size;
  const all = $('accounts-select-all');
  all.disabled = state.accounts.length === 0;
  all.checked = count > 0 && count === state.accounts.length;
  all.indeterminate = count > 0 && !all.checked;
  const copy = $('export-accounts-copy');
  copy.textContent = count ? `复制所选 (${count})` : '复制所选';
  copy.disabled = $('export-accounts-menu-toggle').disabled = count === 0;
  if (!count && activeAccountMenu?.id === 'account-export-split') closeAccountMenu();
}

function selectedAccounts() {
  return state.accounts.filter((row) => state.selectedAccounts.has(accountRowId(row)));
}

function dirty() {
  state.dirty = true;
  state.accountEditGeneration += 1;
  $('accounts-dirty').textContent = '有未应用的修改';
}
async function loadAccounts() {
  const result = await api('/api/accounts');
  state.accounts = result.account;
  state.selectedAccounts.clear();
  state.savedAccounts = clone(result.account);
  state.revision = result.revision;
  state.dirty = false;
  state.accountEditGeneration += 1;
  $('accounts-dirty').textContent = '';
  renderAccounts();
}
function renderAccounts() {
  finishAccountDrag(false, false);
  const rows = $('account-rows');
  const active = document.activeElement;
  const focusClass = ['account-drag-handle', 'account-select'].find((name) => active?.classList.contains(name));
  const focusRow = focusClass ? active.closest('tr')?.dataset.accountRowId : null;
  rows.replaceChildren();
  if (!state.accounts.length) {
    const row = element('tr');
    row.append(element('td', '暂无账号，请新增账号。', { colspan: 6 }));
    rows.append(row);
  }
  state.accounts.forEach((account, index) => {
    const row = element('tr');
    const rowId = accountRowId(account);
    row.dataset.accountRowId = rowId;
    const controls = element('div', null, { class: 'account-row-controls' });
    const handle = element('button', '⠿', {
      type: 'button', class: 'account-drag-handle', 'aria-label': `调整账号 ${account.id} 的顺序`,
      title: '拖动调整顺序，或按方向键上移 / 下移',
    });
    handle.onpointerdown = (event) => startAccountDrag(event, index);
    handle.onpointermove = moveAccountDrag;
    handle.onpointerup = (event) => endAccountDrag(event, true);
    handle.onpointercancel = handle.onlostpointercapture = (event) => endAccountDrag(event, false);
    handle.onkeydown = (event) => {
      const direction = { ArrowUp: -1, ArrowDown: 1 }[event.key];
      if (!direction || state.accountDragging) return;
      event.preventDefault();
      const beforeTops = captureAccountRowTops();
      if (reorderAccounts(index, index + direction)) {
        renderAccounts();
        document.activeElement.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        animateAccountRows(beforeTops, String(rowId));
      }
    };
    const select = element('input', null, {
      type: 'checkbox', class: 'account-select', 'aria-label': `选择账号 ${account.id}`,
    });
    select.checked = state.selectedAccounts.has(rowId);
    select.onchange = () => {
      if (select.checked) state.selectedAccounts.add(rowId);
      else state.selectedAccounts.delete(rowId);
      updateAccountSelection();
    };
    controls.append(handle, select);
    const controlCell = element('td', null, { class: 'account-controls-cell' });
    controlCell.append(controls);
    row.append(controlCell);
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
    const connection = state.accountConnections[account.hash];
    const accountText = account.enable && connection === 'offline'
      ? `${account.id} (离线)`
      : String(account.id);
    row.append(
      element('td', accountText),
      element('td', account.platform_type),
      element('td', `${account.sdk_type} / ${account.model_type}`),
    );
    const actions = element('div', null, { class: 'actions' });
    actions.append(
      button('查看', () => viewAccount(index)),
      button('编辑', () => editAccount(index)),
      button('复制', () => copyAccounts([account])),
      button(
        '删除',
        () => {
          if (confirm(`删除账号 ${account.id}？保存并应用后生效。`)) {
            state.accounts.splice(index, 1);
            state.selectedAccounts.delete(rowId);
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
    if (String(rowId) === focusRow) row.querySelector(`.${focusClass}`).focus({ preventScroll: true });
  });
  updateAccountSelection();
}

function reorderAccounts(from, to) {
  if (from === to || to < 0 || to >= state.accounts.length) return false;
  const [account] = state.accounts.splice(from, 1);
  state.accounts.splice(to, 0, account);
  dirty();
  return true;
}

const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

function captureAccountRowTops() {
  const tops = new Map();
  for (const row of $('account-rows').rows) {
    if (row.dataset.accountRowId) tops.set(row.dataset.accountRowId, row.getBoundingClientRect().top);
  }
  return tops;
}

function animateAccountRows(beforeTops, elevatedRowId = null) {
  if (!beforeTops?.size || reducedMotionQuery.matches) return;
  for (const row of $('account-rows').rows) {
    const before = beforeTops.get(row.dataset.accountRowId);
    if (before === undefined || typeof row.animate !== 'function') continue;
    const deltaY = before - row.getBoundingClientRect().top;
    if (Math.abs(deltaY) < 0.5) continue;
    const elevated = elevatedRowId !== null && row.dataset.accountRowId === elevatedRowId;
    const animation = row.animate(
      [{ transform: `translate3d(0, ${deltaY}px, 0)` }, { transform: 'translate3d(0, 0, 0)' }],
      { duration: 160, easing: 'cubic-bezier(0.2, 0, 0, 1)' },
    );
    if (elevated) {
      row.classList.add('account-row-settling');
      animation.onfinish = animation.oncancel = () => row.classList.remove('account-row-settling');
    }
  }
}

function startAccountDrag(event, from) {
  if (!event.isPrimary || event.button !== 0 || state.accountDragging || state.accounts.length < 2) return;
  const handle = event.currentTarget;
  const rows = $('account-rows');
  const main = rows.closest('main');
  handle.setPointerCapture(event.pointerId);
  handle.focus({ preventScroll: true });
  event.preventDefault();
  state.accountDragging = {
    handle, tbody: rows, rows: rows.rows, from, to: from, pointerId: event.pointerId, startY: event.clientY,
    scroll: main.scrollHeight > main.clientHeight ? main : document.scrollingElement,
    active: false, y: event.clientY, frame: null, marker: null,
    baseTops: null, heights: null, height: 0, startAnchor: 0,
  };
}

function activateAccountDrag(drag) {
  for (const row of drag.rows) {
    for (const animation of row.getAnimations?.() || []) animation.cancel();
    row.style.transform = '';
  }
  const tbodyTop = drag.tbody.getBoundingClientRect().top;
  drag.baseTops = Array.from(drag.rows, (row) => row.getBoundingClientRect().top - tbodyTop);
  drag.heights = Array.from(drag.rows, (row) => row.getBoundingClientRect().height);
  drag.height = drag.heights[drag.from] || 0;
  drag.startAnchor = drag.startY - tbodyTop;
  drag.active = true;
  document.body.classList.add('account-dragging-active');
  drag.tbody.classList.add('account-rows-sorting');
  drag.rows[drag.from].classList.add('account-row-dragging');
}

function updateAccountDragOffset(drag) {
  if (!drag.active || !drag.baseTops) return;
  const tbodyTop = drag.tbody.getBoundingClientRect().top;
  const rawDy = (drag.y - tbodyTop) - drag.startAnchor;
  const minDy = -drag.baseTops[drag.from];
  const lastIndex = drag.baseTops.length - 1;
  const maxDy = (drag.baseTops[lastIndex] + drag.heights[lastIndex]) - (drag.baseTops[drag.from] + drag.height);
  const dy = Math.max(minDy, Math.min(maxDy, rawDy));
  drag.rows[drag.from].style.transform = `translate3d(0, ${dy}px, 0)`;
}

function applyAccountDragShifts(drag) {
  for (let index = 0; index < drag.rows.length; index += 1) {
    if (index === drag.from) continue;
    let shift = 0;
    if (drag.to > drag.from && index > drag.from && index <= drag.to) shift = -drag.height;
    else if (drag.to < drag.from && index >= drag.to && index < drag.from) shift = drag.height;
    drag.rows[index].style.transform = shift ? `translate3d(0, ${shift}px, 0)` : '';
  }
}

function markAccountDrop(drag) {
  const tbodyTop = drag.tbody.getBoundingClientRect().top;
  let first = 0;
  let last = drag.rows.length;
  while (first < last) {
    const index = (first + last) >> 1;
    const middle = drag.baseTops
      ? tbodyTop + drag.baseTops[index] + drag.heights[index] / 2
      : (() => {
          const bounds = drag.rows[index].getBoundingClientRect();
          return (bounds.top + bounds.bottom) / 2;
        })();
    if (drag.y < middle || (drag.y === middle && index < drag.from)) last = index;
    else first = index + 1;
  }
  const to = first > drag.from ? first - 1 : first;
  if (to === drag.to) return;
  drag.marker?.classList.remove('account-drop-before', 'account-drop-after');
  drag.to = to;
  drag.marker = to === drag.from ? null : drag.rows[to];
  drag.marker?.classList.add(to < drag.from ? 'account-drop-before' : 'account-drop-after');
  applyAccountDragShifts(drag);
}

function scrollAccountDrag(drag) {
  drag.frame = null;
  const root = drag.scroll === document.scrollingElement;
  const bounds = root ? null : drag.scroll.getBoundingClientRect();
  const top = Math.max(0, bounds?.top ?? 0);
  const bottom = Math.min(window.innerHeight, bounds?.bottom ?? window.innerHeight);
  const edge = 52;
  const distance = drag.y < top + edge ? drag.y - top - edge : Math.max(0, drag.y - bottom + edge);
  const before = drag.scroll.scrollTop;
  drag.scroll.scrollTop += Math.sign(distance) * Math.min(24, Math.ceil(Math.abs(distance) / 3));
  if (drag.scroll.scrollTop !== before) {
    updateAccountDragOffset(drag);
    markAccountDrop(drag);
    drag.frame = requestAnimationFrame(() => scrollAccountDrag(drag));
  }
}

function moveAccountDrag(event) {
  const drag = state.accountDragging;
  if (drag?.pointerId !== event.pointerId) return;
  drag.y = event.clientY;
  if (!drag.active) {
    if (Math.abs(drag.y - drag.startY) < 4) return;
    activateAccountDrag(drag);
  }
  updateAccountDragOffset(drag);
  markAccountDrop(drag);
  if (drag.frame === null) drag.frame = requestAnimationFrame(() => scrollAccountDrag(drag));
}

function endAccountDrag(event, commit) {
  const drag = state.accountDragging;
  if (drag?.pointerId !== event.pointerId) return;
  if (commit && drag.active) {
    drag.y = event.clientY;
    updateAccountDragOffset(drag);
    markAccountDrop(drag);
  }
  finishAccountDrag(commit);
}

function finishAccountDrag(commit, repaint = true) {
  const drag = state.accountDragging;
  if (!drag) return;
  const beforeTops = repaint && drag.active ? captureAccountRowTops() : null;
  const movedRowId = drag.active ? drag.rows[drag.from]?.dataset.accountRowId ?? null : null;
  state.accountDragging = null;
  if (drag.frame !== null) cancelAnimationFrame(drag.frame);
  if (drag.handle.hasPointerCapture(drag.pointerId)) drag.handle.releasePointerCapture(drag.pointerId);
  document.body.classList.remove('account-dragging-active');
  drag.tbody.classList.remove('account-rows-sorting');
  for (const row of drag.rows) row.style.transform = '';
  drag.rows[drag.from]?.classList.remove('account-row-dragging');
  drag.marker?.classList.remove('account-drop-before', 'account-drop-after');
  if (commit && drag.active) reorderAccounts(drag.from, drag.to);
  if (repaint) {
    renderAccounts();
    animateAccountRows(beforeTops, movedRowId);
  }
}

function portableAccount(account) {
  const row = clone(account);
  delete row.hash;
  if (row.server && typeof row.server.port === 'string') {
    const port = row.server.port.trim();
    if (/^\d+$/.test(port)) {
      const numeric = Number(port);
      if (Number.isSafeInteger(numeric)) row.server.port = numeric;
    }
  }
  const servers = row.extends?.['qsign-server'];
  if (Array.isArray(servers)) {
    for (const server of servers) {
      if (server && typeof server === 'object') delete server._source_index;
    }
  }
  return row;
}

function accountExportText(accounts) {
  return JSON.stringify({ account: accounts.map(portableAccount) }, null, 2);
}

function legacyCopyAccounts(text) {
  const previousFocus = document.activeElement;
  const field = element('textarea', null, { class: 'account-copy-buffer', readonly: '' });
  field.value = text;
  document.body.append(field);
  try {
    field.focus({ preventScroll: true });
    field.select();
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    field.remove();
    previousFocus?.focus({ preventScroll: true });
  }
}

async function copyAccounts(accounts) {
  closeAccountMenu();
  if (!accounts.length) return;
  const text = accountExportText(accounts);
  const auth = state.authGeneration;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    if (auth !== state.authGeneration || state.page !== 'accounts') return;
    if (!legacyCopyAccounts(text)) {
      const dialog = $('account-copy-fallback-dialog');
      const field = $('account-copy-fallback-text');
      field.value = text;
      if (!dialog.open) dialog.showModal();
      field.focus();
      field.select();
      return;
    }
  }
  if (auth === state.authGeneration) notify(`已复制 ${accounts.length} 个账号。`);
}

const exportBlobUrls = new Map();

function revokeExportBlobUrls() {
  for (const [url, timer] of exportBlobUrls) {
    clearTimeout(timer);
    URL.revokeObjectURL(url);
  }
  exportBlobUrls.clear();
}

function downloadAccounts() {
  const accounts = selectedAccounts();
  if (!accounts.length) return;
  const url = URL.createObjectURL(new Blob([accountExportText(accounts)], { type: 'application/json' }));
  const timer = setTimeout(() => {
    exportBlobUrls.delete(url);
    URL.revokeObjectURL(url);
  }, 60000);
  exportBlobUrls.set(url, timer);
  const link = element('a', null, { href: url, download: 'account.json' });
  document.body.append(link);
  link.click();
  link.remove();
}

const ACCOUNT_IMPORT_MAX_BYTES = 1024 * 1024;
let accountImport = null;

function normalizeAccountId(value) {
  const text = String(value ?? '');
  const trimmed = text.trim();
  if (/^[+-]?\d+$/.test(trimmed)) return BigInt(trimmed).toString();
  return text;
}

function accountIdentity(row) {
  return JSON.stringify([normalizeAccountId(row.id), row.sdk_type, row.platform_type]);
}

function accountImportMatches() {
  return new Map(state.accounts.map((row, index) => [accountIdentity(row), { row, index }]));
}

function accountImportDiff(old, account) {
  const local = portableAccount(old);
  const ordered = (value) => JSON.stringify(value, (_, field) => {
    if (!field || typeof field !== 'object' || Array.isArray(field)) return field;
    return Object.fromEntries(Object.keys(field).sort().map((key) => [key, field[key]]));
  });
  const changed = [
    ['model_type', '型号'], ['password', '密码'], ['server', '连接配置'],
    ['extends', '扩展配置'], ['enable', '启用状态'], ['debug', '调试模式'],
  ].filter(([key]) => ordered(local[key]) !== ordered(account[key])).map(([, label]) => label);
  return changed.length ? `将替换：${changed.join('、')}` : '配置相同';
}

function accountImportMessage(text, focusSource = false) {
  const message = $('account-import-error');
  message.textContent = text;
  message.hidden = !text;
  if (focusSource) {
    $('account-import-source').open = true;
    $('account-import-text').focus();
  }
}

function updateAccountImportConfirm() {
  let added = 0;
  let overwritten = 0;
  for (const entry of accountImport?.items || []) {
    if (!entry.checked) continue;
    if (entry.old) overwritten++;
    else added++;
  }
  const confirm = $('account-import-confirm');
  confirm.textContent = `确认导入（新增 ${added}，覆盖 ${overwritten}）`;
  confirm.disabled = added + overwritten === 0;
}

function clearAccountImportPreview() {
  if (accountImport) accountImport.items = [];
  $('account-import-summary').hidden = true;
  $('account-import-list').replaceChildren();
  updateAccountImportConfirm();
}

function openAccountImport() {
  const dialog = $('account-import-dialog');
  accountImport = { request: 0, items: [], duplicates: 0 };
  clearAccountImportPreview();
  $('account-import-text').value = '';
  $('account-import-source').open = false;
  accountImportMessage('正在读取账号…');
  if (!dialog.open) dialog.showModal();
  return accountImport;
}

function accountImportCurrent(session, request) {
  return accountImport === session && session.request === request && $('account-import-dialog').open;
}

function renderAccountImportPreview(session, matches) {
  const list = $('account-import-list');
  list.replaceChildren();
  let added = 0;
  let duplicates = 0;
  let invalid = 0;
  for (const entry of session.items) {
    const { account, identity, error, source } = entry;
    entry.old = matches.get(identity)?.row;
    if (!account) invalid++;
    else if (entry.old) duplicates++;
    else added++;
    const item = element('li', null, { 'data-state': !account ? 'invalid' : entry.old ? 'duplicate' : 'new' });
    const title = element('label', null, { class: 'account-import-choice' });
    const select = element('input', null, { type: 'checkbox' });
    select.disabled = !account;
    select.checked = entry.checked;
    select.onchange = () => {
      entry.checked = select.checked;
      updateAccountImportConfirm();
    };
    const display = (key) => {
      const value = source?.[key];
      if (typeof value === 'number') return String(value);
      if (typeof value === 'string' && value.trim()) return value.trim();
      return '—';
    };
    title.append(
      select,
      element('span', !account ? '无效' : entry.old ? '重复 · 覆盖' : '新增', { class: 'account-import-badge' }),
      element('strong', `账号 ${display('id')}`),
    );
    item.append(title, element('p', `${display('platform_type')} · ${display('sdk_type')} / ${display('model_type')}`));
    if (error || entry.old) item.append(element('p', error || accountImportDiff(entry.old, account)));
    list.append(item);
  }
  const merged = session.duplicates ? ` · 已合并批内重复 ${session.duplicates} 条` : '';
  $('account-import-counts').textContent =
    `总数 ${session.items.length + session.duplicates} · 新增 ${added} · 重复 ${duplicates} · 无效 ${invalid}${merged}`;
  $('account-import-summary').hidden = false;
  $('account-import-conflict-actions').hidden = !duplicates;
  updateAccountImportConfirm();
}

async function previewAccountImport(session, text) {
  if (!session) return;
  const request = ++session.request;
  clearAccountImportPreview();
  const jsonText = text.trim();
  if (new Blob([jsonText]).size > ACCOUNT_IMPORT_MAX_BYTES) {
    accountImportMessage('导入内容超过 1 MB，请拆分后再导入。', true);
    return;
  }
  let payload;
  try {
    payload = JSON.parse(jsonText);
  } catch {
    accountImportMessage('内容不是有效的 JSON。请粘贴账号 JSON 后点击「解析 JSON」。', true);
    return;
  }
  accountImportMessage('正在校验账号…');
  try {
    // 原样提交，避免浏览器重新序列化时把长数字账号 ID 四舍五入。
    const preview = await api('/api/accounts/import/preview', { method: 'POST', jsonText });
    if (!accountImportCurrent(session, request)) return;
    const source = payload && Object.hasOwn(payload, 'payload') ? payload.payload : payload;
    const rows = Array.isArray(source) ? source : source.account || [source];
    session.duplicates = preview.batch_duplicates;
    session.items = preview.items.map((item) => ({
      account: item.account, identity: item.valid ? accountIdentity(item.account) : null,
      error: item.error, source: item.valid ? item.account : rows[item.source_index], checked: item.valid,
    }));
    renderAccountImportPreview(session, accountImportMatches());
    const valid = session.items.some((item) => item.checked);
    accountImportMessage(valid ? '' : '没有可导入的账号。可修正 JSON 后重新解析。', !valid);
  } catch (error) {
    if (accountImportCurrent(session, request) && !error.authHandled && !error.authObsolete) {
      accountImportMessage(`${error.message}。可粘贴账号 JSON 后点击「解析 JSON」。`, true);
    }
  }
}

async function importAccountsFromClipboard() {
  closeAccountMenu(true);
  const session = openAccountImport();
  let text;
  try {
    text = await navigator.clipboard.readText();
  } catch {
    if (accountImportCurrent(session, 0)) {
      accountImportMessage('无法读取剪贴板，请手动粘贴账号 JSON 后点击「解析 JSON」。', true);
    }
    return;
  }
  if (!accountImportCurrent(session, 0)) return;
  $('account-import-text').value = text;
  await previewAccountImport(session, text);
}

async function importAccountsFromFile(event) {
  const input = event.currentTarget;
  const file = input.files[0];
  input.value = '';
  if (!file) return;
  const session = openAccountImport();
  if (file.size > ACCOUNT_IMPORT_MAX_BYTES) {
    accountImportMessage('JSON 文件超过 1 MB，请拆分文件后再导入。', true);
    return;
  }
  let text;
  try {
    text = await file.text();
  } catch {
    if (accountImportCurrent(session, 0)) accountImportMessage('无法读取 JSON 文件。', true);
    return;
  }
  if (!accountImportCurrent(session, 0)) return;
  $('account-import-text').value = text;
  await previewAccountImport(session, text);
}

function setAccountImportConflicts(checked) {
  if (!accountImport) return;
  const inputs = $('account-import-list').querySelectorAll('input');
  accountImport.items.forEach((entry, index) => {
    if (entry.old) inputs[index].checked = entry.checked = checked;
  });
  updateAccountImportConfirm();
}

function confirmAccountImport() {
  const session = accountImport;
  if (!session) return;
  const matches = accountImportMatches();
  if (session.items.some((entry) => entry.old !== matches.get(entry.identity)?.row)) {
    renderAccountImportPreview(session, matches);
    accountImportMessage('账号列表已更新，请重新核对导入预览。');
    return;
  }
  let imported = 0;
  for (const entry of session.items) {
    if (!entry.checked) continue;
    const existing = matches.get(entry.identity);
    const account = entry.account;
    if (existing) {
      if (existing.row.hash) {
        account.hash = existing.row.hash;
        replacedAccounts.add(account);
      }
      replaceAccount(existing.index, account);
    } else {
      state.accounts.push(account);
    }
    imported++;
  }
  if (!imported) return;
  dirty();
  renderAccounts();
  $('account-import-dialog').close();
  notify(`已将 ${imported} 个账号导入草稿。`);
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
const selectMenuMaxHeight = 320;
const selectMenuGap = 4;
const selectMenuViewportGap = 8;
const selectMenuState = {
  select: null,
  menu: null,
  list: null,
  search: null,
  items: [],
  activeIndex: -1,
  typeahead: '',
  lastTypeaheadAt: 0,
  sequence: 0,
};

function selectMenuLabel(select) {
  const aria = select.getAttribute('aria-label');
  if (aria) return aria;
  const label = select.labels && select.labels[0];
  if (!label) return '选项';
  const text = Array.from(label.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => node.textContent)
    .join(' ')
    .trim();
  return text || '选项';
}

function selectMenuHost(select) {
  return select.closest('dialog[open]') || document.body;
}

function enhanceSelect(select) {
  if (!select || select.multiple || select.dataset.customSelectReady === '1') return;
  if (select.closest('.select-shell')) return;
  select.dataset.customSelectReady = '1';
  const shell = element('span', null, { class: 'select-shell' });
  const chevron = element('span', null, { class: 'select-chevron', 'aria-hidden': 'true' });
  select.parentNode.insertBefore(shell, select);
  shell.append(select, chevron);
  select.setAttribute('aria-haspopup', 'listbox');
  select.setAttribute('aria-expanded', 'false');
  select.addEventListener('pointerdown', (event) => {
    if (select.disabled) return;
    event.preventDefault();
    select.focus({ preventScroll: true });
    if (selectMenuState.select === select) closeSelectMenu();
    else openSelectMenu(select);
  });
  select.addEventListener('keydown', handleSelectKeydown);
  const label = select.labels && select.labels[0];
  if (label) {
    label.addEventListener('click', (event) => {
      if (event.target === select || select.disabled) return;
      event.preventDefault();
      select.focus({ preventScroll: true });
      if (selectMenuState.select === select) closeSelectMenu();
      else openSelectMenu(select);
    });
  }
}

function enhanceSelects(root = document) {
  root.querySelectorAll('select:not([multiple])').forEach(enhanceSelect);
}

function appendSelectMenuItem(menu, items, option, index, groupDisabled) {
  const disabled = groupDisabled || option.disabled;
  const item = element('div', null, {
    id: `${menu.id}-option-${index}`,
    class: 'select-menu-option',
    role: 'option',
    'aria-selected': String(option.selected),
    'aria-disabled': String(disabled),
  });
  item.append(element('span', option.textContent.trim() || option.value || '（空白选项）', {
    class: 'select-menu-option-label',
  }));
  if (option.dataset.detail) {
    item.append(element('span', option.dataset.detail, { class: 'select-menu-option-detail' }));
  }
  menu.append(item);
  const entry = { option, element: item, disabled };
  const itemIndex = items.length;
  items.push(entry);
  if (disabled) return;
  item.addEventListener('pointermove', () => {
    if (selectMenuState.activeIndex !== itemIndex) setSelectActiveIndex(itemIndex);
  });
  item.addEventListener('click', () => chooseSelectMenuItem(entry));
}

function openSelectMenu(select) {
  if (!select || select.disabled) return;
  closeSelectMenu();
  closeAccountMenu();
  select.focus({ preventScroll: true });
  const id = `customSelectMenu${++selectMenuState.sequence}`;
  const menu = element('div', null, { class: 'select-menu' });
  const searchable = select.hasAttribute('data-searchable');
  const list = searchable ? element('div', null, { class: 'select-menu-list' }) : menu;
  list.id = id;
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', selectMenuLabel(select));
  let search = null;
  if (searchable) {
    menu.classList.add('select-menu-searchable');
    search = element('input', null, {
      type: 'search', role: 'combobox', autocomplete: 'off',
      placeholder: '搜索城市或时区编号', 'aria-label': '搜索时区',
      'aria-autocomplete': 'list', 'aria-expanded': 'true', 'aria-controls': id,
    });
    search.addEventListener('input', filterSelectMenu);
    search.addEventListener('keydown', handleSelectSearchKeydown);
    menu.append(search, list, element('p', '未找到匹配的时区。', { class: 'select-menu-empty', hidden: '' }));
  }
  const items = [];
  let optionIndex = 0;
  Array.from(select.children).forEach((child) => {
    if (child.tagName === 'OPTGROUP') {
      list.append(element('div', child.label || '', {
        class: 'select-menu-group',
        role: 'presentation',
      }));
      Array.from(child.children).forEach((option) => {
        if (option.tagName !== 'OPTION') return;
        appendSelectMenuItem(list, items, option, optionIndex, child.disabled);
        optionIndex += 1;
      });
      return;
    }
    if (child.tagName === 'OPTION') {
      appendSelectMenuItem(list, items, child, optionIndex, false);
      optionIndex += 1;
    }
  });
  menu.addEventListener('pointerdown', (event) => {
    if (!searchable || event.target.closest('[role="option"]')) event.preventDefault();
  });
  menu.style.visibility = 'hidden';
  selectMenuHost(select).append(menu);
  selectMenuState.select = select;
  selectMenuState.menu = menu;
  selectMenuState.list = list;
  selectMenuState.search = search;
  selectMenuState.items = items;
  selectMenuState.activeIndex = -1;
  select.classList.add('select-menu-open');
  select.setAttribute('aria-expanded', 'true');
  select.setAttribute('aria-controls', id);
  positionSelectMenu();
  const selectedIndex = items.findIndex((item) => item.option.selected && !item.disabled);
  setSelectActiveIndex(selectedIndex >= 0 ? selectedIndex : firstEnabledSelectItem());
  menu.style.visibility = '';
  if (search) search.focus({ preventScroll: true });
  document.addEventListener('pointerdown', handleSelectOutsidePointerDown, true);
  document.addEventListener('focusin', handleSelectFocusChange, true);
  window.addEventListener('resize', positionSelectMenu);
  window.addEventListener('scroll', handleSelectViewportScroll, true);
  window.addEventListener('blur', handleSelectWindowBlur);
}

function setSelectActiveIndex(index) {
  if (!selectMenuState.menu) return;
  const item = selectMenuState.items[index];
  if (index !== -1 && (!item || item.disabled || item.element.hidden)) return;
  selectMenuState.activeIndex = index;
  selectMenuState.items.forEach((entry, entryIndex) => {
    entry.element.dataset.active = String(entryIndex === index);
  });
  const focusTarget = selectMenuState.search || selectMenuState.select;
  if (!item) {
    focusTarget.removeAttribute('aria-activedescendant');
    return;
  }
  focusTarget.setAttribute('aria-activedescendant', item.element.id);
  const menu = selectMenuState.list;
  const itemTop = item.element.offsetTop;
  const itemBottom = itemTop + item.element.offsetHeight;
  if (itemTop < menu.scrollTop) menu.scrollTop = itemTop;
  else if (itemBottom > menu.scrollTop + menu.clientHeight) {
    menu.scrollTop = itemBottom - menu.clientHeight;
  }
}

function moveSelectActive(delta) {
  const items = selectMenuState.items;
  if (!items.length) return;
  let index = selectMenuState.activeIndex;
  for (let count = 0; count < items.length; count += 1) {
    index = index < 0 && delta < 0 ? items.length - 1 : (index + delta + items.length) % items.length;
    if (!items[index].disabled && !items[index].element.hidden) {
      setSelectActiveIndex(index);
      return;
    }
  }
}

function firstEnabledSelectItem() {
  return selectMenuState.items.findIndex((item) => !item.disabled && !item.element.hidden);
}

function lastEnabledSelectItem() {
  for (let index = selectMenuState.items.length - 1; index >= 0; index -= 1) {
    if (!selectMenuState.items[index].disabled) return index;
  }
  return -1;
}

function chooseSelectMenuItem(item) {
  const select = selectMenuState.select;
  if (!select || !item || item.disabled) return;
  const changed = select.selectedIndex !== item.option.index;
  select.selectedIndex = item.option.index;
  closeSelectMenu(true);
  if (changed) select.dispatchEvent(new Event('change', { bubbles: true }));
}

function filterSelectMenu() {
  const { search, items, list, menu } = selectMenuState;
  const words = search.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
  for (const item of items) {
    const { option } = item;
    const text = `${option.textContent} ${option.value}`.toLowerCase();
    item.element.hidden = !words.every((word) => text.includes(word));
  }
  list.querySelectorAll('.select-menu-group').forEach((group) => { group.hidden = words.length > 0; });
  const first = firstEnabledSelectItem();
  menu.querySelector('.select-menu-empty').hidden = first >= 0;
  list.scrollTop = 0;
  positionSelectMenu();
  setSelectActiveIndex(first);
}

function handleSelectSearchKeydown(event) {
  if (event.isComposing) return;
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    moveSelectActive(event.key === 'ArrowDown' ? 1 : -1);
  } else if (event.key === 'Enter') {
    event.preventDefault();
    chooseSelectMenuItem(selectMenuState.items[selectMenuState.activeIndex]);
  } else if (event.key === 'Escape') {
    event.preventDefault();
    closeSelectMenu(true);
  } else if (event.key === 'Tab') {
    closeSelectMenu(true);
  }
}

function handleSelectKeydown(event) {
  const select = event.currentTarget;
  if (select.disabled || event.isComposing) return;
  const open = selectMenuState.select === select;
  if (!open) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      openSelectMenu(select);
      moveSelectActive(event.key === 'ArrowDown' ? 1 : -1);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openSelectMenu(select);
    }
    return;
  }
  if (event.key === 'Escape') {
    event.preventDefault();
    closeSelectMenu(true);
  } else if (event.key === 'Tab') {
    closeSelectMenu();
  } else if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    const item = selectMenuState.items[selectMenuState.activeIndex];
    if (item && !item.disabled) chooseSelectMenuItem(item);
  } else if (event.key === 'ArrowDown') {
    event.preventDefault();
    moveSelectActive(1);
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    moveSelectActive(-1);
  } else if (event.key === 'Home') {
    event.preventDefault();
    setSelectActiveIndex(firstEnabledSelectItem());
  } else if (event.key === 'End') {
    event.preventDefault();
    setSelectActiveIndex(lastEnabledSelectItem());
  } else if (event.key === 'PageDown') {
    event.preventDefault();
    moveSelectActive(5);
  } else if (event.key === 'PageUp') {
    event.preventDefault();
    moveSelectActive(-5);
  } else if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    typeaheadSelectItem(event.key);
  }
}

function typeaheadSelectItem(character) {
  const now = Date.now();
  if (now - selectMenuState.lastTypeaheadAt > 700) selectMenuState.typeahead = '';
  selectMenuState.lastTypeaheadAt = now;
  selectMenuState.typeahead += character.toLocaleLowerCase();
  const query = selectMenuState.typeahead;
  const items = selectMenuState.items;
  const start = selectMenuState.activeIndex >= 0
    ? (selectMenuState.activeIndex + 1) % items.length
    : 0;
  for (let offset = 0; offset < items.length; offset += 1) {
    const index = (start + offset) % items.length;
    const item = items[index];
    if (!item.disabled && item.option.textContent.trim().toLocaleLowerCase().startsWith(query)) {
      setSelectActiveIndex(index);
      return;
    }
  }
}

function positionSelectMenu() {
  const select = selectMenuState.select;
  const menu = selectMenuState.menu;
  if (!select || !menu || !document.contains(select)) {
    closeSelectMenu();
    return;
  }
  const rect = select.getBoundingClientRect();
  if (rect.bottom < 0 || rect.top > window.innerHeight || rect.right < 0 || rect.left > window.innerWidth) {
    closeSelectMenu();
    return;
  }
  const maxWidth = Math.max(0, window.innerWidth - selectMenuViewportGap * 2);
  const width = Math.min(Math.max(rect.width, selectMenuState.search ? 260 : 168), maxWidth);
  const left = Math.min(
    Math.max(rect.left, selectMenuViewportGap),
    Math.max(selectMenuViewportGap, window.innerWidth - width - selectMenuViewportGap),
  );
  menu.style.width = `${Math.round(width)}px`;
  menu.style.left = `${Math.round(left)}px`;
  menu.style.maxHeight = `${Math.min(selectMenuMaxHeight, Math.max(80, window.innerHeight - 16))}px`;
  menu.style.top = '0px';
  const list = selectMenuState.list;
  const naturalHeight = menu.scrollHeight + (list === menu ? 0 : list.scrollHeight - list.clientHeight);
  const availableBelow = window.innerHeight - rect.bottom - selectMenuGap - selectMenuViewportGap;
  const availableAbove = rect.top - selectMenuGap - selectMenuViewportGap;
  const height = Math.min(naturalHeight, selectMenuMaxHeight);
  const opensAbove = availableBelow < height && availableAbove > availableBelow;
  const finalHeight = Math.max(0, Math.min(height, opensAbove ? availableAbove : availableBelow));
  menu.style.maxHeight = `${Math.min(selectMenuMaxHeight, finalHeight)}px`;
  const top = opensAbove ? rect.top - selectMenuGap - finalHeight : rect.bottom + selectMenuGap;
  menu.style.top = `${Math.round(Math.max(selectMenuViewportGap, top))}px`;
  menu.classList.toggle('opens-above', opensAbove);
  // 边框盒会带来 2px 差值，只有内容确实溢出时才启用滚动。
  menu.classList.toggle('is-scrollable', menu.scrollHeight > menu.clientHeight + 2);
}

function handleSelectOutsidePointerDown(event) {
  const select = selectMenuState.select;
  const menu = selectMenuState.menu;
  if (!select || !menu) return;
  if (event.target === select || select.contains(event.target) || menu.contains(event.target)) return;
  closeSelectMenu();
}

function handleSelectViewportScroll(event) {
  if (event.target === selectMenuState.menu || event.target === selectMenuState.list) return;
  positionSelectMenu();
}

function handleSelectFocusChange(event) {
  const select = selectMenuState.select;
  const menu = selectMenuState.menu;
  if (!select || !menu) return;
  if (event.target !== select && !menu.contains(event.target)) closeSelectMenu();
}

function handleSelectWindowBlur() {
  closeSelectMenu();
}

function closeSelectMenu(focusSelect = false) {
  const select = selectMenuState.select;
  if (select) {
    select.classList.remove('select-menu-open');
    select.setAttribute('aria-expanded', 'false');
    select.removeAttribute('aria-controls');
    select.removeAttribute('aria-activedescendant');
  }
  if (selectMenuState.menu?.parentNode) selectMenuState.menu.remove();
  selectMenuState.select = null;
  selectMenuState.menu = null;
  selectMenuState.list = null;
  selectMenuState.search = null;
  selectMenuState.items = [];
  selectMenuState.activeIndex = -1;
  selectMenuState.typeahead = '';
  selectMenuState.lastTypeaheadAt = 0;
  document.removeEventListener('pointerdown', handleSelectOutsidePointerDown, true);
  document.removeEventListener('focusin', handleSelectFocusChange, true);
  window.removeEventListener('resize', positionSelectMenu);
  window.removeEventListener('scroll', handleSelectViewportScroll, true);
  window.removeEventListener('blur', handleSelectWindowBlur);
  if (focusSelect && select && !select.disabled) select.focus({ preventScroll: true });
}

function initializeSelectMenus() {
  enhanceSelects(document);
  document.querySelectorAll('dialog').forEach((dialog) => {
    dialog.addEventListener('close', () => closeSelectMenu());
  });
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
let activeAccountMenu = null;

function closeAccountMenu(restoreFocus = false) {
  if (!activeAccountMenu) return;
  const menu = activeAccountMenu.querySelector('.account-split-menu');
  const toggle = activeAccountMenu.querySelector('.account-split-toggle');
  activeAccountMenu = null;
  menu.hidden = true;
  toggle.setAttribute('aria-expanded', 'false');
  if (restoreFocus) toggle.focus();
}

function openAccountMenu(split) {
  const toggle = split.querySelector('.account-split-toggle');
  if (toggle.disabled) return;
  closeSelectMenu();
  closeAccountMenu();
  const menu = split.querySelector('.account-split-menu');
  activeAccountMenu = split;
  menu.hidden = false;
  const left = split.getBoundingClientRect().left;
  const right = document.documentElement.clientWidth - 8;
  menu.style.left = `${Math.max(8 - left, Math.min(0, right - left - menu.offsetWidth))}px`;
  toggle.setAttribute('aria-expanded', 'true');
  menu.firstElementChild.focus();
}

function editAccount(index) {
  closeAccountMenu();
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
  const secret = /password|token|secret|key$|cookie|authorization/i.test(field.name);
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
  if (secret || input.value === '********') {
    input.type = 'password';
    addSecretToggle(input);
  }
  parent.append(label);
}

function addSecretToggle(input) {
  const wrapper = element('span', null, { class: 'secret-input' });
  input.replaceWith(wrapper);
  const eye = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [name, value] of Object.entries({
    viewBox: '0 0 24 24',
    width: '20',
    height: '20',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': '2',
    'aria-hidden': 'true',
  })) {
    eye.setAttribute(name, value);
  }
  const outline = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  outline.setAttribute('d', 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z');
  const pupil = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  pupil.setAttribute('cx', '12');
  pupil.setAttribute('cy', '12');
  pupil.setAttribute('r', '3');
  const slash = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  slash.setAttribute('d', 'm3 3 18 18');
  eye.append(outline, pupil);
  const toggle = button('', () => {
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    eye.replaceChildren(outline, visible ? slash : pupil);
    const action = visible ? '隐藏内容' : '显示内容';
    toggle.setAttribute('aria-label', action);
    toggle.title = action;
  });
  toggle.className = 'secret-toggle';
  toggle.append(eye);
  toggle.setAttribute('aria-label', '显示内容');
  toggle.title = '显示内容';
  wrapper.append(input, toggle);
}

addSecretToggle($('token'));
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
  $('account-qr-bind-bar').hidden = !(
    state.draft.sdk_type === 'qqGuildv2_link' && state.draft.platform_type === 'qqGuild'
  );
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
      if (key === 'key') addSecretToggle(input);
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
async function createScannedAccount(credentials) {
  const items = Array.isArray(credentials) ? credentials : [credentials];
  let changed = false;
  for (const { app_id, app_secret } of items) {
    const account = clone(state.schema.qqguild_qr_account);
    const existing = state.accounts.find((row) => row.sdk_type === account.sdk_type &&
      row.platform_type === account.platform_type && String(row.id) === String(app_id));
    if (existing) {
      if (!confirm(`账号 ${app_id} 已存在。仅更新 AppSecret 并保存？`)) continue;
      existing.server.access_token = app_secret;
    } else {
      account.id = app_id;
      account.server.access_token = app_secret;
      state.accounts.push(account);
    }
    changed = true;
  }
  if (!changed) return;
  dirty();
  renderAccounts();
  await saveAccounts();
}

function fillScannedAccount(credentials) {
  const items = Array.isArray(credentials) ? credentials : [credentials];
  const { app_id, app_secret } = items[0];
  const extraIds = items.slice(1).map((item) => item.app_id);
  if (!$('account-dialog').open || $('account-qr-bind-bar').hidden) return;
  const form = $('account-form');
  form.querySelector('[data-field="id"]').value = state.draft.id = app_id;
  form.querySelector('[data-field="server.access_token"]').value = state.draft.server.access_token = app_secret;
  if (extraIds.length) {
    notify(`扫码返回了多个机器人，当前编辑器仅填入 ${app_id}，其余账号（${extraIds.join('、')}）请使用「QQ 官方扫码创建」。`);
  }
  if (state.draft.server.type === 'post') {
    $('account-error').textContent = '已填入凭据，请核对 Webhook 回调地址后点击「确定」。';
    return refreshWebhook();
  }
  if (state.draft.server.type !== 'websocket') {
    $('account-error').textContent = '已填入凭据，请核对连接类型后点击「确定」。';
    return;
  }
  const port = form.querySelector('[data-field="server.port"]');
  const intents = state.draft.model_type.endsWith('intents');
  const number = port.value.trim();
  if ((intents && !number) || (number && (!/^\d+$/.test(number) || (!intents && Number(number) > 65535)))) {
    $('account-error').textContent = intents
      ? '已填入凭据，请补全有效的 intents 后点击「确定」。'
      : '已填入凭据，请核对端口后点击「确定」。';
    if (port.closest('details')) port.closest('details').open = true;
    port.focus();
    return;
  }
  form.requestSubmit();
}

async function saveAccounts() {
  if (!state.dirty || state.accountDragging) return;
  const submit = $('save-accounts');
  submit.disabled = true;
  const submittedGeneration = state.accountEditGeneration;
  try {
    const accounts = clone(state.accounts);
    const replaceHashes = state.accounts.filter((row) => row.hash && replacedAccounts.has(row)).map((row) => row.hash);
    for (const row of accounts) {
      if (row.password === '********') delete row.password;
      if (row.server.access_token === '********') delete row.server.access_token;
    }
    const body = { account: accounts, revision: state.revision };
    if (replaceHashes.length) body.replace_hashes = replaceHashes;
    const result = await api('/api/accounts', {
      method: 'POST',
      body,
    });
    state.savedAccounts = clone(result.account);
    state.revision = result.revision;
    if (state.accountEditGeneration === submittedGeneration) {
      state.accounts = result.account;
      state.selectedAccounts.clear();
      state.dirty = false;
      $('accounts-dirty').textContent = '';
      notify('账号已保存，连接配置正在热更新。');
    } else {
      notify('已保存先前的修改；保存期间有新的本地编辑，请再次点击「保存并应用」。');
    }
    renderAccounts();
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
      const formatted = state.logMessageMode === 'cq' ? line.cq_text : line.op_text;
      text = formatted ?? text;
      const timestamp =
        typeof line.time === 'number'
          ? new Date(line.time * 1000).toLocaleString()
          : line.time || '';
      text = `${timestamp ? `[${timestamp}] ` : ''}[${levels[line.level] || 'INFO'}] ${text}`;
    } else if (line.name) {
      text = `${line.name}：${text}`;
    }
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
async function loadLogDisplay() {
  const result = await api('/api/logs/display');
  if (state.logMessageMode !== result.format) {
    state.logMessageMode = result.format;
    if (state.page === 'logs') renderLogs();
  }
  $('log-message-mode').value = state.logMessageMode;
}
async function openLogs() {
  const generation = ++logGeneration;
  closeStream('logs');
  state.logs = [];
  renderLogs();
  await loadLogDisplay();
  const selected = selectedLogLevels();
  if (!selected.length) return;
  // 全选等价于不过滤，后端约定用空 level 表示。
  const filter = selected.length === Object.keys(levels).length ? '' : selected.join(',');
  const query = `level=${encodeURIComponent(filter)}`;
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
  const previous = state.selected;
  const result = await api('/api/terminals');
  state.terminals = result.items;
  state.selected =
    state.terminals.find(
      (item) => item.hash === state.selected?.hash && item.model === state.selected?.model,
    ) ||
    state.terminals[0] ||
    null;
  renderTerminals();
  const switched =
    previous?.hash !== state.selected?.hash || previous?.model !== state.selected?.model;
  if (state.page === 'terminals' && state.selected && switched) openTerminal(state.selected);
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
const qrBindPath = '/api/accounts/qqguild/qr-bind';

function deleteQrBind(path, token) {
  // 卸载时仍发出 DELETE；过期登录的清理响应不应打断新登录。
  return fetch(path, { method: 'DELETE', headers: { 'X-Auth-Token': token }, keepalive: true })
    .catch(() => {});
}

function releaseQRCode() {
  const qr = state.qr;
  if (!qr) return;
  state.qr = null;
  clearTimeout(qr.timer);
  qr.controller.abort();
  const removal = qr.path ? deleteQrBind(qr.path, qr.token) : null;
  if (qr.imageURL) URL.revokeObjectURL(qr.imageURL);
  $('qr-image').hidden = $('qr-link').hidden = true;
  $('qr-image').removeAttribute('src');
  $('qr-link').removeAttribute('href');
  return removal;
}

function closeQRCode() {
  const removal = releaseQRCode();
  if ($('qr-dialog').open) $('qr-dialog').close();
  return removal;
}

function openQRCode(title, apply = null) {
  releaseQRCode();
  const qr = { apply, token: state.token, controller: new AbortController() };
  state.qr = qr;
  $('qr-title').textContent = title;
  $('qr-image').hidden = $('qr-link').hidden = true;
  $('qr-status').hidden = $('qr-actions').hidden = !apply;
  $('qr-status').textContent = apply ? '正在获取二维码…' : '';
  if (!$('qr-dialog').open) $('qr-dialog').showModal();
  return qr;
}

function qrIsOpen(qr) {
  return state.qr === qr && $('qr-dialog').open;
}

async function loadQRImage(qr, path) {
  const response = await fetch(path, {
    headers: { 'X-Auth-Token': qr.token }, signal: qr.controller.signal, cache: 'no-store',
  });
  if (!response.ok) throw new Error('二维码已失效或不可读取');
  const blob = await response.blob();
  if (!qrIsOpen(qr)) return;
  qr.imageURL = URL.createObjectURL(blob);
  $('qr-image').src = qr.imageURL;
  $('qr-image').hidden = false;
}

function setQRLink(url, origin = null) {
  if (!safeURL(url, origin)) return;
  $('qr-link').href = url;
  $('qr-link').hidden = false;
}

async function showQRCode(terminal) {
  if (state.qr?.apply) return; // 终端推送不能取代用户正在确认的官方绑定。
  const qr = openQRCode(`请使用账号 ${terminal.id || terminal.hash} 扫码`);
  setQRLink(terminal.qrcode_url);
  if (!terminal.qrcode) return;
  try {
    await loadQRImage(qr, `/api/terminal/${encodeURIComponent(terminal.model)}/${encodeURIComponent(terminal.hash)}/qrcode`);
  } catch (error) {
    if (qrIsOpen(qr)) {
      $('qr-status').hidden = false;
      $('qr-status').textContent = error.message;
    }
  }
}

function showQrBindError(qr, message) {
  if (!qrIsOpen(qr)) return;
  // 停止旧会话并清除失效链接，保留原入口供刷新重试。
  openQRCode($('qr-title').textContent, qr.apply);
  $('qr-status').textContent = message;
}

async function pollQrBind(qr, interval) {
  if (!qrIsOpen(qr)) return;
  try {
    const result = await api(qr.path, { signal: qr.controller.signal });
    if (!qrIsOpen(qr)) return;
    if (result.status === 2) {
      const credentials = Array.isArray(result.credentials)
        ? result.credentials.filter((item) => item?.app_id && item?.app_secret)
        : [];
      if (!credentials.length) throw new Error('未收到机器人凭据，请刷新二维码重试。');
      closeQRCode();
      try {
        await qr.apply(credentials);
      } catch (error) {
        notifyError(error);
      }
    } else if (result.status === 0 || result.status === 1) {
      $('qr-status').textContent = '请使用手机 QQ 扫码并确认绑定。';
      qr.timer = setTimeout(() => pollQrBind(qr, interval), interval);
    } else {
      showQrBindError(qr, '二维码已过期，请刷新二维码。');
    }
  } catch (error) {
    showQrBindError(qr, error.message);
  }
}

async function startQrBind(apply) {
  const qr = openQRCode(apply === createScannedAccount ? 'QQ 官方扫码创建' : 'QQ 官方扫码填入', apply);
  const pathFor = (result) => `${qrBindPath}/${encodeURIComponent(result.bind_id)}`;
  try {
    // 不中断建单：即便用户已取消，也必须接收迟到的 bind_id 并释放服务端会话。
    const result = await api(qrBindPath, { method: 'POST' }, (late) => deleteQrBind(pathFor(late), qr.token));
    if (!qrIsOpen(qr)) return deleteQrBind(pathFor(result), qr.token);
    qr.path = pathFor(result);
    setQRLink(result.qr_url, 'https://q.qq.com');
    await loadQRImage(qr, `${qr.path}/qrcode`);
    if (!qrIsOpen(qr)) return;
    $('qr-status').textContent = '请使用手机 QQ 扫码并确认绑定。';
    const interval = result.poll_interval * 1000;
    qr.timer = setTimeout(() => pollQrBind(qr, interval), interval);
  } catch (error) {
    showQrBindError(qr, error.message);
  }
}

function safeURL(value, origin = null) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password &&
      (!origin || url.origin === origin);
  } catch {
    return false;
  }
}
async function loadPlugins() {
  const generation = ++state.pluginListGeneration;
  const result = await api('/api/plugins');
  if (generation !== state.pluginListGeneration) return result;
  const plugins = result.shallow_plugin_data_dict || {};
  // 重载未完成时宿主可能仍是旧列表；不要把已经收起的菜单和页面刷回来。
  if (state.pluginReload && Object.keys(plugins).length) return result;
  state.plugins = plugins;
  state.pluginOrder = result.shallow_plugin_order_list || [];
  state.pluginPriority = result.shallow_plugin_priority_dict || {};
  state.priorityRevision = result.revision || '';
  state.priorityError = result.priority_error || '';
  state.pages = result.shallow_plugin_webui_list || [];
  renderPlugins();
  renderPluginNavigation();
  return result;
}
function scheduleTimezoneLabel(zone) {
  if (!zone) return '未知';
  if (zone === 'UTC') return '协调世界时';
  if (Object.hasOwn(timezoneCitiesZh, zone)) return timezoneCitiesZh[zone];
  try {
    const format = new Intl.DateTimeFormat('zh-CN', { timeZone: zone, timeZoneName: 'longGeneric' });
    const canonical = format.resolvedOptions().timeZone;
    if (Object.hasOwn(timezoneCitiesZh, canonical)) return timezoneCitiesZh[canonical];
    const name = format.formatToParts(0).find((part) => part.type === 'timeZoneName')?.value;
    if (name && /[\u3400-\u9fff]/.test(name)) return name;
    return name ? `协调世界时偏移（${name}）` : `时区 ${zone}`;
  } catch (error) {
    if (!(error instanceof RangeError)) throw error;
    return `时区 ${zone}`;
  }
}

function renderScheduleSettings(message = '') {
  const result = state.scheduleSettings;
  const settings = result?.settings;
  const select = $('plugin-schedule-timezone');
  const status = $('plugin-schedule-status');
  select.disabled = !settings?.revision || state.scheduleSaving;
  $('plugin-schedule-save').disabled = select.disabled || !select.value || select.value === settings.timezone;
  if (message || !settings) {
    status.textContent = message || '正在读取时区设置…';
  } else if (settings.error) {
    status.textContent = settings.error;
  } else if (!result.active) {
    status.textContent = '等待插件加载器报告生效时区。';
  } else {
    const active = result.active;
    const zone = active.effective_timezone;
    const current = active.error || `当前生效：${scheduleTimezoneLabel(zone)}${zone ? `（${zone}）` : ''}`;
    status.textContent = active.revision === settings.revision
      ? current : `${current}。已保存的设置将在重载插件后生效。`;
  }
}
function applyScheduleSettings(result, preserveDraft) {
  const select = $('plugin-schedule-timezone');
  const previous = state.scheduleSettings;
  const draft = preserveDraft && previous?.settings.revision && select.value !== previous.settings.timezone
    ? select.value : '';
  const selected = draft || result.settings.timezone || '';
  state.scheduleSettings = result;
  const choicesChanged = previous?.choices.length !== result.choices.length ||
    result.choices.some((zone, index) => zone !== previous?.choices[index]);
  if ((choicesChanged || selected !== select.value) && selectMenuState.select === select) closeSelectMenu(true);
  if (choicesChanged) {
    const zones = element('optgroup', null, { label: '指定时区' });
    const aliases = [];
    for (const zone of result.choices) {
      const option = element('option', scheduleTimezoneLabel(zone), { value: zone, 'data-detail': zone });
      if (zone === 'UTC' || Object.hasOwn(timezoneCitiesZh, zone)) zones.append(option);
      else aliases.push(option);
    }
    // 中文名称相同的候选中，优先显示 CLDR 直接命名的时区，再显示别名。
    zones.append(...aliases);
    select.replaceChildren(element('option', '跟随系统', { value: 'system' }), zones);
  }
  select.value = selected;
  if (draft && previous.settings.revision !== result.settings.revision) {
    // 保留编辑时的版本，避免后台刷新替用户接受另一标签页的改动。
    state.scheduleSettings = { ...result, settings: previous.settings };
    renderScheduleSettings('其他窗口已修改时区。重新进入插件页以读取最新值。');
  } else {
    renderScheduleSettings();
  }
}
async function loadScheduleSettings(preserveDraft = false) {
  const sequence = ++state.scheduleRequest;
  try {
    const result = await api('/api/plugins/schedule');
    if (sequence === state.scheduleRequest) applyScheduleSettings(result, preserveDraft);
  } catch (error) {
    if (sequence === state.scheduleRequest && !error.authHandled && !error.authObsolete) {
      renderScheduleSettings(`读取时区设置失败：${error.message}`);
    }
  }
}
async function saveScheduleSettings(event) {
  event.preventDefault();
  const settings = state.scheduleSettings?.settings;
  const timezone = $('plugin-schedule-timezone').value;
  if (state.scheduleSaving || !settings?.revision || !timezone || timezone === settings.timezone) return;
  const generation = state.authGeneration;
  ++state.scheduleRequest;
  state.scheduleSaving = true;
  renderScheduleSettings('正在保存时区…');
  let message = '';
  try {
    const result = await api('/api/plugins/schedule', { method: 'PUT', body: { timezone, revision: settings.revision } });
    ++state.scheduleRequest;
    applyScheduleSettings(result, false);
    notify('时区设置已保存，重载插件后生效。');
  } catch (error) {
    if (!error.authHandled && !error.authObsolete) {
      if (error.status === 409) await loadScheduleSettings();
      message = error.message;
    }
  } finally {
    if (generation === state.authGeneration) {
      state.scheduleSaving = false;
      renderScheduleSettings(message);
    }
  }
}
function renderTkBridgeSettings() {
  const settings = state.tkBridgeSettings;
  const panels = settings?.panels || [];
  const preview = state.tkBridge;
  if (preview && settings) {
    const panel = panels.find((entry) => entry.namespace === preview.panel.namespace && entry.event === preview.panel.event);
    if (settings.generation !== preview.generation || !panel?.available || !panel.enabled || panel.closing) {
      failTkPreview(preview, panel?.reason || '面板已关闭，请重新打开。');
    }
  }
  const availablePanels = panels.filter((panel) => panel.available);
  $('tk-bridge-panel').hidden = !availablePanels.length;
  $('tk-bridge-empty').hidden = !settings || availablePanels.length > 0;
  $('tk-bridge-panels').replaceChildren(...availablePanels.map((panel) => {
    const row = element('div', null, { class: 'toolbar' });
    const toggle = element('input', null, { type: 'checkbox' });
    toggle.checked = panel.enabled;
    toggle.disabled = !settings.revision;
    const label = element('label');
    label.append(toggle, ` ${panel.title} · ${panel.namespace}`);
    const launch = panel.enabled && panel.applied && !panel.closing
      ? button(`${panel.title} · Tk 兼容`, () => openTkPreview(panel)) : null;
    toggle.addEventListener('change', async () => {
      const sequence = ++state.tkBridgeRequest;
      toggle.disabled = true;
      try {
        const result = await api('/api/tk_bridge/config', {
          method: 'PUT',
          body: { namespace: panel.namespace, event: panel.event, enabled: toggle.checked, revision: settings.revision },
        });
        if (sequence === state.tkBridgeRequest) {
          state.tkBridgeSettings = result;
          renderTkBridgeSettings();
        }
        await loadTkBridgeSettings();
      } catch (err) {
        if (sequence !== state.tkBridgeRequest) return;
        await loadTkBridgeSettings();
        notifyError(err);
      }
    });
    row.append(label);
    if (launch) row.append(launch);
    if (panel.closing || !panel.applied) {
      row.append(element('span', panel.closing || !panel.enabled ? '正在撤销…' : '应用中…', { class: 'hint' }));
    }
    return row;
  }));
  renderTkMenuStatus(state.menuNamespace);
}
async function loadTkBridgeSettings() {
  const sequence = ++state.tkBridgeRequest;
  try {
    const result = await api('/api/tk_bridge');
    if (sequence !== state.tkBridgeRequest) return;
    state.tkBridgeSettings = result;
    renderTkBridgeSettings();
  } catch (error) {
    if (sequence === state.tkBridgeRequest) notifyError(error);
  }
}
function tkRequest(preview, op, fields = {}) {
  return api('/api/tk_bridge', {
    method: 'POST',
    body: { op, namespace: preview.panel.namespace, event: preview.panel.event, bridge_id: preview.id, ...fields },
  });
}
function finishTkPreview(release = true) {
  const preview = state.tkBridge;
  state.tkBridge = null;
  if (preview) clearInterval(preview.timer);
  if ($('tk-bridge-dialog').open) $('tk-bridge-dialog').close();
  $('tk-bridge-content').replaceChildren();
  if (release && preview?.id && state.token) tkRequest(preview, 'close').catch(notifyError);
}
function failTkPreview(preview, message) {
  if (preview.failed) return;
  preview.failed = true;
  clearInterval(preview.timer);
  $('tk-bridge-content').replaceChildren();
  $('tk-bridge-status').textContent = message;
  if (preview.id && state.token) {
    tkRequest(preview, 'close').catch(notifyError);
    preview.id = '';
  }
}
function renderTkSnapshot(preview, snapshot, sectionId) {
  const content = $('tk-bridge-content');
  const regions = [];
  let previousGroup;
  for (const section of snapshot.sections) {
    const previous = preview.regions.get(section.id);
    const data = JSON.stringify(section);
    if (!sectionId && section.group && section.group !== previousGroup) {
      regions.push(element('h3', section.group));
    }
    previousGroup = section.group;
    if (previous?.data === data && previous.partial === Boolean(sectionId)) {
      regions.push(previous.region);
      continue;
    }
    const region = element('section');
    if (section.title) region.append(element(section.group ? 'h4' : 'h3', section.title));
    if (section.type === 'label' || section.type === 'text') {
      region.append(element(section.type === 'text' ? 'pre' : 'p', section.text));
      if (section.truncated) region.append(element('p', '内容已截断。', { class: 'hint' }));
    } else if (section.type === 'table') {
      const wrap = element('div', null, { class: 'table-wrap' });
      const table = element('table');
      const header = element('tr');
      for (const label of section.columns) header.append(element('th', label, { scope: 'col' }));
      table.createTHead().append(header);
      const body = table.createTBody();
      for (const row of section.rows) {
        const cells = row.cells.map((value) => element('td', value));
        if (row.has_children && cells.length) {
          cells[0].append(button('展开', () => refreshTkPreview(preview, { section_id: section.id, node_id: row.id })));
        }
        body.insertRow().append(...cells);
      }
      wrap.append(table);
      region.append(wrap);
      if (section.next_cursor) {
        region.append(button('下一页', () => refreshTkPreview(preview, {
          section_id: section.id, cursor: section.next_cursor,
        })));
      } else if (section.truncated && !sectionId) {
        region.append(button('单独查看此表', () => refreshTkPreview(preview, { section_id: section.id })));
      }
    }
    if (sectionId) {
      region.prepend(button('回到首屏', () => refreshTkPreview(preview, {})));
      previous?.region.replaceWith(region);
    }
    preview.regions.set(section.id, { region, data, partial: Boolean(sectionId) });
    regions.push(region);
  }
  if (!sectionId) {
    const focused = content.contains(document.activeElement) ? document.activeElement : null;
    content.replaceChildren(...regions);
    if (focused?.isConnected) focused.focus({ preventScroll: true });
  }
}
async function refreshTkPreview(preview, fields = null) {
  if (state.tkBridge !== preview || preview.busy || preview.failed || !preview.id) return;
  preview.busy = true;
  try {
    const paused = document.hidden || state.page !== 'plugins' || preview.detail;
    const op = fields !== null || !paused ? 'read' : 'renew';
    const params = fields ?? (op === 'read' && preview.revision ? { revision: preview.revision } : {});
    const result = await tkRequest(preview, op, params);
    if (state.tkBridge !== preview || preview.failed || !result.snapshot) return;
    if (fields?.section_id) preview.detail = true;
    else {
      preview.detail = false;
      preview.revision = result.snapshot.revision;
    }
    $('tk-bridge-status').textContent = '只读预览；编辑请使用桌面面板或原生 WebUI。';
    renderTkSnapshot(preview, result.snapshot, fields?.section_id);
  } catch (error) {
    if (state.tkBridge !== preview || preview.failed) return;
    if (error.code === 'busy') return;
    if (error.code === 'data_changed') {
      preview.detail = true;
      preview.revision = '';
      preview.regions.clear();
      $('tk-bridge-content').replaceChildren(button('重新读取首屏', () => refreshTkPreview(preview, {})));
      $('tk-bridge-status').textContent = error.message;
      return;
    }
    failTkPreview(preview, error.message || '面板已关闭，请退出后重新打开。');
  } finally {
    preview.busy = false;
  }
}
async function openTkPreview(panel) {
  if (state.tkBridge) return;
  const preview = { panel, id: '', timer: null, busy: false, detail: false, revision: '', regions: new Map(),
    generation: state.tkBridgeSettings.generation };
  state.tkBridge = preview;
  const authGeneration = state.authGeneration;
  $('tk-bridge-title').textContent = `${panel.title} · Tk 兼容`;
  $('tk-bridge-status').textContent = '正在打开只读面板…';
  $('tk-bridge-dialog').showModal();
  try {
    const result = await tkRequest(preview, 'open');
    preview.id = result.bridge_id;
    if (state.tkBridge !== preview || preview.failed) {
      if (state.authGeneration === authGeneration) await tkRequest(preview, 'close');
      return;
    }
    $('tk-bridge-status').textContent = '只读预览；编辑请使用桌面面板或原生 WebUI。';
    preview.revision = result.snapshot.revision;
    renderTkSnapshot(preview, result.snapshot);
    preview.timer = setInterval(() => refreshTkPreview(preview), 5000);
  } catch (error) {
    if (state.tkBridge === preview) $('tk-bridge-status').textContent = error.message;
  }
}
function pluginPageRestoreTarget() {
  if (state.page !== 'plugin-page' || !state.frameNamespace || !state.framePath) return null;
  return { namespace: state.frameNamespace, path: state.framePath };
}
function suspendPluginPages() {
  if (!state.pluginReload) {
    state.pluginReload = {
      navigation: state.navigationGeneration,
      active: pluginPageRestoreTarget(),
      hadFrames: state.frames.size > 0,
    };
  }
  state.pluginListGeneration++;
  if (state.frames.size) destroyFrames();
  $('menu-dialog').close();
  if (state.page === 'plugin-page') setPageTitle('插件页面');
  state.plugins = {};
  state.pages = [];
  renderPlugins();
  renderPluginNavigation();
}
async function restorePluginsAfterReload(reloaded = true) {
  const pending = state.pluginReload;
  state.pluginReload = null;
  const navigation = pending?.navigation ?? state.navigationGeneration;
  const active = pending?.active ?? pluginPageRestoreTarget();
  const hadFrames = pending?.hadFrames || state.frames.size > 0;
  if (state.frames.size) destroyFrames();
  await loadPlugins();
  if (active && navigation === state.navigationGeneration && state.page === 'plugin-page') {
    const page = state.pages.find((entry) => embeddedPluginPage(entry) &&
      entry.namespace === active.namespace && entry.path === active.path);
    if (page) {
      try {
        await openPluginPage(page);
        if (reloaded) notify('插件已重载，当前插件页面已自动重新打开；未保存的内容可能需要重新填写。');
      } catch (error) {
        notifyError(error);
      }
    } else {
      await navigate('plugins');
      if (reloaded) notify('插件已重载，原插件页面已不可用，请从列表重新选择。');
    }
  } else if (hadFrames && reloaded) {
    notify('插件已重载，缓存的插件页面已刷新。');
  }
}
function pluginEffectivePriority(namespace, plugin) {
  const info = state.pluginPriority[namespace] || {};
  return Number.isInteger(info.effective) ? info.effective : plugin[6] || 0;
}
// 与 GUI 侧边栏同一套文案，避免两个界面读到的优先级说法不一致。
function pluginPriorityText(namespace, plugin) {
  const info = state.pluginPriority[namespace] || {};
  const effective = pluginEffectivePriority(namespace, plugin);
  if (!Number.isInteger(info.user)) return `${effective}（默认）`;
  return `${effective}（用户 ${info.user} / 默认 ${info.default ?? effective}）`;
}
// 与加载器的 (生效优先级, namespace) 排序保持一致。
function namespaceCompare(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}
function pluginEntries() {
  const rank = new Map(state.pluginOrder.map((namespace, index) => [namespace, index]));
  const fallback = (namespace, plugin) =>
    state.pluginOrder.length + pluginEffectivePriority(namespace, plugin);
  return Object.entries(state.plugins).sort((a, b) => {
    const left = rank.has(a[0]) ? rank.get(a[0]) : fallback(a[0], a[1]);
    const right = rank.has(b[0]) ? rank.get(b[0]) : fallback(b[0], b[1]);
    return left - right || namespaceCompare(a[0], b[0]);
  });
}
function sortedPluginOrder() {
  return Object.keys(state.plugins).sort(
    (a, b) =>
      pluginEffectivePriority(a, state.plugins[a]) - pluginEffectivePriority(b, state.plugins[b]) ||
      namespaceCompare(a, b),
  );
}
function priorityCell(namespace, plugin, position) {
  const info = state.pluginPriority[namespace] || {};
  const effective = pluginEffectivePriority(namespace, plugin);
  const user = Number.isInteger(info.user) ? info.user : null;
  const cell = element('td', null, { class: 'priority-cell' });
  const editor = element('div', null, { class: 'priority-editor' });
  const input = document.createElement('input');
  input.type = 'number';
  input.step = '1';
  input.min = '0';
  input.value = String(effective);
  input.className = 'priority-input';
  input.setAttribute('aria-label', `${plugin[0]} 的优先级`);
  input.disabled = !!state.priorityError;
  const current = () => {
    if (input.value === '') return null;
    const value = Number(input.value);
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  };
  const apply = button('应用', () => savePluginPriority(namespace, current()));
  const reset = button('默认', () => savePluginPriority(namespace, null));
  apply.disabled = true;
  reset.disabled = user === null || !!state.priorityError;
  input.addEventListener('input', () => {
    apply.disabled = current() === null || current() === effective;
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !apply.disabled) apply.click();
  });
  editor.append(input, apply, reset);
  cell.append(editor);
  const source = element('span', null, { class: 'priority-source' });
  const rank = `第 ${position + 1} 位`;
  source.textContent = user === null
    ? `${rank} · 默认 ${info.default ?? effective}`
    : `${rank} · 用户 ${user}（默认 ${info.default ?? '—'}）`;
  cell.append(source);
  return cell;
}
async function savePluginPriority(namespace, priority) {
  if (priority !== null && (!Number.isSafeInteger(priority) || priority < 0))
    throw new Error('优先级必须是非负整数');
  if (!state.priorityRevision) throw new Error(state.priorityError || '插件优先级文件不可编辑');
  const result = await api('/api/plugins/priority', {
    method: 'PUT',
    body: { revision: state.priorityRevision, plugins: { [namespace]: priority } },
  });
  state.priorityRevision = result.revision || '';
  const info = { ...(state.pluginPriority[namespace] || {}) };
  info.default = info.default ?? state.plugins[namespace]?.[6] ?? 0;
  info.user = priority;
  info.effective = priority === null ? info.default : priority;
  info.source = priority === null ? 'default' : 'user';
  state.pluginPriority[namespace] = info;
  state.pluginOrder = sortedPluginOrder();
  renderPlugins();
  notify(priority === null ? '已恢复默认优先级' : `优先级已更新为 ${priority}，正在热生效`);
}
// 优先级可能被其它会话改动，弹窗只会在打开时写一次文案；列表重渲染时同步刷新，
// 避免已打开的菜单一直显示过期的生效优先级。
function refreshOpenMenuPriority() {
  if (!$('menu-dialog').open) {
    state.menuNamespace = '';
    return;
  }
  const namespace = state.menuNamespace;
  if (!namespace) return;
  const plugin = state.plugins[namespace];
  if (!plugin) {
    // 插件被卸载后弹窗内容已无意义，直接关掉。
    state.menuNamespace = '';
    $('menu-dialog').close();
    return;
  }
  $('menu-priority').textContent = pluginPriorityText(namespace, plugin);
}
function renderPlugins() {
  const header = element('tr');
  const columns = [
    ...(state.showPath ? ['路径'] : []),
    '插件',
    '版本',
    '作者',
    '优先级',
    '操作',
  ];
  for (const text of columns) header.append(element('th', text));
  $('plugin-head').replaceChildren(header);
  $('plugin-rows').replaceChildren();
  $('plugin-priority-error').hidden = !state.priorityError;
  $('plugin-priority-error').textContent = state.priorityError || '';
  const plugins = pluginEntries();
  plugins.forEach(([namespace, plugin], position) => {
    const row = element('tr');
    if (state.showPath) {
      // plugin[5] 是插件所在的上级目录，Windows 分隔符统一成正斜杠再拼相对路径。
      const prefix = plugin[5] ? `${plugin[5].replaceAll('\\', '/')}/` : '';
      row.append(element('td', `/${prefix}${namespace}`));
    }
    row.append(element('td', plugin[0]), element('td', plugin[1]), element('td', plugin[2]));
    row.append(priorityCell(namespace, plugin, position));
    const cell = element('td');
    cell.append(button('菜单', () => pluginMenu(namespace)));
    row.append(cell);
    row.ondblclick = () => pluginMenu(namespace);
    $('plugin-rows').append(row);
  });
  if (!plugins.length) {
    const row = element('tr');
    row.append(element('td', '暂无已加载的插件。', { colspan: state.showPath ? 6 : 5 }));
    $('plugin-rows').append(row);
  }
  $('toggle-path').textContent = state.showPath ? '隐藏路径' : '显示路径';
  refreshOpenMenuPriority();
}
function renderTkMenuStatus(namespace) {
  const status = $('menu-tk-status');
  const settings = state.tkBridgeSettings;
  const hasMenu = Boolean(state.plugins[namespace]?.[3]?.length);
  status.hidden = !settings || !hasMenu;
  if (status.hidden) return;
  const match = settings.panels.some((panel) => panel.namespace === namespace);
  status.textContent = settings.error || (match
    ? '在插件页的「可转换为 WebUI 的 GUI 面板」区域管理只读预览。'
    : '此插件版本没有已审核的 Tk 兼容描述，不能开启网页预览。原菜单不变。');
}

function pluginMenu(namespace) {
  const plugin = state.plugins[namespace];
  state.menuNamespace = namespace;
  $('menu-title').textContent = plugin[0];
  // 插件名可能重复，信息区固定按 命名空间 / 优先级 / 介绍 展示，与 GUI 侧边栏一致。
  $('menu-namespace').textContent = namespace;
  $('menu-priority').textContent = pluginPriorityText(namespace, plugin);
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
  renderTkMenuStatus(namespace);
  $('menu-dialog').showModal();
}
function pluginPagePath(page) {
  const path = page.path;
  if (typeof path !== 'string' || /[\\:*?"<>|\u0000-\u001f]/.test(path)) return null;
  const invalid = path
    .split('/')
    .some((part) => !part || part.startsWith('.') || /[ .]$/.test(part));
  return invalid ? null : path;
}
function embeddedPluginPage(page) {
  return page.type === 'iframe' && typeof page.path === 'string' && pluginPagePath(page) !== null;
}
function pluginPageLabel(page) {
  const pages = state.pages.filter(
    (item) => embeddedPluginPage(item) || (item.type === 'link' && safeURL(item.url)),
  );
  const name = state.plugins[page.namespace]?.[0] || page.namespace;
  const duplicateName = pages.some(
    (item) =>
      item.namespace !== page.namespace &&
      (state.plugins[item.namespace]?.[0] || item.namespace) === name,
  );
  const siblings = pages.filter((item) => item.namespace === page.namespace);
  let label = duplicateName ? `${name}（${page.namespace}）` : name;
  if (siblings.length > 1 || page.title !== name) label += ` / ${page.title}`;
  if (siblings.filter((item) => item.title === page.title).length > 1) {
    label += `（${page.type === 'iframe' ? page.path : page.url}）`;
  }
  return label;
}
function appendPluginPage(container, page) {
  if (page.type === 'link') {
    const entry = element('a', page.title, {
      href: page.url,
      target: '_blank',
      rel: 'noopener noreferrer',
      class: 'plugin-link-external',
    });
    container.append(entry);
    return entry;
  }
  const row = element('div', null, { class: 'plugin-link-row' });
  const entry = button(page.title, () => openPluginPage(page), 'plugin-link-entry');
  entry.dataset.pluginNamespace = page.namespace;
  entry.dataset.pluginPath = page.path;
  // 每个页面单独关闭；只有已保活（还在缓存里）的条目才显示这个 ×。
  const close = button('×', () => closePluginPage(page), 'plugin-link-close');
  const label = pluginPageLabel(page);
  entry.title = page.title;
  entry.setAttribute('aria-label', page.title);
  close.title = `关闭：${label}`;
  close.setAttribute('aria-label', `关闭 ${label}`);
  row.append(entry, close);
  container.append(row);
  return entry;
}
function renderPluginNavigation() {
  $('plugin-links').replaceChildren();
  const groups = new Map();
  for (const page of state.pages) {
    if (!embeddedPluginPage(page) && !(page.type === 'link' && safeURL(page.url))) continue;
    if (!groups.has(page.namespace)) groups.set(page.namespace, []);
    groups.get(page.namespace).push(page);
  }
  for (const namespace of state.collapsedPluginGroups) {
    if ((groups.get(namespace)?.length || 0) < 2) state.collapsedPluginGroups.delete(namespace);
  }
  for (const [namespace, pages] of groups) {
    const group = element('div', null, { class: 'plugin-page-group' });
    group.dataset.pluginNamespace = namespace;
    const name = state.plugins[namespace]?.[0] || namespace;
    const label = element('span', null, { class: 'plugin-group-label' });
    const groupName = element('span', name, { class: 'plugin-group-name' });
    groupName.title = name;
    const groupNamespace = element('span', namespace, { class: 'plugin-group-namespace' });
    groupNamespace.title = namespace;
    label.append(groupName, groupNamespace);
    if (pages.length === 1) {
      const page = pages[0];
      const entry = appendPluginPage(group, page);
      entry.classList.add('plugin-single-entry');
      const pageLabel = element('span', null, { class: 'plugin-group-label' });
      const pageName = element('span', page.title, { class: 'plugin-group-name' });
      pageName.title = page.title;
      const pageNamespace = element('span', namespace, { class: 'plugin-group-namespace' });
      pageNamespace.title = namespace;
      pageLabel.append(pageName, pageNamespace);
      entry.replaceChildren(pageLabel);
      entry.title = name;
      entry.setAttribute('aria-label', `${page.title}（${namespace}）`);
      $('plugin-links').append(group);
      continue;
    }
    const id = `plugin-page-children-${$('plugin-links').children.length}`;
    const toggle = button(null, () => {
      setPluginGroupExpanded(group, toggle.getAttribute('aria-expanded') !== 'true');
    }, 'plugin-group-toggle');
    toggle.id = `${id}-toggle`;
    toggle.setAttribute('aria-controls', id);
    toggle.append(
      element('span', '▾', { class: 'disclosure-arrow', 'aria-hidden': 'true' }),
      label,
      element('span', String(pages.length), {
        class: 'plugin-group-count',
        'aria-label': `${pages.length} 个页面`,
      }),
    );
    const children = element('div', null, {
      id,
      class: 'plugin-group-children',
      role: 'group',
      'aria-labelledby': toggle.id,
    });
    const titles = new Map();
    for (const page of pages) titles.set(page.title, (titles.get(page.title) || 0) + 1);
    for (const page of pages) {
      const entry = appendPluginPage(children, page);
      entry.title = page.title;
      entry.setAttribute('aria-label', `${page.title}（${namespace}）`);
      if (titles.get(page.title) > 1) {
        const path = page.type === 'iframe' ? page.path : page.url;
        entry.setAttribute('aria-label', `${page.title}（${namespace}） / ${path}`);
        entry.append(
          element('span', path, {
            class: 'plugin-entry-path',
          }),
        );
      }
    }
    group.append(toggle, children);
    setPluginGroupExpanded(group, !state.collapsedPluginGroups.has(namespace));
    $('plugin-links').append(group);
  }
  if (!$('plugin-links').children.length) $('plugin-links').append(element('p', '暂无插件页面'));
  let unloaded = false;
  for (const key of [...state.frames.keys()]) {
    if (state.plugins[state.frames.get(key).namespace]) continue;
    destroyFrame(key);
    unloaded = true;
  }
  if (unloaded) notify('插件页面已卸载。');
  syncPluginSelection();
}
function setPluginGroupExpanded(group, expanded) {
  group.querySelector('.plugin-group-toggle').setAttribute('aria-expanded', String(expanded));
  group.querySelector('.plugin-group-children').hidden = !expanded;
  if (expanded) state.collapsedPluginGroups.delete(group.dataset.pluginNamespace);
  else state.collapsedPluginGroups.add(group.dataset.pluginNamespace);
}
function syncPluginSelection() {
  $('plugin-links').querySelectorAll('.plugin-link-entry').forEach((entry) => {
    const active =
      entry.dataset.pluginNamespace === state.frameNamespace &&
      entry.dataset.pluginPath === state.framePath;
    const cached = state.frames.has(
      frameKey(entry.dataset.pluginNamespace, entry.dataset.pluginPath),
    );
    entry.classList.toggle('active', active);
    entry.classList.toggle('cached', cached && !active);
    if (active) entry.setAttribute('aria-current', 'page');
    else entry.removeAttribute('aria-current');
    // 单项 × 只在页面还活着时出现；用 visibility 占位，避免出现/消失时行高跳动
    const close = entry.parentElement.querySelector('.plugin-link-close');
    if (close) close.style.visibility = cached ? 'visible' : 'hidden';
  });
  $('plugin-links').querySelectorAll('.plugin-page-group').forEach((group) => {
    const toggle = group.querySelector('.plugin-group-toggle');
    if (!toggle) return;
    toggle.classList.toggle('contains-active', !!group.querySelector('.plugin-link-entry.active'));
    toggle.classList.toggle('contains-cached', !!group.querySelector('.plugin-link-entry.cached'));
  });
  const count = state.frames.size;
  const close = $('plugin-pages-close');
  close.hidden = count === 0;
  close.title = count
    ? `关闭全部插件页面（${framePluginCount()} 个插件，${count} 个页面）`
    : '关闭全部插件页面';
  close.setAttribute('aria-label', close.title);
}
function framePluginCount() {
  return new Set([...state.frames.values()].map((entry) => entry.namespace)).size;
}
function closePluginPage(page) {
  const key = frameKey(page.namespace, page.path);
  if (!state.frames.has(key)) return;
  const wasActive = state.frameNamespace === page.namespace && state.framePath === page.path;
  destroyFrame(key);
  notify(`已关闭插件页面：${pluginPageLabel(page)}`);
  if (wasActive) navigate('plugins').catch(notifyError);
}
function closePluginPages() {
  const count = state.frames.size;
  if (!count) return;
  const pluginCount = framePluginCount();
  destroyFrames();
  notify(`已关闭全部插件页面（${pluginCount} 个插件，共 ${count} 个页面）。`);
  if (state.page === 'plugin-page') navigate('plugins').catch(notifyError);
}
function frameKey(namespace, path) {
  return `${namespace}\n${path}`;
}
function entryOfWindow(source) {
  for (const entry of state.frames.values())
    if (entry.frame.contentWindow === source) return entry;
  return null;
}
function postToFrame(entry, payload) {
  const target = entry && entry.frame.contentWindow;
  if (target) target.postMessage(payload, '*');
}
// 保活的插件页面即使被隐藏也会继续跑定时器与轮询，用可见性通知让插件能自行暂停
function postVisibility(entry, visible) {
  postToFrame(entry, { type: 'olivos:plugin_visibility', visible });
}
function touchFrame(key) {
  const at = state.frameOrder.indexOf(key);
  if (at >= 0) state.frameOrder.splice(at, 1);
  state.frameOrder.push(key);
}
function destroyFrame(key) {
  const entry = state.frames.get(key);
  if (!entry) return;
  entry.frame.remove();
  state.frames.delete(key);
  const at = state.frameOrder.indexOf(key);
  if (at >= 0) state.frameOrder.splice(at, 1);
  for (const [id, owner] of [...state.requests]) if (owner === key) state.requests.delete(id);
  if (state.frame === entry.frame) {
    state.frame = null;
    state.frameNamespace = null;
    state.framePath = null;
  }
  syncPluginSelection();
}
// 超限时销毁最久未使用的页面：hidden 并不会释放内存，只能真销毁
function trimFrames() {
  const limit = Math.max(1, state.frameCacheLimit);
  let dropped = 0;
  while (state.frameOrder.length > limit) {
    const key = state.frameOrder[0];
    const entry = state.frames.get(key);
    if (!entry) {
      state.frameOrder.shift();
      continue;
    }
    if (state.frame === entry.frame) break;
    destroyFrame(key);
    dropped += 1;
  }
  if (dropped) notify(`插件页面超过保活上限 ${limit} 个，已释放最久未使用的 ${dropped} 个。`);
}
function showFrame(entry) {
  for (const item of state.frames.values()) {
    item.frame.hidden = item !== entry;
    postVisibility(item, item === entry);
  }
  state.frame = entry ? entry.frame : null;
  state.frameNamespace = entry ? entry.namespace : null;
  state.framePath = entry ? entry.path : null;
  syncPluginSelection();
}
function dropExternalFrame() {
  if (state.externalFrame) state.externalFrame.remove();
  state.externalFrame = null;
  state.externalPage = null;
}
// 离开插件页签：内嵌页面留驻 DOM 保活，外部临时页面不参与缓存直接销毁
function hideFrames() {
  dropExternalFrame();
  for (const entry of state.frames.values()) {
    entry.frame.hidden = true;
    postVisibility(entry, false);
  }
  state.frame = null;
  state.frameNamespace = null;
  state.framePath = null;
  syncPluginSelection();
}
function destroyFrames() {
  dropExternalFrame();
  for (const entry of state.frames.values()) entry.frame.remove();
  state.frames.clear();
  state.frameOrder.length = 0;
  state.requests.clear();
  state.frame = null;
  state.frameNamespace = null;
  state.framePath = null;
  syncPluginSelection();
}
async function openPluginPage(page) {
  const routePath = pluginPagePath(page);
  if (routePath === null) return;
  const navigation = state.navigationGeneration + 1;
  await navigate('plugin-page');
  if (navigation !== state.navigationGeneration) return;
  dropExternalFrame();
  const key = frameKey(page.namespace, page.path);
  let entry = state.frames.get(key);
  if (!entry) {
    hideFrames();
    // Cookie 可能已过期或被清除，必须先修复再发起 iframe 导航。
    await ensureSession(true);
    if (navigation !== state.navigationGeneration) return;
    const filename = routePath.split('/').map(encodeURIComponent).join('/');
    const frame = element('iframe', null, {
      title: page.title,
      src: `/plugin/${encodeURIComponent(page.namespace)}/${filename}`,
      sandbox: pluginSandbox,
    });
    entry = { key, frame, namespace: page.namespace, path: page.path };
    state.frames.set(key, entry);
    $('plugin-frame-container').append(frame);
    // 加载完成时补一次可见性，避免刚就绪的页面不知道自己究竟在前台还是后台
    frame.addEventListener('load', () => postVisibility(entry, state.frame === frame));
  }
  entry.frame.title = page.title;
  touchFrame(key);
  showFrame(entry);
  // 打开页面时把它所属的分组展开，否则侧栏里看不到当前页在哪。
  for (const group of $('plugin-links').querySelectorAll('.plugin-page-group')) {
    if (group.dataset.pluginNamespace !== page.namespace) continue;
    if (group.querySelector('.plugin-group-toggle')) setPluginGroupExpanded(group, true);
  }
  trimFrames();
  setPageTitle(page.title);
  rememberPage();
}
async function openExternalPage(page) {
  await navigate('plugin-page');
  hideFrames();
  const title = page.title || '插件页面';
  state.externalPage = { url: page.url, title };
  state.externalFrame = element('iframe', null, {
    src: page.url,
    title,
    sandbox: externalSandbox,
  });
  $('plugin-frame-container').append(state.externalFrame);
  rememberPage();
  setPageTitle(title);
}
window.addEventListener('message', async (ev) => {
  if (ev.origin !== 'null') return;
  const entry = entryOfWindow(ev.source);
  if (!entry) return;
  const data = ev.data;
  if (data?.type === 'olivos:plugin_auth_required') {
    if (entry.authRetried) {
      notify('插件页面登录恢复失败，请关闭此插件页后重新打开。');
      return;
    }
    entry.authRetried = true;
    try {
      await ensureSession(true);
      if (state.frames.get(entry.key) === entry) entry.frame.src = entry.frame.src;
    } catch (error) {
      notifyError(error);
    }
    return;
  }
  if (
    !data ||
    data.type !== 'olivos:plugin_event' ||
    typeof data.event !== 'string' ||
    typeof data.request_id !== 'string' ||
    data.request_id.length > 128
  )
    return;
  entry.authRetried = false;
  // 同一 request_id 仍在处理中时丢弃重复投递，避免插件页面重发导致事件被执行多次
  if (state.requests.has(data.request_id)) return;
  if (state.requests.size >= 128) {
    notify('插件页面等待回包过多，请刷新页面。');
    return;
  }
  try {
    state.requests.set(data.request_id, entry.key);
    await ensureSession();
    await api('/api/plugin_event', {
      method: 'POST',
      body: {
        namespace: entry.namespace,
        event: data.event,
        payload: data.payload,
        request_id: data.request_id,
        session: state.session,
      },
    });
  } catch (error) {
    state.requests.delete(data.request_id);
    postToFrame(entry, {
      type: 'olivos:plugin_reply',
      request_id: data.request_id,
      error: error.message,
    });
  }
});
// 同一个操作在插件页和仪表盘各有一个按钮，禁用状态必须同步。
function actionButtons(kind) {
  return kind === 'reload' ? ['reload-plugins', 'dashboard-reload-plugins'] : ['check-update'];
}
function clearAction(kind) {
  clearTimeout(state.actions[kind]?.timer);
  state.actions[kind] = null;
  for (const id of actionButtons(kind)) $(id).disabled = false;
}
function showActionResult(kind, message) {
  // 结果用非阻塞提示条呈现，避免重载这类高频操作反复弹出模态窗口。
  notify(`${kind === 'reload' ? '重载插件' : '检查更新'}：${message}`);
}
function finishAction(kind, result) {
  const pending = state.actions[kind];
  if (!pending || !Number.isFinite(result.started_at)) return;
  if (!pending.result || result.started_at >= pending.result.started_at) pending.result = result;
  if (pending.startedAt === null || pending.result.started_at < pending.startedAt) return;
  const { message, rejected } = pending.result;
  clearAction(kind);
  if (rejected && kind === 'reload' && state.pluginReload) restorePluginsAfterReload(false).catch(notifyError);
  showActionResult(kind, message);
}
async function runAction(kind, path, progress) {
  if (state.actions[kind]) return;
  const pending = { startedAt: null, result: null, timer: null };
  state.actions[kind] = pending;
  for (const id of actionButtons(kind)) $(id).disabled = true;
  notify(progress);
  pending.timer = setTimeout(() => {
    clearAction(kind);
    showActionResult(kind, '等待操作完成超时，请查看日志确认结果。');
  }, 90000);
  try {
    const result = await api(path, { method: 'POST' });
    if (state.actions[kind] !== pending) return;
    pending.startedAt = result.started_at;
    if (kind === 'reload') suspendPluginPages();
    if (pending.result) finishAction(kind, pending.result);
  } catch (error) {
    if (state.actions[kind] !== pending) return;
    clearAction(kind);
    if (state.token) showActionResult(kind, error.message || String(error));
  }
}
async function onPluginsEvent(item) {
  // 纯优先级调整不重载插件，只刷新列表，保留已打开的插件页面。
  if (item.priority_only) {
    await loadPlugins();
    return;
  }
  if (!item.ready) {
    // 加载器未就绪时会广播空列表。只有宿主当前也确实为空才收起菜单和页面；
    // 会话重连回放旧事件时宿主仍有插件，忽略以免长时间运行后丢页。
    const generation = ++state.pluginListGeneration;
    const result = await api('/api/plugins');
    if (generation !== state.pluginListGeneration) return;
    if (Object.keys(result.shallow_plugin_data_dict || {}).length) return;
    finishTkPreview(false);
    if (state.page === 'plugins') await loadTkBridgeSettings();
    suspendPluginPages();
    return;
  }
  await restorePluginsAfterReload();
  if (state.page === 'plugins') await Promise.all([loadTkBridgeSettings(), loadScheduleSettings(true)]);
  finishAction('reload', {
    started_at: item.started_at,
    message: `插件重载完成，当前已加载 ${Object.keys(state.plugins).length} 个插件。`,
  });
}
async function handleEvent(item) {
  if (item.type === 'plugins') {
    const run = () => onPluginsEvent(item);
    state.pluginEventChain = state.pluginEventChain.then(run, run);
    await state.pluginEventChain;
  } else if (item.type === 'tk_bridge_status') {
    if (state.page === 'plugins') await loadTkBridgeSettings();
  } else if (item.type === 'plugin_schedule_status') {
    if (state.page === 'plugins' && !state.scheduleSaving) await loadScheduleSettings(true);
  } else if (item.type === 'plugin_schedule_lifecycle_rejected' && item.operation === 'restart') {
    const pending = state.actions.reload;
    if (pending && Number.isFinite(item.started_at) &&
        (pending.startedAt === null || item.started_at === pending.startedAt)) {
      const tasks = (item.tasks || []).map((task) => `${task.namespace}/${task.task_id}`).join('、');
      const reason = item.reason === 'timeout' ? '等待定时任务退出超时' : '插件加载器正忙';
      finishAction('reload', { started_at: item.started_at, message: `${reason}${tasks ? `：${tasks}` : ''}，本次重载已取消。`, rejected: true });
    }
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
    finishAction('update', {
      started_at: item.started_at,
      message: messages[item.status] || messages.error,
    });
    await refreshStatus();
  } else if (item.type === 'plugin_reply' && state.requests.has(item.request_id)) {
    const entry = state.frames.get(state.requests.get(item.request_id));
    state.requests.delete(item.request_id);
    if (entry && entry.namespace === item.namespace) {
      postToFrame(entry, {
        type: 'olivos:plugin_reply',
        request_id: item.request_id,
        payload: item.payload,
      });
    }
  } else if (item.type === 'open_page' && safeURL(item.url)) {
    await openExternalPage(item);
  }
}
function eventBatch(items) {
  for (const item of items) {
    if (state.seenEvents.has(item.sequence)) continue;
    state.seenEvents.add(item.sequence);
    if (state.seenEvents.size > state.limit * 2) {
      state.seenEvents.delete(state.seenEvents.values().next().value);
    }
    handleEvent(item).catch(notifyError);
  }
}

$('login-form').addEventListener('submit', login);
bind('logout', logout);
bind('performance-processes-refresh', () => refreshPerformanceProcesses());
bind('performance-nav-toggle', togglePerformanceNav);
bind('performance-nav-close', () => setPerformanceNavOpen(false));
bind('performance-nav-backdrop', () => setPerformanceNavOpen(false));
document.addEventListener('keydown', trapPerformanceNavFocus);
bind('plugin-pages-close', closePluginPages);
document.querySelectorAll('[data-performance-window]').forEach((button) => {
  button.addEventListener('click', () => {
    const key = button.dataset.performanceWindow;
    if (!performanceWindowKeys.includes(key) || button.disabled) return;
    state.performanceWindow = key;
    if (state.performanceStatistics) renderPerformanceStatistics(state.performanceStatistics);
  });
});
document.querySelectorAll('[data-performance-category]').forEach((button) => {
  button.addEventListener('click', () => {
    setPerformanceCategory(button.dataset.performanceCategory, {
      refreshProcesses: true,
      reveal: true,
    });
    setPerformanceNavOpen(false);
  });
  button.addEventListener('keydown', (event) => {
    const direction = {
      ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1,
    }[event.key];
    if (!direction) return;
    event.preventDefault();
    const buttons = [...document.querySelectorAll('[data-performance-category]')];
    const index = buttons.indexOf(button);
    const next = buttons[(index + direction + buttons.length) % buttons.length];
    setPerformanceCategory(next.dataset.performanceCategory, {
      refreshProcesses: true,
      reveal: true,
    });
    next.focus();
  });
});
bind('sidebar-toggle', toggleSidebar);
bind('sidebar-close', () => setSidebarOpen(false));
bind('sidebar-backdrop', () => setSidebarOpen(false));
document.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Escape') return;
  if (state.accountDragging || activeAccountMenu) {
    ev.preventDefault();
    if (state.accountDragging) finishAccountDrag(false);
    else closeAccountMenu(true);
    return;
  }
  if (state.performanceNavOpen) {
    ev.preventDefault();
    setPerformanceNavOpen(false);
    return;
  }
  if (!state.sidebarOpen) return;
  ev.preventDefault();
  setSidebarOpen(false);
});
document.addEventListener('click', (ev) => {
  if (!state.sidebarOpen || !ev.target.closest('#plugin-links .plugin-link-external')) return;
  setSidebarOpen(false, { restoreFocus: false });
});
document
  .querySelectorAll('[data-page]')
  .forEach((node) =>
    node.addEventListener('click', () => navigate(node.dataset.page).catch(notifyError)),
  );
document
  .querySelectorAll('[data-close]')
  .forEach((node) => node.addEventListener('click', () => $(node.dataset.close).close()));
bind('add-account', () => editAccount(null));
bind('account-add-general', () => {
  closeAccountMenu(true);
  editAccount(null);
});
bind('account-add-qr', () => {
  closeAccountMenu(true);
  if (state.dirty && !confirm('快捷扫码创建会一并保存并应用当前未提交的账号修改，是否继续？')) return;
  return startQrBind(createScannedAccount);
});
bind('account-qr-fill', () => startQrBind(fillScannedAccount));
bind('qr-refresh', () => {
  if (state.qr?.apply) return startQrBind(state.qr.apply);
});
$('qr-dialog').addEventListener('close', () => {
  if (!$('qr-dialog').open) releaseQRCode();
});
$('account-dialog').addEventListener('close', () => {
  if (!$('account-dialog').open && state.qr?.apply === fillScannedAccount) closeQRCode();
});
for (const event of ['pointerdown', 'focusin']) {
  document.addEventListener(event, (ev) => {
    if (activeAccountMenu && !activeAccountMenu.contains(ev.target)) closeAccountMenu();
  });
}
for (const split of document.querySelectorAll('.account-split')) {
  split.querySelector('.account-split-toggle').addEventListener('click', () => {
    if (activeAccountMenu === split) closeAccountMenu(true);
    else openAccountMenu(split);
  });
  split.addEventListener('keydown', (event) => {
    const direction = { ArrowUp: -1, ArrowDown: 1 }[event.key];
    if (!direction || split.querySelector('.account-split-toggle').disabled) return;
    event.preventDefault();
    if (activeAccountMenu !== split) {
      openAccountMenu(split);
    } else {
      const items = [...split.querySelectorAll('[role="menuitem"]')];
      const index = items.indexOf(event.target);
      items[index < 0 ? 0 : (index + direction + items.length) % items.length].focus();
    }
  });
}
window.addEventListener('resize', () => closeAccountMenu());
bind('accounts-select-all', (event) => {
  const checked = event.currentTarget.checked;
  state.selectedAccounts.clear();
  for (const row of state.accounts) {
    if (checked) state.selectedAccounts.add(accountRowId(row));
  }
  for (const input of $('account-rows').querySelectorAll('.account-select')) input.checked = checked;
  updateAccountSelection();
}, 'change');
bind('export-accounts-copy', () => copyAccounts(selectedAccounts()));
bind('account-export-clipboard', () => {
  closeAccountMenu(true);
  return copyAccounts(selectedAccounts());
});
bind('account-export-file', () => {
  closeAccountMenu(true);
  downloadAccounts();
});
bind('account-import-clipboard', importAccountsFromClipboard);
bind('account-import-file-trigger', () => {
  closeAccountMenu(true);
  $('account-import-file').click();
});
bind('account-import-file', importAccountsFromFile, 'change');
bind('account-import-text', () => {
  if (!accountImport) return;
  accountImport.request++;
  clearAccountImportPreview();
  accountImportMessage('');
}, 'input');
bind('account-import-parse', () => {
  if (!accountImport) return;
  return previewAccountImport(accountImport, $('account-import-text').value);
});
bind('account-import-check-conflicts', () => setAccountImportConflicts(true));
bind('account-import-uncheck-conflicts', () => setAccountImportConflicts(false));
bind('account-import-confirm', confirmAccountImport);
$('account-import-dialog').addEventListener('close', () => {
  if ($('account-import-dialog').open || !accountImport) return;
  clearAccountImportPreview();
  accountImport = null;
  $('account-import-text').value = '';
});
$('account-copy-fallback-dialog').addEventListener('close', () => {
  if (!$('account-copy-fallback-dialog').open) $('account-copy-fallback-text').value = '';
});
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
    else replaceAccount(state.editing, clone(state.draft));
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
bind('log-message-mode', async (ev) => {
  const mode = ev.target.value;
  try {
    const result = await api('/api/logs/display', { method: 'PUT', body: { format: mode } });
    state.logMessageMode = result.format;
    renderLogs();
  } catch (error) {
    ev.target.value = state.logMessageMode;
    throw error;
  }
}, 'change');
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
bind('open-plugin-folder', async () => {
  const result = await api('/api/plugins/open', { method: 'POST' });
  notify(`已在文件管理器中打开插件目录：${result.path}`);
});
bind('plugin-schedule-timezone', () => renderScheduleSettings(), 'change');
bind('plugin-schedule-form', saveScheduleSettings, 'submit');
bind('tk-bridge-dialog', () => {
  if (!$('tk-bridge-dialog').open) finishTkPreview();
}, 'close');
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopUptimeLoop();
    return;
  }
  if (state.tkBridge?.id) refreshTkPreview(state.tkBridge);
  if (state.token && isStatusPage(state.page)) {
    if (state.page === 'dashboard') startUptimeLoop();
    refreshStatus().then(() => ensureSession()).catch(notifyError);
  }
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
    // 用户可以取消离开：此时不要销毁仍在编辑的绑定。
    ev.preventDefault();
    ev.returnValue = '';
  } else {
    // 未触发离开确认时尽早发送；Chromium 可能丢弃仅在 pagehide 发起的 keepalive。
    closeQRCode();
  }
});
window.addEventListener('pagehide', () => {
  const qr = state.qr;
  const worker = navigator.serviceWorker?.controller;
  if (qr?.path && worker?.scriptURL === new URL('/service-worker.js', location.origin).href) {
    worker.postMessage({ type: 'olivos:cancel-qr-bind', path: qr.path, token: qr.token });
  }
  closeQRCode();
  revokeExportBlobUrls();
  for (const name of [...state.streams.keys()]) closeStream(name);
  clearInterval(state.timer);
  clearInterval(state.dashboardTimer);
  stopUptimeLoop();
});
window.addEventListener('pageshow', (ev) => {
  if (ev.persisted && state.token) login(null, state.token);
});
window.addEventListener('hashchange', () => {
  const ticket = takeLoginTicket();
  if (ticket !== null) {
    login(null, null, ticket);
  }
});
{
  initializeSidebar();
  initializeSelectMenus();
  syncPerformanceFactGrids();
  window.addEventListener('resize', schedulePerformanceFactGridSync);
  if (performanceFactColumnsQuery.addEventListener) {
    performanceFactColumnsQuery.addEventListener('change', schedulePerformanceFactGridSync);
  } else {
    performanceFactColumnsQuery.addListener(schedulePerformanceFactGridSync);
  }
  loadPublicVersion();
  if (document.readyState === 'complete') registerServiceWorker();
  else window.addEventListener('load', registerServiceWorker, { once: true });
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
  if (startupTicket !== null) {
    login(null, null, startupTicket);
  } else if (savedToken?.startsWith('webui.')) {
    login(null, savedToken);
  } else if (savedToken) {
    // 旧版缓存的是长期 Token，升级后需要手动登录一次。
    resetLogin();
  } else {
    $('loading').hidden = true;
    $('login').hidden = false;
  }
}
