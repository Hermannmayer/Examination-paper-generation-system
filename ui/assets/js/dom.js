/* ==========================================================================
   dom.js —— DOM 小工具 + 提示条 / 状态栏
   ========================================================================== */

window.App = window.App || {};

App.dom = (function () {
  'use strict';

  function byId(id) { return document.getElementById(id); }

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  function option(value, label) {
    var node = document.createElement('option');
    node.value = value;
    node.textContent = label;
    return node;
  }

  return { byId: byId, make: make, clear: clear, option: option };
})();

/* 提示条：warning 与 error 都以数据形式呈现，绝不使用 alert() */
App.notice = (function () {
  'use strict';

  var bar = null;
  var list = null;
  var closeBtn = null;
  var timer = null;

  function init() {
    bar = App.dom.byId('noticeBar');
    list = App.dom.byId('noticeList');
    closeBtn = App.dom.byId('noticeClose');
    if (closeBtn) closeBtn.addEventListener('click', hide);
  }

  function show(items, kind) {
    if (!bar || !list) return;
    if (timer) { clearTimeout(timer); timer = null; }

    App.dom.clear(list);
    items.forEach(function (item) {
      var li = App.dom.make('li');
      if (item.code) li.appendChild(App.dom.make('span', 'notice__code', item.code));
      var body = App.dom.make('span');
      body.textContent = item.message || '';
      li.appendChild(body);
      if (item.hint) {
        var hint = App.dom.make('span', 'hint hint--inline', '（' + item.hint + '）');
        li.appendChild(hint);
      }
      list.appendChild(li);
    });

    bar.dataset.kind = kind || 'warning';
    bar.hidden = false;

    // 错误不自动消失，必须让用户看到
    if (kind !== 'error') {
      timer = setTimeout(hide, 9000);
    }
  }

  function warnings(items) {
    if (!items || !items.length) return;
    show(items, 'warning');
  }

  function error(err) {
    var item = err || {};
    show([{ code: item.code, message: item.message, hint: item.hint }], 'error');
  }

  function hide() {
    if (bar) bar.hidden = true;
    if (timer) { clearTimeout(timer); timer = null; }
  }

  return { init: init, warnings: warnings, error: error, hide: hide, show: show };
})();

App.status = (function () {
  'use strict';
  var node = null;

  function set(text) {
    if (!node) node = App.dom.byId('statusbar');
    if (node) node.textContent = text;
  }

  return { set: set };
})();
