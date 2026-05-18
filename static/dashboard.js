(function () {
  'use strict';

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function escapeHtml(s) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function pad(n) {
    return n < 10 ? '0' + n : String(n);
  }

  function formatDateKey(d) {
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }

  function monthRange(year, month) {
    var start = new Date(year, month, 1);
    var end = new Date(year, month + 1, 0);
    return { start: formatDateKey(start), end: formatDateKey(end) };
  }

  function buildFilterQuery(form) {
    if (!form) return '';
    var params = new URLSearchParams(new FormData(form));
    var parts = [];
    params.forEach(function (value, key) {
      if (value) parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(value));
    });
    return parts.length ? '&' + parts.join('&') : '';
  }

  function renderCalendar(container, year, month, events) {
    var first = new Date(year, month, 1);
    var startPad = first.getDay();
    var daysInMonth = new Date(year, month + 1, 0).getDate();
    var eventsByDay = {};
    events.forEach(function (ev) {
      var dayKey = ev.start.slice(0, 10);
      if (!eventsByDay[dayKey]) eventsByDay[dayKey] = [];
      eventsByDay[dayKey].push(ev);
    });

    var weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    var html = '<div class="dash-cal-header">';
    html += '<button type="button" class="dash-btn dash-btn--secondary" data-cal-prev aria-label="Previous month">←</button>';
    html += '<strong>' + first.toLocaleString('en-GB', { month: 'long', year: 'numeric' }) + '</strong>';
    html += '<button type="button" class="dash-btn dash-btn--secondary" data-cal-next aria-label="Next month">→</button>';
    html += '</div>';
    html += '<div class="dash-cal-grid">';
    weekdays.forEach(function (w) {
      html += '<div class="dash-cal-weekday">' + w + '</div>';
    });

    var totalCells = Math.ceil((startPad + daysInMonth) / 7) * 7;
    for (var i = 0; i < totalCells; i++) {
      var dayNum = i - startPad + 1;
      var cellClass = 'dash-cal-day';
      var inner = '';
      if (dayNum < 1 || dayNum > daysInMonth) {
        cellClass += ' dash-cal-day--other';
        inner = '<span class="dash-cal-day__num"></span>';
      } else {
        var d = new Date(year, month, dayNum);
        var key = formatDateKey(d);
        inner = '<span class="dash-cal-day__num">' + dayNum + '</span>';
        (eventsByDay[key] || []).forEach(function (ev) {
          var statusClass = (ev.status || 'pending').toLowerCase();
          inner +=
            '<a class="dash-cal-event dash-cal-event--' +
            statusClass +
            '" href="' +
            ev.url +
            '" title="' +
            escapeHtml(ev.title) +
            '">' +
            escapeHtml(ev.title) +
            '</a>';
        });
      }
      html += '<div class="' + cellClass + '">' + inner + '</div>';
    }
    html += '</div>';
    container.innerHTML = html;

    container.querySelector('[data-cal-prev]').addEventListener('click', function () {
      var m = month - 1;
      var y = year;
      if (m < 0) {
        m = 11;
        y -= 1;
      }
      loadMonth(container, y, m);
    });
    container.querySelector('[data-cal-next]').addEventListener('click', function () {
      var m = month + 1;
      var y = year;
      if (m > 11) {
        m = 0;
        y += 1;
      }
      loadMonth(container, y, m);
    });
  }

  function loadMonth(container, year, month) {
    var apiUrl = container.dataset.apiUrl;
    var filterForm = document.getElementById('dashCalendarFilters');
    var range = monthRange(year, month);
    var url =
      apiUrl + '?start=' + range.start + '&end=' + range.end + buildFilterQuery(filterForm);
    container.dataset.year = year;
    container.dataset.month = month;
    fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'X-CSRFToken': getCsrfToken() },
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (events) {
        renderCalendar(container, year, month, events);
      })
      .catch(function () {
        container.innerHTML = '<p class="dash-empty">Could not load calendar.</p>';
      });
  }

  window.DashCalendar = {
    init: function () {
      var el = document.getElementById('dashCalendar');
      if (!el) return;
      var now = new Date();
      loadMonth(el, now.getFullYear(), now.getMonth());
      var filterForm = document.getElementById('dashCalendarFilters');
      if (filterForm) {
        filterForm.addEventListener('submit', function (e) {
          e.preventDefault();
          var y = parseInt(el.dataset.year, 10);
          var m = parseInt(el.dataset.month, 10);
          loadMonth(el, y, m);
        });
      }
    },
  };
})();
