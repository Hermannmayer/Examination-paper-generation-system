/* ==========================================================================
   preview.js —— 试卷预览（渲染真实 PDF）
   ==========================================================================

   预览栏显示的是**真正要导出的那个 PDF**，用内嵌的 pdf.js 渲染，
   所以分页、换行、字体、行距与实际导出文件逐像素一致。

   早先的版本是另做一套 HTML 题目列表，和导出文件对不上 ——
   用户一眼就能看出「预览不是我要的东西」。
   ========================================================================== */

window.App = window.App || {};

App.preview = (function () {
  'use strict';

  /* 请求序号：预览是异步的，快速连点会让旧请求后到并覆盖新结果。
     每次发起时自增，回来后比对，不是最新的就丢弃。 */
  var reqId = 0;
  var autoRefresh = true;
  var cachedPdf = null;      // 已加载的 PDF，供窗口缩放时重排复用
  var target = 'paper';      // 'paper' 试卷 / 'card' 答题卡

  var PDFJS_AVAILABLE = typeof window.pdfjsLib !== 'undefined';

  if (PDFJS_AVAILABLE) {
    // 以 file:// 加载时无法 new Worker(file://...)，pdf.js 会回退到
    // 主线程的假 worker —— 那条路径能用 <script> 加载，file:// 下是允许的。
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'js/vendor/pdf.worker.min.js';
  }

  function isAuto() { return autoRefresh; }
  function setAuto(on) { autoRefresh = !!on; }
  function getTarget() { return target; }

  /** 切换预览对象（试卷 / 答题卡）。会重新渲染，但走的是同一套 PDF 管线。 */
  function setTarget(next) {
    var value = next === 'card' ? 'card' : 'paper';
    if (value === target) return;
    target = value;
    syncTargetButtons();
    cachedPdf = null;
    refresh();
  }

  function syncTargetButtons() {
    [['previewPaper', 'paper'], ['previewCard', 'card']].forEach(function (pair) {
      var node = App.dom.byId(pair[0]);
      if (!node) return;
      var active = pair[1] === target;
      node.classList.toggle('is-active', active);
      node.setAttribute('aria-selected', active ? 'true' : 'false');
    });
  }

  /* ── 刷新 ─────────────────────────────────────────────────────── */

  async function refresh() {
    // 刻意不做「有请求在跑就直接返回」的节流：那样手动点「刷新预览」时
    // 若正好赶上一次自动刷新，就会毫无反应。并发由下面的 reqId 处理 ——
    // 旧请求回来后发现自己不是最新的，自己丢弃结果。
    var my = ++reqId;

    var container = App.dom.byId('pageView');
    container.setAttribute('aria-busy', 'true');

    try {
      var result = await App.bridge.call('preview', App.config.read(), target);
      if (my !== reqId) return;              // 已有更新的请求，丢弃本次结果

      renderStats(result.data);
      await renderDocument(result.data, my);
      if (my !== reqId) return;
      App.status.set('预览已更新　' + (target === 'card' ? '答题卡' : '试卷')
        + '　共 ' + result.data.total_count + ' 题　'
        + result.data.total_score + ' 分　·　与实际导出文件一致');
    } catch (error) {
      if (my !== reqId) return;
      if (error.code !== 'NOT_LOADED' && error.code !== 'NO_TYPE_SELECTED') {
        App.notice.error(error);
      }
      showEmpty(messageFor(error));
    } finally {
      if (my === reqId) {
        container.setAttribute('aria-busy', 'false');
      }
    }
  }

  function messageFor(error) {
    if (error.code === 'NOT_LOADED') return '请先在左侧选择题库文件并加载。';
    if (error.code === 'NO_TYPE_SELECTED') return '请至少勾选一种题型并填写数量。';
    return error.message || '无法生成预览。';
  }

  function showEmpty(text) {
    var container = App.dom.byId('pageView');
    App.dom.clear(container);
    container.appendChild(App.dom.make('p', 'doc__empty', text));
    App.dom.byId('statLine').textContent = '—';
    setFallback(null);
  }

  /* ── 渲染 PDF ─────────────────────────────────────────────────── */

  async function renderDocument(data, my) {
    var container = App.dom.byId('pageView');
    setFallback(null);

    if (!data.pdf_base64) {
      showEmpty('预览渲染失败。可直接导出后查看文件。');
      return;
    }
    if (!PDFJS_AVAILABLE) {
      offerSystemViewer('当前环境不支持内嵌 PDF 预览');
      return;
    }

    var bytes;
    try {
      bytes = base64ToBytes(data.pdf_base64);
    } catch (error) {
      offerSystemViewer('预览数据解析失败');
      return;
    }

    var pdf;
    try {
      pdf = await window.pdfjsLib.getDocument({ data: bytes, isEvalSupported: false }).promise;
    } catch (error) {
      // 常见于 file:// 下 worker 起不来 —— 给一条总能走通的路
      offerSystemViewer('内嵌 PDF 渲染不可用（' + (error && error.message ? error.message : error) + '）');
      return;
    }

    if (my !== reqId) return;               // 渲染期间又刷新了

    cachedPdf = pdf;
    App.dom.clear(container);

    for (var pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
      if (my !== reqId) return;
      var canvas = await renderPage(pdf, pageNumber, container);
      container.appendChild(wrapPage(canvas, pageNumber, pdf.numPages));
    }
    container.scrollTop = 0;
  }

  /** 窗口尺寸变化时按新宽度重排，复用已加载的 PDF，不重新请求后端。 */
  async function relayout() {
    if (!cachedPdf) return;
    var my = reqId;
    var container = App.dom.byId('pageView');
    if (!container || container.querySelector('.doc__empty')) return;

    App.dom.clear(container);
    for (var pageNumber = 1; pageNumber <= cachedPdf.numPages; pageNumber++) {
      if (my !== reqId) return;             // 期间用户又改了配置，让新渲染接管
      var canvas = await renderPage(cachedPdf, pageNumber, container);
      container.appendChild(wrapPage(canvas, pageNumber, cachedPdf.numPages));
    }
  }

  async function renderPage(pdf, pageNumber, container) {
    var page = await pdf.getPage(pageNumber);
    var unscaled = page.getViewport({ scale: 1 });

    // 让页面宽度贴合预览栏，再用设备像素比放大以保证清晰
    var available = Math.max(240, (container.clientWidth || 600) - 36);
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var scale = (available / unscaled.width) * dpr;
    var viewport = page.getViewport({ scale: scale });

    var canvas = document.createElement('canvas');
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = Math.floor(viewport.width / dpr) + 'px';
    canvas.style.height = Math.floor(viewport.height / dpr) + 'px';
    canvas.className = 'page-canvas';

    await page.render({
      canvasContext: canvas.getContext('2d'),
      viewport: viewport
    }).promise;
    return canvas;
  }

  function wrapPage(canvas, number, total) {
    var figure = App.dom.make('figure', 'page');
    figure.appendChild(canvas);
    figure.appendChild(
      App.dom.make('figcaption', 'page__label', '第 ' + number + ' / ' + total + ' 页')
    );
    return figure;
  }

  function base64ToBytes(base64) {
    var binary = atob(base64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  /* ── 兜底：交给系统查看器 ─────────────────────────────────────── */

  function offerSystemViewer(reason) {
    setFallback(reason + '。可改用系统查看器打开相同的文件：', function () {
      App.bridge.call('open_preview_pdf', App.config.read(), target)
        .catch(function (error) { App.notice.error(error); });
    });
  }

  function setFallback(text, onOpen) {
    var node = App.dom.byId('previewFallback');
    if (!node) return;
    App.dom.clear(node);
    if (!text) {
      node.hidden = true;
      return;
    }
    node.hidden = false;
    node.appendChild(App.dom.make('span', '', text + ' '));
    var button = App.dom.make('button', 'link', '用系统查看器打开');
    button.type = 'button';
    button.addEventListener('click', onOpen);
    node.appendChild(button);
  }

  /* ── 统计行 ───────────────────────────────────────────────────── */

  function renderStats(data) {
    var isCard = (data.target || target) === 'card';
    var parts = [
      isCard ? '答题卡' : '试卷',
      '共 ' + data.total_count + ' 题',
      '总分 ' + data.total_score + ' 分',
      // 答题卡固定 A4，不跟随纸张设置，标出来免得用户以为没生效
      isCard ? 'A4' : data.paper_size
    ];
    (data.sections || []).forEach(function (section) {
      parts.push(section.label + ' ' + section.count + '×' + section.per_score);
    });
    if (data.reused_count) parts.push('复用 ' + data.reused_count + ' 题');
    App.dom.byId('statLine').textContent = parts.join('　|　');
  }

  return {
    refresh: refresh,
    relayout: relayout,
    isAuto: isAuto,
    setAuto: setAuto,
    setTarget: setTarget,
    getTarget: getTarget,
    syncTargetButtons: syncTargetButtons,
    showEmpty: showEmpty,
    renderStats: renderStats,
    pdfjsAvailable: function () { return PDFJS_AVAILABLE; }
  };
})();
