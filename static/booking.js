/**
 * Skin Sensation — booking flow (API-backed).
 * Do not log raw customer PII.
 */

let catalogCache = [];
let staffCache = [];
let apiConfig = {};
let calcTimer = null;
let calcAbortController = null;

function pad2(n) {
  return String(n).padStart(2, '0');
}

function toDateKey(d) {
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
}

function parseDateKey(key) {
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function formatMoney(amount) {
  const n = typeof amount === 'string' ? parseFloat(amount) : amount;
  return 'K' + Math.round(n).toLocaleString('en-ZM', { maximumFractionDigits: 0 });
}

function formatDuration(totalMinutes) {
  if (totalMinutes < 60) return totalMinutes + ' min';
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  if (m === 0) return h + ' hr' + (h > 1 ? 's' : '');
  return h + ' hr ' + m + ' min';
}

function formatTimeLabel(value) {
  const [hStr, mStr] = value.split(':');
  const h = parseInt(hStr, 10);
  const min = mStr || '00';
  return (h % 12 || 12) + ':' + min + (h >= 12 ? ' PM' : ' AM');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function getApiConfig(root) {
  return {
    catalogUrl: root.dataset.catalogUrl,
    staffUrl: root.dataset.staffUrl,
    availabilityUrl: root.dataset.availabilityUrl,
    calculateUrl: root.dataset.calculateUrl,
    appointmentsUrl: root.dataset.appointmentsUrl,
    csrfToken: root.dataset.csrfToken,
  };
}

function getSelectedServiceIds() {
  return Array.from(document.querySelectorAll('input[name="booking_service"]:checked')).map(
    (i) => parseInt(i.value, 10)
  );
}

function getSelectedServices() {
  const ids = getSelectedServiceIds();
  return catalogCache.filter((s) => ids.includes(s.id));
}

async function fetchCatalog() {
  const inline = document.getElementById('bookingCatalogData');
  if (inline) {
    catalogCache = JSON.parse(inline.textContent);
  } else {
    const res = await fetch(apiConfig.catalogUrl, { headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error('Could not load services.');
    catalogCache = await res.json();
  }
  catalogCache.forEach((s) => {
    s.price = parseFloat(s.price);
    s.duration = s.duration_minutes;
  });
  return catalogCache;
}

async function fetchCalculate(serviceIds) {
  if (!serviceIds.length) return null;
  if (calcAbortController) calcAbortController.abort();
  calcAbortController = new AbortController();
  const url = apiConfig.calculateUrl + '?service_ids=' + serviceIds.join(',');
  try {
    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: calcAbortController.signal,
    });
    if (!res.ok) return null;
    return res.json();
  } catch (e) {
    if (e.name === 'AbortError') return null;
    throw e;
  }
}

function debouncedUpdateSummary(state, delay = 300) {
  clearTimeout(calcTimer);
  calcTimer = setTimeout(() => updateSummary(state), delay);
}

async function fetchStaff(serviceIds) {
  if (!serviceIds.length) {
    staffCache = [{ id: 'any', display_name: 'Any available', specialization: 'Fastest match' }];
    return staffCache;
  }
  const url = apiConfig.staffUrl + '?service_ids=' + serviceIds.join(',');
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error('Could not load therapists.');
  staffCache = await res.json();
  return staffCache;
}

function renderStaffGrid(selectedStaffId) {
  const grid = document.getElementById('bookingStaffGrid');
  if (!grid) return;

  if (!staffCache.length) {
    grid.innerHTML = '<p class="booking-summary-empty">No therapists available for the selected services.</p>';
    return;
  }

  grid.innerHTML = staffCache
    .map((staff) => {
      const id = String(staff.id);
      const checked = String(selectedStaffId) === id || (!selectedStaffId && id === 'any');
      const avatar = staff.image_url
        ? '<img src="' + escapeHtml(staff.image_url) + '" alt="">'
        : '<i class="fa-solid ' + (id === 'any' ? 'fa-user-group' : 'fa-user') + '" aria-hidden="true"></i>';
      return (
        '<label class="booking-staff-card">' +
        '<input type="radio" name="booking_staff" value="' +
        escapeHtml(id) +
        '"' +
        (checked ? ' checked' : '') +
        '>' +
        '<div class="booking-staff-avatar" aria-hidden="true">' +
        avatar +
        '</div>' +
        '<div class="booking-staff-name">' +
        escapeHtml(staff.display_name) +
        '</div>' +
        '<div class="booking-staff-role">' +
        escapeHtml(staff.specialization || '') +
        '</div>' +
        '</label>'
      );
    })
    .join('');

  grid.querySelectorAll('input[name="booking_staff"]').forEach((input) => {
    input.addEventListener('change', () => {
      if (typeof window.__bookingOnStaffChange === 'function') {
        window.__bookingOnStaffChange();
      }
    });
  });
}

async function fetchAvailability(dateKey, serviceIds, staffId) {
  const params = new URLSearchParams({
    date: dateKey,
    service_ids: serviceIds.join(','),
    staff_id: staffId || 'any',
  });
  const res = await fetch(apiConfig.availabilityUrl + '?' + params.toString(), {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || 'Could not load availability.');
  }
  return res.json();
}

function renderTimeSlots(container, slots, state) {
  if (!container) return;
  container.innerHTML = '';

  if (!slots || slots.length === 0) {
    container.innerHTML =
      '<div class="booking-slots-empty"><i class="fa-solid fa-calendar-xmark" aria-hidden="true"></i><p>No slots available that day. Please choose another date.</p></div>';
    return;
  }

  const groups = [
    { label: 'Morning', icon: 'fa-sun', range: [9, 12] },
    { label: 'Afternoon', icon: 'fa-cloud-sun', range: [12, 15] },
    { label: 'Late Afternoon', icon: 'fa-cloud', range: [15, 19] },
  ];

  groups.forEach((group) => {
    const groupSlots = slots.filter((s) => {
      const h = parseInt(s.start.split(':')[0], 10);
      return h >= group.range[0] && h < group.range[1];
    });
    if (groupSlots.length === 0) return;

    const groupEl = document.createElement('div');
    groupEl.className = 'booking-slot-group';
    groupEl.innerHTML =
      '<p class="booking-slot-group-label"><i class="fa-solid ' +
      group.icon +
      '" aria-hidden="true"></i> ' +
      group.label +
      '</p>';
    const grid = document.createElement('div');
    grid.className = 'booking-slot-group-grid';

    groupSlots.forEach((slot) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'booking-time-slot';
      btn.dataset.timeValue = slot.start;
      btn.dataset.staffId = String(slot.staff_id);
      btn.dataset.staffName = slot.staff_name || '';
      btn.innerHTML = '<span class="slot-time">' + formatTimeLabel(slot.start) + '</span>';
      grid.appendChild(btn);
    });

    groupEl.appendChild(grid);
    container.appendChild(groupEl);
  });

  container.querySelectorAll('.booking-time-slot').forEach((btn) => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('.booking-time-slot').forEach((b) => b.classList.remove('is-selected'));
      btn.classList.add('is-selected');
      const timeInput = document.getElementById('bookingTime');
      const staffResolved = document.getElementById('bookingStaffResolved');
      if (timeInput) timeInput.value = btn.dataset.timeValue;
      if (staffResolved) staffResolved.value = btn.dataset.staffId;
      state.selectedStaffName = btn.dataset.staffName;
      if (typeof window.__bookingOnSlotChange === 'function') {
        window.__bookingOnSlotChange();
      }
    });
  });
}

async function updateSummary(state) {
  const services = getSelectedServices();
  const serviceIds = getSelectedServiceIds();
  const staffInput = document.querySelector('input[name="booking_staff"]:checked');
  const staffId = staffInput ? staffInput.value : 'any';
  const staff = staffCache.find((s) => String(s.id) === staffId) || {
    display_name: 'Any available',
  };

  const dateInput = document.getElementById('bookingDate');
  const dateVal = dateInput ? dateInput.value : '';
  const timeInput = document.getElementById('bookingTime');
  const timeVal = timeInput ? timeInput.value : '';

  let totals = {
    price: 0,
    duration: 0,
    buffer: 0,
    appointmentMinutes: 0,
    deposit: 0,
  };

  if (serviceIds.length) {
    const calc = await fetchCalculate(serviceIds);
    if (calc) {
      totals = {
        price: parseFloat(calc.total_price),
        duration: calc.total_duration,
        buffer: calc.buffer_minutes,
        appointmentMinutes: calc.appointment_minutes,
        deposit: parseFloat(calc.deposit_amount),
      };
    } else {
      services.forEach((s) => {
        totals.price += s.price;
        totals.duration += s.duration;
      });
      totals.buffer = 15;
      totals.appointmentMinutes = totals.duration + totals.buffer;
      totals.deposit = Math.max(50, Math.round(totals.price * 0.2));
    }
  }

  const elServices = document.getElementById('summaryServices');
  const elDuration = document.getElementById('summaryDuration');
  const elBuffer = document.getElementById('summaryBuffer');
  const elSubtotal = document.getElementById('summarySubtotal');
  const elDeposit = document.getElementById('summaryDeposit');
  const elTotal = document.getElementById('summaryTotal');
  const elStaff = document.getElementById('summaryStaff');
  const elSchedule = document.getElementById('summarySchedule');

  if (elServices) {
    elServices.innerHTML = services.length
      ? services
          .map(
            (s) =>
              '<div class="booking-summary-line"><span>' +
              escapeHtml(s.name) +
              '</span><span>' +
              formatMoney(s.price) +
              '</span></div>'
          )
          .join('')
      : '<p class="booking-summary-empty">No services selected yet.</p>';
  }
  if (elDuration) elDuration.textContent = services.length ? formatDuration(totals.duration) : '—';
  if (elBuffer) elBuffer.textContent = services.length ? formatDuration(totals.buffer) + ' buffer' : '—';
  if (elSubtotal) elSubtotal.textContent = services.length ? formatMoney(totals.price) : '—';
  if (elDeposit) elDeposit.textContent = services.length ? formatMoney(totals.deposit) : '—';
  if (elTotal) elTotal.textContent = services.length ? formatMoney(totals.price) : '—';
  if (elStaff) {
    elStaff.textContent = state.selectedStaffName || staff.display_name;
  }

  let scheduleText = '—';
  if (dateVal && timeVal) {
    const d = parseDateKey(dateVal);
    scheduleText =
      d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) +
      ' · ' +
      formatTimeLabel(timeVal);
  } else if (dateVal) {
    scheduleText =
      parseDateKey(dateVal).toLocaleDateString('en-GB', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }) + ' · pick a time';
  }
  if (elSchedule) elSchedule.textContent = scheduleText;

  state.totals = totals;
  state.staff = staff;
  state.services = services;
}

function validateStep(step) {
  const err = document.getElementById('bookingStepError');
  if (err) err.textContent = '';

  if (step === 1) {
    if (getSelectedServiceIds().length === 0) {
      if (err) err.textContent = 'Please select at least one service.';
      return false;
    }
  }
  if (step === 2) {
    if (!document.querySelector('input[name="booking_staff"]:checked')) {
      if (err) err.textContent = 'Please choose a therapist or “Any available”.';
      return false;
    }
  }
  if (step === 3) {
    const dateInput = document.getElementById('bookingDate');
    const timeInput = document.getElementById('bookingTime');
    if (!dateInput || !dateInput.value) {
      if (err) err.textContent = 'Please select a date.';
      return false;
    }
    if (!timeInput || !timeInput.value) {
      if (err) err.textContent = 'Please select an available time slot.';
      return false;
    }
  }
  if (step === 4) {
    const name = document.getElementById('bookingFullName');
    const phone = document.getElementById('bookingPhone');
    const email = document.getElementById('bookingEmail');
    if (!name || !name.value.trim()) {
      if (err) err.textContent = 'Please enter your full name.';
      name && name.focus();
      return false;
    }
    if (!phone || !phone.value.trim()) {
      if (err) err.textContent = 'Please enter your phone number.';
      phone && phone.focus();
      return false;
    }
    const digits = phone.value.replace(/\D/g, '');
    if (digits.length < 9) {
      if (err) err.textContent = 'Please enter a valid phone number (at least 9 digits).';
      phone.focus();
      return false;
    }
    if (email && email.value.trim()) {
      const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());
      if (!ok) {
        if (err) err.textContent = 'Please enter a valid email or leave it blank.';
        email.focus();
        return false;
      }
    }
  }
  if (step === 5) {
    if (!document.querySelector('input[name="booking_payment"]:checked')) {
      if (err) err.textContent = 'Please select a payment option.';
      return false;
    }
  }
  return true;
}

function showStep(root, step) {
  root.querySelectorAll('[data-booking-step]').forEach((panel) => {
    const n = parseInt(panel.getAttribute('data-booking-step'), 10);
    panel.hidden = n !== step;
    panel.classList.toggle('is-active', n === step);
  });
  root.querySelectorAll('[data-progress-step]').forEach((item) => {
    const n = parseInt(item.getAttribute('data-progress-step'), 10);
    item.classList.remove('is-active', 'is-complete');
    if (step === 6) {
      if (n < 6) item.classList.add('is-complete');
      if (n === 6) item.classList.add('is-active');
    } else {
      if (n < step) item.classList.add('is-complete');
      if (n === step) item.classList.add('is-active');
    }
  });
  const err = document.getElementById('bookingStepError');
  if (err) err.textContent = '';
}

const BOOKING_STORAGE_KEY = 'ss_booking_v1';

function saveBookingState(currentStep) {
  try {
    const data = {
      step: currentStep,
      services: getSelectedServiceIds(),
      staff: (document.querySelector('input[name="booking_staff"]:checked') || {}).value || 'any',
      date: (document.getElementById('bookingDate') || {}).value || '',
      time: (document.getElementById('bookingTime') || {}).value || '',
      staffResolved: (document.getElementById('bookingStaffResolved') || {}).value || '',
      name: (document.getElementById('bookingFullName') || {}).value || '',
      phone: (document.getElementById('bookingPhone') || {}).value || '',
      email: (document.getElementById('bookingEmail') || {}).value || '',
      notes: (document.getElementById('bookingNotes') || {}).value || '',
      allergies: (document.getElementById('bookingAllergies') || {}).value || '',
      firstVisit: !!(document.getElementById('bookingFirstVisit') || {}).checked,
      payment: (document.querySelector('input[name="booking_payment"]:checked') || {}).value || 'mobile_money',
    };
    sessionStorage.setItem(BOOKING_STORAGE_KEY, JSON.stringify(data));
  } catch (e) {}
}

function loadBookingState() {
  try {
    return JSON.parse(sessionStorage.getItem(BOOKING_STORAGE_KEY)) || null;
  } catch (e) {
    return null;
  }
}

function clearBookingState() {
  try {
    sessionStorage.removeItem(BOOKING_STORAGE_KEY);
  } catch (e) {}
}

async function submitAppointment(state) {
  const staffInput = document.querySelector('input[name="booking_staff"]:checked');
  const staffResolved = document.getElementById('bookingStaffResolved');
  const payInput = document.querySelector('input[name="booking_payment"]:checked');
  const proofInput = document.getElementById('bookingPaymentProof');
  const hasProof = proofInput && proofInput.files && proofInput.files.length > 0;

  const payload = {
    service_ids: getSelectedServiceIds(),
    staff_id: staffResolved && staffResolved.value ? staffResolved.value : staffInput ? staffInput.value : 'any',
    appointment_date: document.getElementById('bookingDate').value,
    start_time: document.getElementById('bookingTime').value,
    full_name: document.getElementById('bookingFullName').value.trim(),
    phone: document.getElementById('bookingPhone').value.trim(),
    email: (document.getElementById('bookingEmail').value || '').trim(),
    notes: (document.getElementById('bookingNotes').value || '').trim(),
    allergies: (document.getElementById('bookingAllergies').value || '').trim(),
    first_visit: !!(document.getElementById('bookingFirstVisit') || {}).checked,
    payment_method: payInput ? payInput.value : '',
    website: '',
  };

  let fetchOpts;
  if (hasProof) {
    const formData = new FormData();
    formData.append('service_ids', JSON.stringify(payload.service_ids));
    Object.keys(payload).forEach(function (key) {
      if (key === 'service_ids') return;
      formData.append(key, key === 'first_visit' ? (payload[key] ? 'true' : 'false') : payload[key]);
    });
    formData.append('proof_of_payment', proofInput.files[0]);
    fetchOpts = {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'X-CSRFToken': apiConfig.csrfToken,
      },
      credentials: 'same-origin',
      body: formData,
    };
  } else {
    fetchOpts = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRFToken': apiConfig.csrfToken,
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    };
  }

  const res = await fetch(apiConfig.appointmentsUrl, fetchOpts);

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.error || 'Could not complete your booking. Please try again.';
    throw { status: res.status, message: msg };
  }
  return data;
}

function initCategoryFilter() {
  const pills = document.querySelectorAll('.booking-category-pill');
  if (!pills.length) return;

  function applyFilter(selected) {
    document.querySelectorAll('.booking-service-card[data-category]').forEach((card) => {
      card.style.display = card.dataset.category !== selected ? 'none' : '';
    });
  }

  // Activate first pill by default
  pills[0].classList.add('is-active');
  applyFilter(pills[0].dataset.category);

  pills.forEach((pill) => {
    pill.addEventListener('click', () => {
      pills.forEach((p) => p.classList.remove('is-active'));
      pill.classList.add('is-active');
      applyFilter(pill.dataset.category);
    });
  });
}

function initBookingFlow() {
  const root = document.querySelector('[data-booking-root]');
  if (!root) return;

  apiConfig = getApiConfig(root);
  initCategoryFilter();
  const state = { totals: {}, staff: null, services: [], selectedStaffName: '' };
  let currentStep = 1;

  const dateInput = document.getElementById('bookingDate');
  const slotContainer = document.getElementById('bookingTimeSlots');
  const bookingCalendarEl = document.getElementById('bookingCalendar');
  const bookingCalGrid = bookingCalendarEl ? bookingCalendarEl.querySelector('.booking-cal-grid') : null;
  const bookingCalTitle = document.getElementById('bookingCalMonthYear');
  const bookingCalPrev = bookingCalendarEl ? bookingCalendarEl.querySelector('[data-cal-prev]') : null;
  const bookingCalNext = bookingCalendarEl ? bookingCalendarEl.querySelector('[data-cal-next]') : null;
  const dateReadout = document.getElementById('bookingDateReadout');

  const today0 = new Date();
  today0.setHours(0, 0, 0, 0);
  let calendarViewDate = new Date(today0.getFullYear(), today0.getMonth(), 1);

  function getMinMaxDateKeys() {
    const t = new Date();
    t.setHours(0, 0, 0, 0);
    const minK = toDateKey(t);
    const maxK = toDateKey(new Date(t.getFullYear(), t.getMonth() + 3, t.getDate()));
    return { minK, maxK };
  }

  function canGoPrev() {
    const { minK } = getMinMaxDateKeys();
    const minD = parseDateKey(minK);
    const v = calendarViewDate;
    return v.getFullYear() > minD.getFullYear() || v.getMonth() > minD.getMonth();
  }

  function canGoNext() {
    const { maxK } = getMinMaxDateKeys();
    const maxD = parseDateKey(maxK);
    const v = calendarViewDate;
    return v.getFullYear() < maxD.getFullYear() || v.getMonth() < maxD.getMonth();
  }

  function updateDateReadout(key) {
    if (!dateReadout) return;
    if (!key) {
      dateReadout.textContent = '';
      return;
    }
    const d = parseDateKey(key);
    dateReadout.textContent =
      'Selected: ' + d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }

  async function loadSlotsForDate(dateKey) {
    if (!dateKey || !slotContainer) return;
    slotContainer.innerHTML =
      '<div class="booking-slots-empty"><i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i><p>Loading available times…</p></div>';
    const serviceIds = getSelectedServiceIds();
    const staffInput = document.querySelector('input[name="booking_staff"]:checked');
    const staffId = staffInput ? staffInput.value : 'any';
    try {
      const data = await fetchAvailability(dateKey, serviceIds, staffId);
      renderTimeSlots(slotContainer, data.slots, state);
      const savedTime = document.getElementById('bookingTime').value;
      if (savedTime) {
        const slot = slotContainer.querySelector('[data-time-value="' + savedTime + '"]');
        if (slot) {
          slot.classList.add('is-selected');
          state.selectedStaffName = slot.dataset.staffName;
        } else {
          document.getElementById('bookingTime').value = '';
          document.getElementById('bookingStaffResolved').value = '';
        }
      }
    } catch (e) {
      slotContainer.innerHTML =
        '<div class="booking-slots-empty"><i class="fa-solid fa-circle-exclamation" aria-hidden="true"></i><p>' +
        escapeHtml(e.message || 'Could not load times.') +
        '</p></div>';
    }
    updateSummary(state);
  }

  function renderBookingCalendar() {
    if (!bookingCalGrid || !bookingCalTitle || !dateInput) return;

    const { minK, maxK } = getMinMaxDateKeys();
    const t = new Date();
    t.setHours(0, 0, 0, 0);
    const todayKey = toDateKey(t);

    const y = calendarViewDate.getFullYear();
    const m0 = calendarViewDate.getMonth();
    bookingCalTitle.textContent = calendarViewDate.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
    if (bookingCalPrev) bookingCalPrev.disabled = !canGoPrev();
    if (bookingCalNext) bookingCalNext.disabled = !canGoNext();

    bookingCalGrid.textContent = '';
    const firstDow = new Date(y, m0, 1).getDay();
    const mondayOffset = (firstDow + 6) % 7;
    const daysInMonth = new Date(y, m0 + 1, 0).getDate();

    for (let i = 0; i < mondayOffset; i++) {
      const pad = document.createElement('div');
      pad.className = 'booking-cal-pad';
      pad.setAttribute('aria-hidden', 'true');
      bookingCalGrid.appendChild(pad);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const key = y + '-' + pad2(m0 + 1) + '-' + pad2(day);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'booking-cal-day';
      btn.textContent = String(day);
      btn.dataset.dateKey = key;
      if (key < minK || key > maxK) btn.disabled = true;
      if (key === todayKey) btn.classList.add('is-today');
      if (dateInput.value === key) btn.classList.add('is-selected');

      btn.addEventListener('click', () => {
        if (btn.disabled) return;
        dateInput.value = key;
        document.getElementById('bookingTime').value = '';
        document.getElementById('bookingStaffResolved').value = '';
        bookingCalGrid.querySelectorAll('.booking-cal-day').forEach((b) => b.classList.remove('is-selected'));
        btn.classList.add('is-selected');
        updateDateReadout(key);
        loadSlotsForDate(key);
        saveBookingState(currentStep);
      });

      bookingCalGrid.appendChild(btn);
    }
  }

  function syncCalendarViewForStep3() {
    if (dateInput && dateInput.value) {
      const d = parseDateKey(dateInput.value);
      calendarViewDate = new Date(d.getFullYear(), d.getMonth(), 1);
    } else {
      const t = new Date();
      t.setHours(0, 0, 0, 0);
      calendarViewDate = new Date(t.getFullYear(), t.getMonth(), 1);
    }
  }

  async function refreshStep3FromNav() {
    if (!dateInput || !bookingCalGrid) return;
    syncCalendarViewForStep3();
    renderBookingCalendar();
    updateDateReadout(dateInput.value);
    if (dateInput.value) {
      await loadSlotsForDate(dateInput.value);
    }
  }

  window.__bookingOnStaffChange = async () => {
    updateSummary(state);
    saveBookingState(currentStep);
    if (dateInput && dateInput.value) {
      document.getElementById('bookingTime').value = '';
      document.getElementById('bookingStaffResolved').value = '';
      await loadSlotsForDate(dateInput.value);
    }
  };

  window.__bookingOnSlotChange = () => {
    updateSummary(state);
    saveBookingState(currentStep);
  };

  if (bookingCalPrev) {
    bookingCalPrev.addEventListener('click', () => {
      if (!canGoPrev()) return;
      const m = calendarViewDate.getMonth();
      const y = calendarViewDate.getFullYear();
      calendarViewDate = m === 0 ? new Date(y - 1, 11, 1) : new Date(y, m - 1, 1);
      renderBookingCalendar();
    });
  }
  if (bookingCalNext) {
    bookingCalNext.addEventListener('click', () => {
      if (!canGoNext()) return;
      const m = calendarViewDate.getMonth();
      const y = calendarViewDate.getFullYear();
      calendarViewDate = m === 11 ? new Date(y + 1, 0, 1) : new Date(y, m + 1, 1);
      renderBookingCalendar();
    });
  }

  document.querySelectorAll('input[name="booking_service"]').forEach((input) => {
    input.addEventListener('change', () => {
      debouncedUpdateSummary(state);
      saveBookingState(currentStep);
    });
  });

  ['bookingFullName', 'bookingPhone', 'bookingEmail', 'bookingNotes', 'bookingAllergies'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => saveBookingState(currentStep));
  });
  const firstVisit = document.getElementById('bookingFirstVisit');
  if (firstVisit) firstVisit.addEventListener('change', () => saveBookingState(currentStep));

  document.querySelectorAll('input[name="booking_payment"]').forEach((input) => {
    input.addEventListener('change', () => {
      const proof = document.getElementById('bookingPaymentProofWrap');
      if (proof) proof.hidden = input.value === 'pay_later';
      saveBookingState(currentStep);
    });
  });

  root.querySelectorAll('[data-booking-next]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!validateStep(currentStep)) return;
      if (currentStep === 1) {
        try {
          await fetchStaff(getSelectedServiceIds());
          renderStaffGrid('any');
        } catch (e) {
          const err = document.getElementById('bookingStepError');
          if (err) err.textContent = e.message;
          return;
        }
      }
      if (currentStep < 5) {
        currentStep += 1;
        showStep(root, currentStep);
        if (currentStep === 3) {
          await refreshStep3FromNav();
        }
        await updateSummary(state);
        saveBookingState(currentStep);
      }
    });
  });

  root.querySelectorAll('[data-booking-back]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (currentStep > 1 && currentStep < 6) {
        currentStep -= 1;
        showStep(root, currentStep);
        if (currentStep === 3) {
          refreshStep3FromNav();
        }
        saveBookingState(currentStep);
      }
    });
  });

  const confirmBtn = root.querySelector('[data-booking-confirm]');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', async () => {
      const honeypot = document.getElementById('bookingHoneypot');
      if (honeypot && honeypot.value.trim()) return;

      if (!validateStep(5)) return;
      if (!validateStep(4)) {
        currentStep = 4;
        showStep(root, currentStep);
        return;
      }
      if (!validateStep(3)) {
        currentStep = 3;
        showStep(root, currentStep);
        await refreshStep3FromNav();
        return;
      }
      if (!validateStep(1)) {
        currentStep = 1;
        showStep(root, currentStep);
        return;
      }

      confirmBtn.disabled = true;
      const err = document.getElementById('bookingStepError');

      try {
        const result = await submitAppointment(state);

        document.getElementById('confirmReference').textContent = result.booking_reference;
        const listEl = document.getElementById('confirmServicesList');
        if (listEl) {
          listEl.innerHTML = (result.services || [])
            .map((s) => '<li>' + escapeHtml(s.name) + ' · ' + formatMoney(s.price) + '</li>')
            .join('');
        }
        document.getElementById('confirmStaff').textContent = result.staff_name || '—';
        const d = parseDateKey(result.appointment_date);
        document.getElementById('confirmSchedule').textContent =
          d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) +
          ' at ' +
          formatTimeLabel(result.start_time);
        document.getElementById('confirmDeposit').textContent = formatMoney(result.deposit_amount);
        document.getElementById('confirmTotal').textContent = formatMoney(result.total_price);

        const pay = document.querySelector('input[name="booking_payment"]:checked');
        const payEl = document.getElementById('confirmPaymentMethod');
        if (payEl && pay) {
          const labels = {
            mobile_money: 'Mobile Money',
            bank_transfer: 'Bank Transfer',
            pay_later: 'Pay at spa / later',
          };
          payEl.textContent = labels[pay.value] || pay.value;
        }
        document.getElementById('confirmPaymentStatus').textContent =
          pay && pay.value === 'pay_later' ? 'Pending (pay on arrival)' : 'Pending verification';

        currentStep = 6;
        showStep(root, currentStep);
        clearBookingState();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (e) {
        if (err) {
          err.textContent = e.message || 'Booking failed. Please try again.';
        }
        if (e.status === 409) {
          currentStep = 3;
          showStep(root, currentStep);
          await refreshStep3FromNav();
        }
      } finally {
        confirmBtn.disabled = false;
      }
    });
  }

  const restartBtn = root.querySelector('[data-booking-restart]');
  if (restartBtn) {
    restartBtn.addEventListener('click', async () => {
      document.getElementById('bookingFlowForm').reset();
      document.getElementById('bookingTime').value = '';
      document.getElementById('bookingStaffResolved').value = '';
      const t = new Date();
      t.setHours(0, 0, 0, 0);
      calendarViewDate = new Date(t.getFullYear(), t.getMonth(), 1);
      if (dateInput) dateInput.value = '';
      updateDateReadout('');
      renderBookingCalendar();
      if (slotContainer) {
        slotContainer.innerHTML =
          '<div class="booking-slots-empty"><i class="fa-solid fa-clock" aria-hidden="true"></i><p>Choose a date on the calendar to see available times.</p></div>';
      }
      await fetchStaff(getSelectedServiceIds());
      renderStaffGrid('any');
      currentStep = 1;
      clearBookingState();
      showStep(root, currentStep);
      await updateSummary(state);
    });
  }

  fetchCatalog()
    .then(async () => {
      const saved = loadBookingState();
      if (saved && saved.step > 1) {
        (saved.services || []).forEach((id) => {
          const inp = document.querySelector('input[name="booking_service"][value="' + id + '"]');
          if (inp) inp.checked = true;
        });
        try {
          await fetchStaff(getSelectedServiceIds());
          renderStaffGrid(saved.staff || 'any');
        } catch (e) {
          renderStaffGrid('any');
        }
        if (saved.date && dateInput) dateInput.value = saved.date;
        if (saved.time) document.getElementById('bookingTime').value = saved.time;
        if (saved.staffResolved) document.getElementById('bookingStaffResolved').value = saved.staffResolved;
        const fieldMap = {
          bookingFullName:  'name',
          bookingPhone:     'phone',
          bookingEmail:     'email',
          bookingNotes:     'notes',
          bookingAllergies: 'allergies',
        };
        Object.entries(fieldMap).forEach(([elId, key]) => {
          const el = document.getElementById(elId);
          if (el && saved[key]) el.value = saved[key];
        });
        const firstVisitEl = document.getElementById('bookingFirstVisit');
        if (firstVisitEl) firstVisitEl.checked = !!saved.firstVisit;
        if (saved.payment) {
          const inp = document.querySelector('input[name="booking_payment"][value="' + saved.payment + '"]');
          if (inp) inp.checked = true;
        }
        currentStep = saved.step;
        showStep(root, currentStep);
        if (saved.date) {
          syncCalendarViewForStep3();
          renderBookingCalendar();
          updateDateReadout(saved.date);
          await loadSlotsForDate(saved.date);
        }
      } else {
        showStep(root, 1);
        // Restore cart selections from the treatment list page
        try {
          const cart = JSON.parse(sessionStorage.getItem('ss_cart_v1'));
          if (cart && cart.services && cart.services.length) {
            cart.services.forEach(function (id) {
              const inp = document.querySelector('input[name="booking_service"][value="' + id + '"]');
              if (inp) inp.checked = true;
            });
            sessionStorage.removeItem('ss_cart_v1');
            // Switch the active category pill to reveal the first pre-selected card
            const firstChecked = document.querySelector('input[name="booking_service"]:checked');
            if (firstChecked) {
              const card = firstChecked.closest('.booking-service-card[data-category]');
              if (card) {
                const matchPill = document.querySelector(
                  '.booking-category-pill[data-category="' + card.dataset.category + '"]'
                );
                if (matchPill) matchPill.click();
              }
            }
          }
        } catch (e) {}
        const treatmentId = new URLSearchParams(window.location.search).get('treatment');
        if (treatmentId) {
          const preselect = document.querySelector(
            'input[name="booking_service"][value="' + treatmentId + '"]'
          );
          if (preselect) {
            preselect.checked = true;
            const card = preselect.closest('.booking-service-card[data-category]');
            if (card) {
              const matchPill = document.querySelector(
                '.booking-category-pill[data-category="' + card.dataset.category + '"]'
              );
              if (matchPill) matchPill.click();
            }
            try {
              await fetchStaff(getSelectedServiceIds());
              renderStaffGrid('any');
            } catch (e) {
              renderStaffGrid('any');
            }
          }
        }
      }
      await updateSummary(state);
      const payChecked = document.querySelector('input[name="booking_payment"]:checked');
      const proofWrap = document.getElementById('bookingPaymentProofWrap');
      if (proofWrap && payChecked) proofWrap.hidden = payChecked.value === 'pay_later';
    })
    .catch(() => {
      const err = document.getElementById('bookingStepError');
      if (err) err.textContent = 'Could not load services. Please refresh the page.';
    });

  if (dateInput && bookingCalGrid) {
    renderBookingCalendar();
    updateDateReadout(dateInput.value);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initBookingFlow);
} else {
  initBookingFlow();
}
