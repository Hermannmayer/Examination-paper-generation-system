/* ==========================================================================
   config.js —— 配置表单

   与旧 Tkinter 界面的一个关键改进：题型行会**随导出模式变形**
   （随机→数量 / 比例→百分比 / 顺序→题号范围）。

   旧界面把「比例设置」放在另一个独立面板里，用户必须既勾选题型复选框、
   又跑到另一处填比例，两个步骤分离且容易漏。现在同一行内完成。
   ========================================================================== */

window.App = window.App || {};

App.config = (function () {
  'use strict';

  var TYPES = [];
  var rows = {};      // key -> {on, count, score, ratio, start, end, el:{...}}
  var order = [];

  var difficultyValues = [];
  var knowledgeValues = [];
  var difficultyWeights = {};
  var knowledgeInclude = [];
  var bankCounts = {};        // {题型标签: 题量}
  var knowledgeCounts = {};   // {考点: 题量}，用于排序与展示
  var bankLoaded = false;

  /* 考点不一次性全渲染。题库上千题时考点可能有几百个，
     平铺出来会把面板撑到几屏长。先给这么多，其余靠搜索。 */
  var KNOWLEDGE_PREVIEW_LIMIT = 40;

  /* 考点少于这个数时连搜索框都不用出现 */
  var KNOWLEDGE_SEARCH_THRESHOLD = 12;

  function init(info) {
    TYPES = info.question_types || [];
    order = TYPES.map(function (t) { return t.key; });
    TYPES.forEach(function (type) {
      rows[type.key] = {
        on: !!type.default,
        count: '',
        score: String(type.score),
        ratio: '',
        start: '',
        end: ''
      };
    });
  }

  /* ── 题库信息回填 ─────────────────────────────────────────────── */

  function applyBankInfo(bank) {
    difficultyValues = bank.difficulty_values || [];
    knowledgeValues = bank.knowledge_values || [];
    knowledgeCounts = bank.knowledge_counts || {};
    difficultyWeights = {};
    knowledgeInclude = [];
    bankCounts = bank.counts_by_type || {};
    bankLoaded = true;

    // 题库没有这两列时，整块功能区直接不出现，不给用户增加理解成本。
    // 外层 filterGroup 也要一起隐藏，否则会留下一个空标题。
    var hasFilters = difficultyValues.length > 0 || knowledgeValues.length > 0;
    App.dom.byId('filterGroup').hidden = !hasFilters;
    App.dom.byId('difficultyGroup').hidden = difficultyValues.length === 0;
    App.dom.byId('knowledgeGroup').hidden = knowledgeValues.length === 0;

    renderChips();
    renderAvailability(bank);

    TYPES.forEach(function (type) {
      var row = rows[type.key];
      if (!row) return;
      var available = bankCounts[type.label] || 0;
      if (available > 0 && !row.count) row.count = String(available);
      if (available === 0) row.on = false;
    });

    App.dom.byId('bankInfo').textContent =
      '共 ' + bank.total + ' 题　' +
      TYPES.map(function (t) {
        return t.label + ' ' + (bankCounts[t.label] || 0);
      }).join('　');

    // 题库换了，按比例/顺序的默认值要跟着重算
    ensureModeDefaults();
  }

  /** 难度的题量分布（考点数量由 renderKnowledgeSummary 负责展示）。 */
  function renderAvailability(bank) {
    var diffNode = App.dom.byId('difficultyAvail');
    if (!diffNode) return;
    var counts = bank.difficulty_counts || {};
    diffNode.textContent = difficultyValues.length
      ? '题库中各难度题量：' + difficultyValues.map(function (v) {
          var n = counts[v];
          return v + ' ' + (n === undefined ? '?' : n);
        }).join('　')
      : '';
  }

  /** 是否要出答题卡（Word 或 PDF 任一勾选即算）。 */
  function cardRequested() {
    var docx = App.dom.byId('exportCardDocx');
    var pdf = App.dom.byId('exportCard');
    return !!((docx && docx.checked) || (pdf && pdf.checked));
  }

  /** 卸掉当前题库，回到「还没选题库」的状态。
   *
   * 用于换科目出卷：上一个题库的题量、考点、难度都会残留，
   * 不重置的话换个题库后看到的还是旧数字。
   */
  function resetBank() {
    difficultyValues = [];
    knowledgeValues = [];
    knowledgeCounts = {};
    difficultyWeights = {};
    knowledgeInclude = [];
    bankCounts = {};
    bankLoaded = false;

    App.dom.byId('filterGroup').hidden = true;
    App.dom.byId('difficultyGroup').hidden = true;
    App.dom.byId('knowledgeGroup').hidden = true;

    TYPES.forEach(function (type) {
      var row = rows[type.key];
      if (!row) return;
      row.on = !!type.default;
      row.count = '';
      row.ratio = '';
      row.start = '';
      row.end = '';
    });

    renderChips();
    renderTypes();
    updateModeHint();
  }

  /**
   * 切换导出模式时补默认值。
   *
   * 「按比例导出」若全部留空 / 为 0，用户会以为功能坏了（预览直接报错），
   * 所以进入该模式时自动填一组常见比例。
   * 「顺序导出」同理预填 1..该题型题量。
   */
  function ensureModeDefaults() {
    var mode = App.dom.byId('exportMode').value;
    var active = order.filter(function (key) {
      return rows[key] && rows[key].on;
    });
    if (!active.length) return;

    if (mode === '按比例导出') {
      var anySet = active.some(function (key) { return Number(rows[key].ratio) > 0; });
      if (anySet) return;
      // 按 2:2:1 的权重凑满 100：两个题型时是 50/50，三个时是 40/40/20。
      // 留空或全 0 会让预览直接报错，用户会以为功能坏了。
      var weights = [2, 2, 1];
      var totalWeight = active.reduce(function (sum, key, index) {
        return sum + (weights[index] !== undefined ? weights[index] : 1);
      }, 0);

      var assigned = 0;
      active.forEach(function (key, index) {
        if (index === active.length - 1) {
          rows[key].ratio = String(100 - assigned);   // 末项吃掉舍入余数
          return;
        }
        var w = weights[index] !== undefined ? weights[index] : 1;
        var share = Math.round((w / totalWeight) * 100);
        rows[key].ratio = String(share);
        assigned += share;
      });
      return;
    }

    if (mode === '顺序导出') {
      active.forEach(function (key) {
        var row = rows[key];
        if (Number(row.start) > 0 && Number(row.end) > 0) return;
        var type = TYPES.filter(function (t) { return t.key === key; })[0];
        var available = (type && bankCounts[type.label]) || 0;
        if (available > 0) {
          row.start = '1';
          row.end = String(available);
        }
      });
    }
  }

  function renderChips() {
    renderDifficulty();
    renderKnowledge();
  }

  function renderDifficulty() {
    var box = App.dom.byId('difficultyList');
    App.dom.clear(box);
    difficultyValues.forEach(function (value) {
      box.appendChild(chip(value, difficultyWeights[value] || '', function (v) {
        if (v === '') delete difficultyWeights[value];
        else difficultyWeights[value] = Number(v);
      }));
    });
  }

  /**
   * 考点列表。
   *
   * 题库大时考点可能有几百上千个，所以：
   *   ① 按题量降序 —— 题多的考点更可能要被选中，排前面
   *   ② 已选中的永远置顶常显，且不受搜索过滤影响
   *      （否则搜别的词时就看不到自己已经选了什么）
   *   ③ 超出上限的折叠起来，靠搜索框找
   */
  function renderKnowledge() {
    var box = App.dom.byId('knowledgeList');
    var search = App.dom.byId('knowledgeSearch');
    App.dom.clear(box);

    var total = knowledgeValues.length;
    var needSearch = total > KNOWLEDGE_SEARCH_THRESHOLD;
    if (search) {
      search.hidden = !needSearch;
      if (!needSearch) search.value = '';
    }

    var keyword = needSearch ? (search.value || '').trim().toLowerCase() : '';

    var selected = knowledgeInclude.filter(function (v) {
      return knowledgeValues.indexOf(v) !== -1;
    });

    var rest = knowledgeValues
      .filter(function (v) { return selected.indexOf(v) === -1; })
      .filter(function (v) {
        return !keyword || v.toLowerCase().indexOf(keyword) !== -1;
      })
      .sort(function (a, b) {
        return (knowledgeCounts[b] || 0) - (knowledgeCounts[a] || 0);
      });

    var shown = keyword ? rest : rest.slice(0, KNOWLEDGE_PREVIEW_LIMIT);
    var hiddenCount = rest.length - shown.length;

    selected.forEach(function (v) { box.appendChild(knowledgeItem(v, true)); });
    shown.forEach(function (v) { box.appendChild(knowledgeItem(v, false)); });

    if (hiddenCount > 0) {
      var more = App.dom.make(
        'span', 'chip-list__more',
        '另有 ' + hiddenCount + ' 个考点未列出，用上方搜索框查找'
      );
      box.appendChild(more);
    }

    renderKnowledgeSummary(total, selected.length);
  }

  function knowledgeItem(value, isSelected) {
    var count = knowledgeCounts[value];
    var label = count === undefined ? value : value + '（' + count + '）';
    var node = toggle(label, isSelected, function (on) {
      var at = knowledgeInclude.indexOf(value);
      if (on && at === -1) knowledgeInclude.push(value);
      if (!on && at !== -1) knowledgeInclude.splice(at, 1);
      renderKnowledge();
      schedulePreview();
    });
    if (isSelected) node.classList.add('check--selected');
    return node;
  }

  function renderKnowledgeSummary(total, selectedCount) {
    var node = App.dom.byId('knowledgeSelected');
    if (node) {
      node.textContent = selectedCount
        ? '已选 ' + selectedCount + ' 个考点'
        : '未选择（不限知识点）';
    }
    var clearBtn = App.dom.byId('knowledgeClear');
    if (clearBtn) clearBtn.hidden = selectedCount === 0;

    var avail = App.dom.byId('knowledgeAvail');
    if (avail) {
      avail.textContent = total ? '题库中共 ' + total + ' 个考点' : '';
    }
  }

  function chip(label, value, onChange) {
    var wrap = App.dom.make('label', 'check');
    wrap.appendChild(App.dom.make('span', '', label));
    var input = App.dom.make('input', 'input');
    input.type = 'text';
    input.inputMode = 'numeric';
    input.style.width = '52px';
    input.style.flex = 'none';
    input.value = value;
    input.addEventListener('input', function () { onChange(input.value.trim()); });
    wrap.appendChild(input);
    return wrap;
  }

  function toggle(label, checked, onChange) {
    var wrap = App.dom.make('label', 'check');
    var input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = checked;
    input.addEventListener('change', function () { onChange(input.checked); });
    wrap.appendChild(input);
    wrap.appendChild(App.dom.make('span', '', label));
    return wrap;
  }

  /* ── 题型行 ───────────────────────────────────────────────────── */

  function renderTypes() {
    var mode = App.dom.byId('exportMode').value;
    var box = App.dom.byId('typeList');
    App.dom.clear(box);

    order.forEach(function (key, index) {
      var type = TYPES.filter(function (t) { return t.key === key; })[0];
      if (!type) return;
      var row = rows[key];

      var el = App.dom.make('div', 'type-row');

      var on = document.createElement('input');
      on.type = 'checkbox';
      on.checked = row.on;
      on.setAttribute('aria-label', type.label + ' 参与组卷');
      on.addEventListener('change', function () {
        row.on = on.checked;
        updateModeHint();
        schedulePreview();
      });
      el.appendChild(on);

      el.appendChild(App.dom.make('span', 'type-row__label', type.label));

      if (mode === '按比例导出') {
        el.appendChild(numberInput(row.ratio, 'type-row__num', '比例', function (v) {
          row.ratio = v; schedulePreview();
        }));
        el.appendChild(App.dom.make('span', 'type-row__unit', '%'));
      } else if (mode === '顺序导出') {
        el.appendChild(numberInput(row.start, 'type-row__num', '起始题号', function (v) {
          row.start = v; schedulePreview();
        }));
        el.appendChild(App.dom.make('span', 'type-row__unit', '–'));
        el.appendChild(numberInput(row.end, 'type-row__num', '结束题号', function (v) {
          row.end = v; schedulePreview();
        }));
        el.appendChild(App.dom.make('span', 'type-row__unit', '题'));
      } else {
        el.appendChild(numberInput(row.count, 'type-row__num', '数量', function (v) {
          row.count = v; schedulePreview();
        }));
        el.appendChild(App.dom.make('span', 'type-row__unit', '题'));
      }

      el.appendChild(App.dom.make('span', 'type-row__unit', '每题'));
      el.appendChild(numberInput(row.score, 'type-row__score', '每题分值', function (v) {
        row.score = v; schedulePreview();
      }));
      el.appendChild(App.dom.make('span', 'type-row__unit', '分'));

      var orderBox = App.dom.make('div', 'type-row__order');
      orderBox.appendChild(moveButton('↑', index, -1, '上移 ' + type.label));
      orderBox.appendChild(moveButton('↓', index, 1, '下移 ' + type.label));
      el.appendChild(orderBox);

      box.appendChild(el);
    });

    updateModeHint();
  }

  function numberInput(value, className, label, onChange) {
    var input = App.dom.make('input', 'input ' + className);
    input.type = 'text';
    input.inputMode = 'numeric';
    input.value = value;
    input.setAttribute('aria-label', label);
    input.addEventListener('input', function () { onChange(input.value.trim()); });
    return input;
  }

  function moveButton(text, index, delta, label) {
    var btn = App.dom.make('button', 'move-btn', text);
    btn.type = 'button';
    btn.setAttribute('aria-label', label);
    btn.title = label;
    btn.disabled = (index + delta < 0 || index + delta >= order.length);
    btn.addEventListener('click', function () {
      var target = index + delta;
      var moved = order.splice(index, 1)[0];
      order.splice(target, 0, moved);
      renderTypes();
      schedulePreview();
    });
    return btn;
  }

  function updateModeHint() {
    var mode = App.dom.byId('exportMode').value;
    var hints = {
      '随机抽取': '从题库中随机抽取指定数量的题目。',
      '按比例导出': '按各题型填写的百分比分配题数（合计不必等于 100，会自动归一化）。',
      '顺序导出': '按题型内的题号范围选取；此时「数量」不参与，题数由范围决定。'
    };
    App.dom.byId('modeHint').textContent = hints[mode] || '';
    App.dom.byId('ratioRow').hidden = mode !== '按比例导出';
  }

  /* ── 预览防抖 ─────────────────────────────────────────────────── */

  var previewTimer = null;

  function schedulePreview() {
    if (!App.preview || !App.preview.isAuto()) return;
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      previewTimer = null;
      App.preview.refresh().catch(function () { /* 自动刷新静默失败 */ });
    }, 400);
  }

  /* ── 读写配置 ─────────────────────────────────────────────────── */

  function read() {
    var cfg = {
      export_mode: App.dom.byId('exportMode').value,
      exam_title: App.dom.byId('examTitle').value,
      student_name: App.dom.byId('studentName').value,
      exam_time: App.dom.byId('examTime').value.trim(),
      paper_size: App.dom.byId('paperSize').value,
      header_text: App.dom.byId('headerText').value.trim(),
      include_answers: App.dom.byId('includeAnswers').checked,
      random_order: App.dom.byId('randomOrder').checked,
      unique_across_papers: App.dom.byId('uniqueAcrossPapers').checked,
      avoid_history: App.dom.byId('avoidHistory').checked,
      on_pool_exhausted: App.dom.byId('onPoolExhausted').value,
      total_questions: App.dom.byId('totalQuestions').value,
      // 出了答题卡，试卷上就不留作答横线 —— 学生写在卡上。
      // 预览要据此重新排版，所以这个开关必须跟着配置一起传。
      include_answer_card: cardRequested(),
      question_order: order.slice(),
      difficulty_weights: Object.assign({}, difficultyWeights),
      knowledge_include: knowledgeInclude.slice()
    };

    TYPES.forEach(function (type) {
      var row = rows[type.key];
      cfg['include_' + type.key] = row.on;
      cfg[type.key + '_count'] = row.count;
      cfg[type.key + '_score'] = row.score;
      cfg[type.key + '_ratio'] = row.ratio;
      cfg[type.key + '_start'] = row.start;
      cfg[type.key + '_end'] = row.end;
    });

    return cfg;
  }

  function write(cfg) {
    if (!cfg) return;
    var set = function (id, value) {
      var node = App.dom.byId(id);
      if (node && value !== undefined && value !== null) node.value = value;
    };

    set('examTitle', cfg.exam_title);
    set('studentName', cfg.student_name);
    set('examTime', cfg.exam_time);
    set('paperSize', cfg.paper_size);
    set('headerText', cfg.header_text);
    set('exportMode', cfg.export_mode);
    set('totalQuestions', cfg.total_questions);
    set('onPoolExhausted', cfg.on_pool_exhausted);

    var check = function (id, value) {
      var node = App.dom.byId(id);
      if (node && value !== undefined) node.checked = !!value;
    };
    check('includeAnswers', cfg.include_answers);
    check('randomOrder', cfg.random_order);
    check('uniqueAcrossPapers', cfg.unique_across_papers);
    check('avoidHistory', cfg.avoid_history);

    if (cfg.question_order && cfg.question_order.length) {
      var known = cfg.question_order.filter(function (k) { return rows[k]; });
      var rest = order.filter(function (k) { return known.indexOf(k) === -1; });
      order = known.concat(rest);
    }

    TYPES.forEach(function (type) {
      var row = rows[type.key];
      if (!row) return;
      row.on = !!cfg['include_' + type.key];
      if (cfg[type.key + '_count'] !== undefined) row.count = String(cfg[type.key + '_count'] || '');
      if (cfg[type.key + '_score'] !== undefined) row.score = String(cfg[type.key + '_score'] || type.score);
      if (cfg[type.key + '_ratio'] !== undefined) row.ratio = String(cfg[type.key + '_ratio'] || '');
      if (cfg[type.key + '_start'] !== undefined) row.start = String(cfg[type.key + '_start'] || '');
      if (cfg[type.key + '_end'] !== undefined) row.end = String(cfg[type.key + '_end'] || '');
    });

    difficultyWeights = Object.assign({}, cfg.difficulty_weights || {});
    knowledgeInclude = (cfg.knowledge_include || []).slice();
    renderChips();
    renderTypes();
  }

  return {
    init: init,
    applyBankInfo: applyBankInfo,
    resetBank: resetBank,
    cardRequested: cardRequested,
    renderTypes: renderTypes,
    renderKnowledge: renderKnowledge,
    updateModeHint: updateModeHint,
    ensureModeDefaults: ensureModeDefaults,
    read: read,
    write: write,
    schedulePreview: schedulePreview,
    order: function () { return order.slice(); }
  };
})();
