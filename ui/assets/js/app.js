/* ==========================================================================
   app.js —— 初始化与事件接线
   ========================================================================== */

window.App = window.App || {};

App.main = (function () {
  'use strict';

  var POLL_MS = 200;
  var pollTimer = null;
  var currentJob = null;
  var info = null;

  /* ── 启动 ─────────────────────────────────────────────────────── */

  async function start() {
    App.notice.init();
    App.bridge.setWarningHandler(App.notice.warnings);

    App.placeholderPreview();

    try {
      info = await App.bridge.data('get_app_info');
    } catch (error) {
      App.notice.error(error);
      App.status.set('初始化失败');
      return;
    }

    App.dom.byId('versionLine').textContent =
      'v' + info.version + '　|　powered by Hermannmayer';

    if (!info.fonts.cjk_ok) {
      App.notice.show([{
        code: 'FONT_NOT_FOUND',
        message: '系统中找不到中文字体，PDF 导出将不可用',
        hint: '可改用 Word 导出，或安装宋体/黑体后重试'
      }], 'warning');
      App.dom.byId('exportPdf').disabled = true;
      App.dom.byId('pdfFontHint').textContent = '（不可用：缺中文字体）';
    }

    App.config.init(info);
    App.config.renderTypes();
    App.preview.syncTargetButtons();
    await restoreSettings();
    updateCardHint();
    wire();
    App.status.set('就绪　选择题库后即可开始');
  }

  /** 还没有任何预览内容时的占位提示。 */
  App.placeholderPreview = function () {
    App.preview.showEmpty('左侧配置完成后，点击「刷新预览」查看试卷。');
  };

  async function restoreSettings() {
    var saved;
    try {
      saved = await App.bridge.data('load_settings');
    } catch (error) {
      return;
    }
    if (!saved) return;

    if (saved.exam_title === undefined) {
      App.dom.byId('examTitle').value = info.default_exam_title;
      App.dom.byId('studentName').value = info.default_student_info;
    }
    if (saved.paper_size) App.dom.byId('paperSize').value = saved.paper_size;
    if (saved.last_output_dir) App.dom.byId('outputDir').value = saved.last_output_dir;
    App.dom.byId('fileName').value = saved.file_name || '';
    updateFileNamePreview();
    App.dom.byId('exportDocx').checked = saved.export_docx !== false;
    App.dom.byId('exportPdf').checked = !!saved.export_pdf;
    App.dom.byId('exportCard').checked = !!saved.export_card;
    App.dom.byId('exportCardDocx').checked = !!saved.export_card_docx;
    App.dom.byId('includeAnswers').checked = !!saved.include_answers;

    if (saved.last_bank_path) {
      App.dom.byId('bankPath').value = saved.last_bank_path;
      var restored = await loadBank(saved.last_bank_path, true);
      if (restored) return;
    }
    App.dom.byId('bankPath').value = '';
  }

  /* ── 接线 ─────────────────────────────────────────────────────── */

  function wire() {
    byId('btnBrowse').addEventListener('click', onBrowse);
    byId('btnTemplateBank').addEventListener('click', onBundledTemplate);
    byId('btnClearBank').addEventListener('click', onClearBank);
    byId('btnOutputDir').addEventListener('click', onPickOutputDir);
    byId('btnPreview').addEventListener('click', function () {
      App.preview.refresh().catch(function () {});
    });

    // 试卷 / 答题卡 分开预览
    byId('previewPaper').addEventListener('click', function () {
      App.preview.setTarget('paper');
    });
    byId('previewCard').addEventListener('click', function () {
      App.preview.setTarget('card');
    });
    byId('btnExport').addEventListener('click', onExport);
    byId('btnCancelExport').addEventListener('click', onCancelExport);
    byId('btnSaveTemplate').addEventListener('click', onSaveTemplate);
    byId('btnLoadTemplate').addEventListener('click', onLoadTemplate);
    byId('btnHistory').addEventListener('click', onHistory);

    byId('exportMode').addEventListener('change', function () {
      // 切模式先补默认值：按比例若不预填比例、顺序若不预填范围，
      // 用户会看到报错并以为功能坏了。
      App.config.ensureModeDefaults();
      App.config.renderTypes();
      App.preview.refresh().catch(function () {});
    });

    ['includeAnswers', 'randomOrder', 'uniqueAcrossPapers', 'avoidHistory',
      'onPoolExhausted', 'paperSize', 'totalQuestions'].forEach(function (id) {
      byId(id).addEventListener('change', App.config.schedulePreview);
    });

    ['examTitle', 'studentName', 'examTime', 'headerText'].forEach(function (id) {
      byId(id).addEventListener('input', App.config.schedulePreview);
    });

    ['exportDocx', 'exportPdf', 'exportCard', 'exportCardDocx',
      'includeAnswers', 'paperSize'].forEach(function (id) {
      byId(id).addEventListener('change', persistSettings);
    });

    // 勾选/取消答题卡会改变试卷的排版（有无作答横线），必须重排预览
    ['exportCard', 'exportCardDocx'].forEach(function (id) {
      byId(id).addEventListener('change', function () {
        updateCardHint();
        App.preview.refresh().catch(function () {});
      });
    });

    byId('fileName').addEventListener('input', function () {
      updateFileNamePreview();
    });
    byId('fileName').addEventListener('change', persistSettings);

    // 考点搜索：只过滤列表，不动已选内容
    byId('knowledgeSearch').addEventListener('input', function () {
      App.config.renderKnowledge();
    });
    byId('knowledgeClear').addEventListener('click', function () {
      App.config.write(Object.assign(App.config.read(), { knowledge_include: [] }));
      App.preview.refresh().catch(function () {});
    });

    // 预览页按容器宽度渲染，窗口尺寸变了要重排（复用已加载的 PDF，不重新生成）
    var resizeTimer = null;
    window.addEventListener('resize', function () {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        resizeTimer = null;
        App.preview.relayout();
      }, 250);
    });
  }

  function byId(id) { return App.dom.byId(id); }

  function persistSettings() {
    if (!info) return;
    App.bridge.call('save_settings', {
      paper_size: byId('paperSize').value,
      file_name: byId('fileName').value.trim(),
      export_docx: byId('exportDocx').checked,
      export_pdf: byId('exportPdf').checked,
      export_card: byId('exportCard').checked,
      export_card_docx: byId('exportCardDocx').checked,
      include_answers: byId('includeAnswers').checked
    }).catch(function () { /* 设置写不进去不打扰用户 */ });
  }

  /** 文件名输入框的实时预览，让用户看到最终会生成什么名字。 */
  function updateFileNamePreview() {
    var raw = byId('fileName').value.trim();
    var safe = raw.replace(/[\\/:*?"<>|]/g, '');
    var node = byId('fileNamePreview');
    if (node) node.textContent = safe || '试卷';
  }

  /**
   * 勾选答题卡会影响试卷排版，所以要把这条规则说出来 ——
   * 否则用户发现「简答题的作答横线不见了」会以为是 bug。
   */
  function updateCardHint() {
    var node = byId('cardHint');
    if (!node) return;
    var requested = App.config.cardRequested();
    node.hidden = !requested;
    node.textContent = requested
      ? '已勾选答题卡：试卷上不再留作答横线，学生写在答题卡上。'
      : '';
  }

  /* ── 题库 ─────────────────────────────────────────────────────── */

  async function onBrowse() {
    try {
      var picked = await App.bridge.data('pick_bank_file');
      if (picked.cancelled) return;
      await loadBank(picked.path, false);
    } catch (error) {
      App.notice.error(error);
    }
  }

  async function onBundledTemplate() {
    try {
      await App.bridge.data('load_bundled_template');
      var bank = await App.bridge.data('get_bank_info');
      afterBankLoaded(bank, '示例题库');
    } catch (error) {
      App.notice.error(error);
    }
  }

  /** 卸掉当前题库，方便接着选下一个科目的题。 */
  async function onClearBank() {
    try {
      await App.bridge.data('clear_bank');
      App.config.resetBank();
      byId('bankPath').value = '';
      byId('bankInfo').textContent = '支持 .xlsx / .xlsm / .csv';
      byId('btnClearBank').disabled = true;
      App.preview.showEmpty('题库已清除，可以接着选择另一个题库。');
      App.status.set('已清除题库');
    } catch (error) {
      App.notice.error(error);
    }
  }

  async function loadBank(path, silent) {
    try {
      var result = await App.bridge.call('load_excel', path);
      afterBankLoaded(result.data, path);
      return true;
    } catch (error) {
      if (!silent) App.notice.error(error);
      byId('bankInfo').textContent = '题库未加载';
      return false;
    }
  }

  function afterBankLoaded(bank, path) {
    byId('bankPath').value = bank.source || path || '';
    byId('btnClearBank').disabled = false;
    App.config.applyBankInfo(bank);
    App.config.renderTypes();
    App.status.set('题库已加载　共 ' + bank.total + ' 题');
    App.preview.refresh().catch(function () {});
  }

  /* ── 导出 ─────────────────────────────────────────────────────── */

  async function onPickOutputDir() {
    try {
      var picked = await App.bridge.data('pick_output_dir');
      if (picked.cancelled) return;
      byId('outputDir').value = picked.path;
    } catch (error) {
      App.notice.error(error);
    }
  }

  async function onExport() {
    var options = {
      docx: byId('exportDocx').checked,
      pdf: byId('exportPdf').checked,
      card: byId('exportCard').checked,
      card_docx: byId('exportCardDocx').checked,
      include_answers: byId('includeAnswers').checked,
      exam_count: byId('examCount').value,
      file_prefix: byId('fileName').value.trim(),
      output_dir: byId('outputDir').value
    };

    try {
      var started = await App.bridge.data('start_export', App.config.read(), options);
      beginPolling(started.job_id);
    } catch (error) {
      App.notice.error(error);
    }
  }

  function beginPolling(jobId) {
    currentJob = jobId;
    byId('progress').hidden = false;
    byId('btnExport').disabled = true;
    setProgress(0, '已提交…');

    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () { pollJob(jobId); }, POLL_MS);
    pollJob(jobId);
  }

  async function pollJob(jobId) {
    var job;
    try {
      job = await App.bridge.data('get_job', jobId);
    } catch (error) {
      endPolling();
      App.notice.error(error);
      return;
    }
    if (!job) { endPolling(); return; }

    setProgress(job.progress || 0, job.message || '');
    if (!job.done) return;

    endPolling();
    if (job.state === 'done') {
      onExportDone(job.result);
    } else if (job.state === 'cancelled') {
      App.status.set('导出已取消');
      App.notice.show([{ code: 'CANCELLED_BY_USER', message: '导出已取消，未生成文件' }], 'warning');
    } else {
      App.notice.error(job.error);
      App.status.set('导出失败');
    }
  }

  function onExportDone(result) {
    if (!result) return;
    App.status.set('已生成 ' + result.exam_count + ' 份试卷　共 '
      + result.total_count + ' 题 / ' + result.total_score + ' 分');

    App.notice.show([{
      code: 'DONE',
      message: '导出完成：' + result.files.length + ' 个文件已写入 ' + result.output_dir,
      hint: '点此在资源管理器中查看'
    }], 'warning');
    openOnClick(result.files[0] || result.output_dir);
  }

  function openOnClick(path) {
    var list = App.dom.byId('noticeList');
    if (!list) return;
    list.style.cursor = 'pointer';
    list.addEventListener('click', function handler() {
      list.removeEventListener('click', handler);
      App.bridge.call('reveal_in_explorer', path).catch(function () {});
    });
  }

  async function onCancelExport() {
    if (!currentJob) return;
    try {
      await App.bridge.data('cancel_job', currentJob);
      App.status.set('正在取消…');
    } catch (error) {
      App.notice.error(error);
    }
  }

  function endPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    currentJob = null;
    byId('progress').hidden = true;
    byId('btnExport').disabled = false;
  }

  function setProgress(fraction, message) {
    byId('progressFill').style.width = Math.round((fraction || 0) * 100) + '%';
    if (message) byId('progressMsg').textContent = message;
  }

  /* ── 模板 ─────────────────────────────────────────────────────── */

  async function onSaveTemplate() {
    try {
      var result = await App.bridge.data('save_template', App.config.read());
      if (result.cancelled) return;
      App.status.set('模板已保存：' + result.path);
    } catch (error) {
      App.notice.error(error);
    }
  }

  async function onLoadTemplate() {
    try {
      var result = await App.bridge.data('load_template');
      if (result.cancelled) return;
      App.config.write(result.config);
      App.preview.refresh().catch(function () {});
      App.status.set('模板已加载');
    } catch (error) {
      App.notice.error(error);
    }
  }

  /* ── 历史 ─────────────────────────────────────────────────────── */

  async function onHistory() {
    var dialog = byId('historyDialog');
    try {
      var listing = await App.bridge.data('history_list');
      renderHistory(listing);
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', 'open');
    } catch (error) {
      App.notice.error(error);
    }
  }

  function renderHistory(listing) {
    byId('historyPath').textContent = '记录文件：' + listing.path;
    var body = App.dom.clear(byId('historyBody'));

    if (!listing.entries.length) {
      body.appendChild(App.dom.make('p', 'doc__empty', '还没有生成记录。'));
      return;
    }

    listing.entries.forEach(function (entry) {
      var row = App.dom.make('div', 'history-row');
      row.appendChild(App.dom.make('span', 'history-row__time', entry.time.replace('T', ' ')));
      row.appendChild(App.dom.make('span', 'history-row__title', entry.exam_title || '（未命名）'));
      row.appendChild(App.dom.make('span', 'history-row__meta',
        entry.exam_count + ' 份 · ' + entry.qid_count + ' 题'));
      body.appendChild(row);
    });
  }

  function wireHistoryDialog() {
    var dialog = byId('historyDialog');
    byId('historyClose').addEventListener('click', function () {
      if (typeof dialog.close === 'function') dialog.close();
      else dialog.removeAttribute('open');
    });
    byId('historyClear').addEventListener('click', async function () {
      try {
        await App.bridge.data('history_clear');
        onHistory();
        App.status.set('历史记录已清空');
      } catch (error) {
        App.notice.error(error);
      }
    });
  }

  return {
    start: start,
    wireHistoryDialog: wireHistoryDialog
  };
})();

document.addEventListener('DOMContentLoaded', function () {
  App.main.wireHistoryDialog();
  App.main.start();
});
