/* ==========================================================================
   bridge.js —— 与 Python 通信的唯一通道

   注意：本文件是**普通脚本**，不是 ES module。
   本程序以 file:// 加载页面、不开本地 HTTP 服务，Chromium 在这种情况下
   会拒绝 <script type="module">。同理也不能用 fetch()。
   ========================================================================== */

window.App = window.App || {};

App.bridge = (function () {
  'use strict';

  var readyPromise = null;
  var onWarnings = null;

  /** pywebview 注入 api 对象后才可调用。 */
  function ready() {
    if (readyPromise) return readyPromise;
    readyPromise = new Promise(function (resolve) {
      if (window.pywebview && window.pywebview.api) {
        resolve();
        return;
      }
      window.addEventListener('pywebviewready', function () { resolve(); }, { once: true });
    });
    return readyPromise;
  }

  function BridgeError(error) {
    this.name = 'BridgeError';
    this.code = (error && error.code) || 'INTERNAL';
    this.message = (error && error.message) || '未知错误';
    this.hint = (error && error.hint) || '';
    this.details = (error && error.details) || {};
  }
  BridgeError.prototype = Object.create(Error.prototype);

  /**
   * 调用一个 Python 方法。
   * 成功返回 { data, warnings }；失败抛出 BridgeError。
   */
  async function call(method) {
    var args = Array.prototype.slice.call(arguments, 1);
    await ready();

    var api = window.pywebview.api;
    var fn = api && api[method];
    if (typeof fn !== 'function') {
      throw new BridgeError({ code: 'NO_METHOD', message: '接口不存在: ' + method });
    }

    var envelope;
    try {
      envelope = await fn.apply(api, args);
    } catch (transportError) {
      throw new BridgeError({
        code: 'TRANSPORT',
        message: '与后台通信失败：' + (transportError && transportError.message
          ? transportError.message : String(transportError))
      });
    }

    if (!envelope || envelope.ok !== true) {
      throw new BridgeError(envelope && envelope.error);
    }

    var warnings = envelope.warnings || [];
    if (warnings.length && typeof onWarnings === 'function') {
      onWarnings(warnings);
    }
    return { data: envelope.data, warnings: warnings };
  }

  /** 便捷封装：只要 data。 */
  async function data(method) {
    var args = Array.prototype.slice.call(arguments, 1);
    var result = await call.apply(null, [method].concat(args));
    return result.data;
  }

  return {
    ready: ready,
    call: call,
    data: data,
    BridgeError: BridgeError,
    setWarningHandler: function (handler) { onWarnings = handler; }
  };
})();
