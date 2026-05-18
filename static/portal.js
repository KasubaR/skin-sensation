(function () {
  'use strict';

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function initCancelConfirm() {
    document.querySelectorAll('[data-portal-cancel]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        if (!window.confirm('Are you sure you want to cancel this appointment?')) {
          event.preventDefault();
        }
      });
    });
  }

  function initPrintReceipt() {
    if (document.body.dataset.printOnLoad !== undefined) {
      window.addEventListener('load', function () {
        window.print();
      });
    }

    document.querySelectorAll('[data-action="print-receipt"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        window.print();
      });
    });
  }

  function initReschedule() {
    var root = document.querySelector('[data-portal-reschedule]');
    if (!root) return;

    var availabilityUrl = root.dataset.availabilityUrl;
    var serviceIds = root.dataset.serviceIds;
    var staffId = root.dataset.staffId || 'any';
    var excludeId = root.dataset.excludeId;
    var dateInput = document.getElementById('reschedule-date');
    var slotsContainer = root.querySelector('[data-portal-slots]');
    var timeInput = document.getElementById('reschedule-time');
    var staffInput = document.getElementById('reschedule-staff');
    var submitBtn = root.querySelector('[data-portal-submit]');

    if (!dateInput || !slotsContainer || !timeInput) return;

    var selectedBtn = null;

    function clearSelection() {
      if (selectedBtn) {
        selectedBtn.classList.remove('is-selected');
        selectedBtn = null;
      }
      timeInput.value = '';
      if (submitBtn) submitBtn.disabled = true;
    }

    function selectSlot(btn, start, staff) {
      clearSelection();
      selectedBtn = btn;
      btn.classList.add('is-selected');
      timeInput.value = start;
      if (staffInput && staff) {
        staffInput.value = staff;
      }
      if (submitBtn) submitBtn.disabled = false;
    }

    function renderSlots(slots) {
      slotsContainer.innerHTML = '';
      if (!slots.length) {
        slotsContainer.innerHTML = '<p class="portal-slots__hint">No times available on this date.</p>';
        return;
      }

      slots.forEach(function (slot) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'portal-slot-btn';
        btn.textContent = slot.start;
        btn.dataset.start = slot.start;
        btn.dataset.staffId = slot.staff_id;
        btn.addEventListener('click', function () {
          selectSlot(btn, slot.start, String(slot.staff_id));
        });
        slotsContainer.appendChild(btn);
      });
    }

    function loadSlots() {
      clearSelection();
      var date = dateInput.value;
      if (!date) {
        slotsContainer.innerHTML = '<p class="portal-slots__hint">Select a date to see available times.</p>';
        return;
      }

      slotsContainer.innerHTML = '<p class="portal-slots__hint">Loading times…</p>';

      var params = new URLSearchParams({
        date: date,
        service_ids: serviceIds,
        staff_id: staffId,
        exclude_appointment_id: excludeId,
      });

      fetch(availabilityUrl + '?' + params.toString(), {
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': getCsrfToken() },
      })
        .then(function (res) {
          return res.json().then(function (data) {
            if (!res.ok) throw new Error(data.error || 'Could not load times.');
            return data;
          });
        })
        .then(function (data) {
          renderSlots(data.slots || []);
        })
        .catch(function (err) {
          slotsContainer.innerHTML =
            '<p class="portal-slots__hint">' + (err.message || 'Could not load times.') + '</p>';
        });
    }

    dateInput.addEventListener('change', loadSlots);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initCancelConfirm();
    initPrintReceipt();
    initReschedule();
  });
})();
