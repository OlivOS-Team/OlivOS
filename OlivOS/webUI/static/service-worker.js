'use strict';

const CACHE_NAME = 'olivos-webui-v2';
const CACHE_PREFIX = 'olivos-webui-';
const STATIC_FILES_URL = '/static/static-files.json';
const PRIVATE_PREFIXES = ['/api/', '/ws/', '/plugin/'];
let appShellPromise;

function isPrivate(pathname) {
  return PRIVATE_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

async function loadAppShell() {
  const response = await fetch(STATIC_FILES_URL, { cache: 'no-store' });
  if (!response.ok) throw new Error('无法读取 WebUI 静态资源清单');
  const files = await response.json();
  const urls = [
    '/',
    ...Object.entries(files.root || {})
      .filter(([, config]) => config.precache !== false)
      .map(([name]) => `/${name}`),
    ...(files.static || []).map((name) => `/static/${name}`),
  ];
  if (!urls.includes(STATIC_FILES_URL)) urls.push(STATIC_FILES_URL);
  return {
    urls,
    paths: new Set(urls.map((url) => new URL(url, self.location.origin).pathname)),
  };
}

function appShell() {
  if (!appShellPromise) {
    appShellPromise = loadAppShell().catch((error) => {
      appShellPromise = null;
      throw error;
    });
  }
  return appShellPromise;
}

async function canCache(url) {
  if (url.search !== '') return false;
  const shell = await appShell();
  return url.pathname === '/' || shell.paths.has(url.pathname);
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    try {
      if (response.ok && await canCache(new URL(request.url))) {
        const cache = await caches.open(CACHE_NAME);
        await cache.put(request, response.clone());
      }
    } catch {
      // 清单或缓存不可用时仍返回本次网络响应。
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) return cached;
    if (request.mode === 'navigate') {
      const shell = await caches.match('/');
      if (shell) return shell;
    }
    throw error;
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    appShell().then((shell) => caches.open(CACHE_NAME).then((cache) => cache.addAll(shell.urls))),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  );
});

// 只代宿主页面完成卸载时的绑定清理；浏览器可在普通 fetch 发出前销毁该页面。
// 不缓存令牌、请求或响应，插件页面也不能借此指定请求目标。
self.addEventListener('message', (event) => {
  const data = event.data;
  if (data?.type !== 'olivos:cancel-qr-bind' || event.source?.type !== 'window') return;
  const source = new URL(event.source.url);
  if (source.origin !== self.location.origin || source.pathname !== '/' ||
      typeof data.path !== 'string' || !/^\/api\/accounts\/qqguild\/qr-bind\/[\w-]+$/.test(data.path) ||
      typeof data.token !== 'string') return;
  event.waitUntil(fetch(data.path, {
    method: 'DELETE', headers: { 'X-Auth-Token': data.token }, cache: 'no-store', redirect: 'error',
  }).catch(() => {}));
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.headers.has('range')) return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isPrivate(url.pathname)) return;
  if (request.mode !== 'navigate' && !url.pathname.startsWith('/static/')) return;
  event.respondWith(networkFirst(request));
});
