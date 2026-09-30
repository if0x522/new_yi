// 《周易》现代转译 · 客户端检索（即时过滤：卡片墙 + 全文结果）
(function () {
  'use strict';
  var qInput = document.getElementById('q');
  var cardsWrap = document.getElementById('cards');
  var cardsEmpty = document.getElementById('cards-empty');
  var resultsWrap = document.getElementById('results');
  var statusEl = document.getElementById('search-status');
  var INDEX = window.SEARCH_INDEX || [];
  var activeTag = '';
  var MAX_RESULTS = 30;

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function highlight(text, q) {
    if (!q) return esc(text);
    var lower = text.toLowerCase();
    var needle = q.toLowerCase();
    var out = '';
    var i = 0;
    while (true) {
      var hit = lower.indexOf(needle, i);
      if (hit === -1) { out += esc(text.slice(i)); break; }
      out += esc(text.slice(i, hit)) + '<mark>' + esc(text.slice(hit, hit + q.length)) + '</mark>';
      i = hit + q.length;
    }
    return out;
  }

  function applyCards(q) {
    if (!cardsWrap) return;
    var cards = cardsWrap.querySelectorAll('.card');
    var shown = 0;
    var lq = q.toLowerCase();
    for (var i = 0; i < cards.length; i++) {
      var el = cards[i];
      var text = el.getAttribute('data-text') || '';
      var tags = el.getAttribute('data-tags') || '';
      var okQ = !lq || text.indexOf(lq) !== -1;
      var okTag = !activeTag || tags.indexOf(activeTag) !== -1;
      var show = okQ && okTag;
      el.style.display = show ? '' : 'none';
      if (show) shown++;
    }
    if (cardsEmpty) cardsEmpty.hidden = shown !== 0;
    return shown;
  }

  function snippetFor(entry, q) {
    var text = entry.text || '';
    var lower = text.toLowerCase();
    var hit = q ? lower.indexOf(q.toLowerCase()) : -1;
    if (hit === -1) {
      return text.slice(0, 120) + (text.length > 120 ? '......' : '');
    }
    var start = Math.max(0, hit - 45);
    var end = Math.min(text.length, hit + q.length + 85);
    return (start > 0 ? '......' : '') + text.slice(start, end) +
      (end < text.length ? '......' : '');
  }

  function applyResults(q) {
    if (!resultsWrap) return;
    if (!q) {
      resultsWrap.innerHTML = '<p class="empty-state">上方输入关键词，这里显示命中的页面、片段与跳转。</p>';
      return 0;
    }
    var lq = q.toLowerCase();
    var hits = [];
    for (var i = 0; i < INDEX.length; i++) {
      var e = INDEX[i];
      var hay = ((e.title || '') + ' ' + (e.keywords || '') + ' ' + (e.text || '')).toLowerCase();
      if (hay.indexOf(lq) !== -1) hits.push(e);
      if (hits.length >= 200) break;
    }
    if (!hits.length) {
      resultsWrap.innerHTML = '<p class="empty-state">未命中——试试「消长」「艰难」「信任」等主题词</p>';
      return 0;
    }
    var htmlParts = [];
    for (var j = 0; j < Math.min(hits.length, MAX_RESULTS); j++) {
      var en = hits[j];
      htmlParts.push(
        '<article class="result-item">' +
        '<h3 class="result-title"><a href="' + esc(en.url) + '">' + highlight(en.title, q) + '</a></h3>' +
        '<p class="result-snippet">' + highlight(snippetFor(en, q), q) + '</p>' +
        '</article>');
    }
    resultsWrap.innerHTML = htmlParts.join('');
    return hits.length;
  }

  function run() {
    var q = qInput ? qInput.value.trim() : '';
    var nCards = applyCards(q);
    var nResults = applyResults(q);
    if (statusEl) {
      if (!q && !activeTag) {
        statusEl.textContent = '';
      } else {
        var parts = [];
        if (q) parts.push('「' + q + '」');
        if (activeTag) parts.push('主题簇「' + activeTag + '」');
        statusEl.innerHTML = parts.join(' × ') + ' -- 卡片命中 <strong>' + nCards +
          '</strong> 卦 · 全文命中 <strong>' + nResults + '</strong> 页';
      }
    }
  }

  if (qInput) {
    qInput.addEventListener('input', run);
    qInput.addEventListener('search', run);
    var params = new URLSearchParams(window.location.search);
    var q0 = params.get('q');
    var tag0 = params.get('tag');
    if (q0) qInput.value = q0;
    if (tag0) {
      activeTag = tag0;
      var chips = document.querySelectorAll('.cluster-chip');
      for (var k = 0; k < chips.length; k++) {
        if (chips[k].getAttribute('data-tag') === tag0) chips[k].classList.add('active');
      }
    }
    run();
    if (q0) {
      var sec = document.getElementById('search');
      if (sec) sec.scrollIntoView({ block: 'start' });
    }
  }

  var chips = document.querySelectorAll('.cluster-chip');
  for (var c = 0; c < chips.length; c++) {
    chips[c].addEventListener('click', function (ev) {
      var tag = ev.currentTarget.getAttribute('data-tag');
      if (activeTag === tag) {
        activeTag = '';
        ev.currentTarget.classList.remove('active');
      } else {
        activeTag = tag;
        for (var m = 0; m < chips.length; m++) chips[m].classList.remove('active');
        ev.currentTarget.classList.add('active');
      }
      var wall = document.getElementById('hexagrams');
      if (wall) wall.scrollIntoView({ behavior: 'smooth', block: 'start' });
      run();
    });
  }
})();
