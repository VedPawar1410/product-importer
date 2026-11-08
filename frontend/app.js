/* Product Importer frontend.
   One script for three pages; <body data-page="..."> picks which part runs.
   Plain JS, no build step: FastAPI serves these files as-is. */
(() => {
  'use strict';

  // --- Small helpers ---------------------------------------------------------

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const nf = new Intl.NumberFormat();
  const price = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const ICON = {
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12M9 7V4h6v3"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/></svg>',
    box: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>',
    link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
  };

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  }

  function formatDuration(seconds) {
    if (!Number.isFinite(seconds)) return '–';
    const s = Math.max(0, Math.round(seconds));
    const m = Math.floor(s / 60);
    return m ? `${m}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`;
  }

  function timeAgo(iso) {
    const secs = (Date.now() - new Date(iso).getTime()) / 1000;
    if (secs < 60) return 'just now';
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
    if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
    if (secs < 86400 * 30) return `${Math.floor(secs / 86400)}d ago`;
    return new Date(iso).toLocaleDateString();
  }

  function debounce(fn, ms) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  }

  // Count smoothly from the previous value: imports report progress per batch
  // of 1,000 rows, and easing the numbers makes those jumps feel continuous.
  function tweenNumber(el, to) {
    const from = Number(el.dataset.value || 0);
    el.dataset.value = to;
    if (from === to) { el.textContent = nf.format(to); return; }
    const start = performance.now();
    const step = (now) => {
      const k = Math.min(1, (now - start) / 650);
      el.textContent = nf.format(Math.round(from + (to - from) * (1 - (1 - k) ** 3)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // --- Toasts, dialogs, busy buttons -----------------------------------------

  function toast(message, type = 'success', ms = 3800) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span class="t-dot"></span><div>${escapeHtml(message)}</div>`;
    $('#toasts').appendChild(el);
    setTimeout(() => {
      el.classList.add('leaving');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    }, ms);
  }

  function setupDialogs() {
    $$('dialog.modal').forEach((dialog) => {
      dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); }); // backdrop click
      $$('[data-close]', dialog).forEach((btn) => btn.addEventListener('click', () => dialog.close()));
    });
  }

  /** Native <dialog> confirmation; resolves true only if the user confirms. */
  function confirmAction({ title, text, confirmLabel = 'Delete' }) {
    const dialog = $('#confirmModal');
    $('#confirmTitle').textContent = title;
    $('#confirmText').textContent = text;
    $('#confirmBtn').textContent = confirmLabel;
    $('#confirmBtn').onclick = () => dialog.close('confirm');
    dialog.returnValue = '';
    dialog.showModal();
    return new Promise((resolve) => {
      dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true });
    });
  }

  async function withBusy(button, label, fn) {
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span>${escapeHtml(label)}`;
    try { return await fn(); } finally { button.disabled = false; button.innerHTML = original; }
  }

  // --- API -------------------------------------------------------------------

  async function errorMessage(res) {
    try {
      const { detail } = await res.json();
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.slice(-1)[0] ?? 'field'}: ${d.msg}`).join('; ');
    } catch { /* not JSON */ }
    return `Request failed (${res.status})`;
  }

  /** fetch + JSON + readable errors. Free Render instances sleep when idle, so
      a request that takes over 4s shows a "waking up" note instead of looking frozen. */
  async function api(path, { method = 'GET', body } = {}) {
    const options = { method, headers: {} };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    const wakeNote = setTimeout(() => toast('Waking up the server… free instances sleep when idle (up to a minute).', 'info', 6000), 4000);
    try {
      const res = await fetch(path, options);
      if (!res.ok) throw new Error(await errorMessage(res));
      return res.status === 204 ? null : res.json();
    } finally {
      clearTimeout(wakeNote);
    }
  }

  // ===========================================================================
  // Upload page
  // ===========================================================================

  function initUpload() {
    const input = $('#csvFile');
    const zone = $('#dropzone');
    const uploadBtn = $('#uploadBtn');
    const ringBar = $('#ringBar');
    const CIRCUMFERENCE = 2 * Math.PI * 52;
    ringBar.style.strokeDasharray = CIRCUMFERENCE;
    let file = null;

    function setFile(f) {
      if (f && !/\.csv$/i.test(f.name)) { toast('Please choose a .csv file.', 'error'); return; }
      file = f || null;
      $('#fileChip').hidden = !file;
      uploadBtn.disabled = !file;
      if (file) {
        $('#fileName').textContent = file.name;
        $('#fileSize').textContent = formatBytes(file.size);
      } else {
        input.value = '';
      }
    }

    input.addEventListener('change', () => setFile(input.files[0]));
    ['dragenter', 'dragover'].forEach((type) => zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.add('is-dragging'); }));
    ['dragleave', 'drop'].forEach((type) => zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.remove('is-dragging'); }));
    zone.addEventListener('drop', (e) => setFile(e.dataTransfer.files[0]));
    $('#clearFileBtn').addEventListener('click', () => setFile(null));
    uploadBtn.addEventListener('click', () => file && startImport(file));

    function setRing(pct, state = '') {
      const clamped = Math.max(0, Math.min(100, pct));
      ringBar.style.strokeDashoffset = CIRCUMFERENCE * (1 - clamped / 100);
      $('#pct').textContent = Math.floor(clamped);
      $('#ring').className = `ring ${state}`;
    }

    function setPill(text, classes) {
      const pill = $('#statusPill');
      pill.textContent = text;
      pill.className = `pill ${classes}`;
    }

    function startImport(f) {
      $('#pickStage').hidden = true;
      $('#progressStage').hidden = false;
      $('#resultBanner').hidden = true;
      $('#pFileName').textContent = f.name;
      $('#pFileSize').textContent = formatBytes(f.size);
      ['#statOk', '#statFailed'].forEach((id) => { $(id).dataset.value = 0; $(id).textContent = '0'; });
      $('#statFailed').classList.remove('danger');
      ['#statTotal', '#statRate', '#statEta'].forEach((id) => { $(id).textContent = '–'; });
      setRing(0);
      setPill('Uploading', 'pill-accent pill-live');
      $('#ringSub').textContent = 'uploaded';

      const startedAt = performance.now();
      let processingStartedAt = null;
      let lastPct = 0;
      const elapsedTimer = setInterval(() => {
        $('#statElapsed').textContent = formatDuration((performance.now() - startedAt) / 1000);
      }, 1000);
      // No upload progress after 5s usually means the free server is still waking up.
      const wakeHint = setTimeout(() => { $('#wakeHint').hidden = false; }, 5000);

      // XHR rather than fetch: it reports upload progress for big files.
      const xhr = new XMLHttpRequest();
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        clearTimeout(wakeHint);
        $('#wakeHint').hidden = true;
        setRing((e.loaded / e.total) * 100);
      };
      xhr.onload = () => {
        clearTimeout(wakeHint);
        $('#wakeHint').hidden = true;
        if (xhr.status !== 202) {
          let message = `Upload failed (${xhr.status}).`;
          try { message = JSON.parse(xhr.responseText).detail || message; } catch { /* keep default */ }
          finish('failed', { message });
          return;
        }
        poll(JSON.parse(xhr.responseText).task_id);
      };
      xhr.onerror = () => finish('failed', { message: 'Network error while uploading. Check your connection and try again.' });
      const form = new FormData();
      form.append('file', f);
      xhr.open('POST', '/upload/start');
      xhr.send(form);

      async function poll(taskId) {
        setRing(0);
        setPill('Queued', 'pill-muted pill-live');
        $('#ringSub').textContent = 'queued';

        for (;;) {
          let data;
          try {
            data = await api(`/upload/status/${taskId}`);
          } catch {
            await sleep(2000); // transient network/server hiccup: keep polling
            continue;
          }
          const state = data.status.status;
          const p = data.progress || {};
          const total = Number(p.total_rows || 0);
          const done = Number(p.processed_rows || 0);
          const ok = Number(p.successful_rows || 0);
          const failed = Number(p.failed_rows || 0);

          if (state === 'PROCESSING' || done > 0) {
            processingStartedAt ??= performance.now();
            setPill('Importing', 'pill-accent pill-live');
            $('#ringSub').textContent = 'processed';
          }
          tweenNumber($('#statOk'), ok);
          tweenNumber($('#statFailed'), failed);
          $('#statFailed').classList.toggle('danger', failed > 0);
          if (total) $('#statTotal').textContent = nf.format(total);

          const secs = processingStartedAt ? (performance.now() - processingStartedAt) / 1000 : 0;
          const rate = secs > 0.5 ? done / secs : 0;
          if (rate > 0) $('#statRate').textContent = nf.format(Math.round(rate));
          $('#statEta').textContent = rate > 0 && total ? formatDuration((total - done) / rate) : '–';

          lastPct = total ? (done / total) * 100 : 0;
          setRing(lastPct);

          if (state === 'COMPLETED') return finish('done', { ok, failed });
          if (state === 'FAILED') return finish('failed', { message: data.status.error || 'The import failed.' });
          await sleep(1000);
        }
      }

      function finish(result, { ok = 0, failed = 0, message = '' }) {
        clearInterval(elapsedTimer);
        clearTimeout(wakeHint);
        $('#statEta').textContent = '–';
        const banner = $('#resultBanner');
        banner.hidden = false;

        if (result === 'done') {
          setRing(100, 'done');
          setPill('Completed', 'pill-success');
          $('#ringSub').textContent = 'complete';
          banner.className = 'result-banner success';
          $('#resultText').textContent = `Imported ${nf.format(ok)} rows${failed ? ` · ${nf.format(failed)} skipped as invalid` : ''}.`;
          $('#resultActions').innerHTML = '<a class="btn btn-primary btn-sm" href="/products.html">View products</a><button type="button" class="btn btn-secondary btn-sm" data-again>Import another</button>';
          toast('Import complete');
        } else {
          setRing(lastPct, 'failed');
          setPill('Failed', 'pill-danger');
          $('#ringSub').textContent = 'stopped';
          banner.className = 'result-banner failed';
          $('#resultText').textContent = message;
          $('#resultActions').innerHTML = '<button type="button" class="btn btn-secondary btn-sm" data-again>Try again</button>';
        }
        $('[data-again]', banner).addEventListener('click', () => {
          $('#progressStage').hidden = true;
          $('#pickStage').hidden = false;
          setFile(null);
        });
      }
    }
  }

  // ===========================================================================
  // Products page
  // ===========================================================================

  function initProducts() {
    const PAGE_SIZE = 20;
    const state = { page: 1, name: '', sku: '', active: '', total: 0 };
    const rows = $('#productRows');
    const modal = $('#productModal');
    let items = [];
    let editingId = null;
    let requestSeq = 0;

    const hasFilters = () => Boolean(state.name || state.sku || state.active);

    function query({ paged = true } = {}) {
      const params = new URLSearchParams();
      if (paged) { params.set('limit', PAGE_SIZE); params.set('offset', (state.page - 1) * PAGE_SIZE); }
      if (state.name) params.set('name', state.name);
      if (state.sku) params.set('sku', state.sku);
      if (state.active) params.set('active', state.active);
      return params;
    }

    function showSkeleton() {
      rows.innerHTML = Array.from({ length: 8 }, (_, i) => `
        <tr>
          <td><span class="skeleton" style="width: 92px"></span></td>
          <td><span class="skeleton" style="width: ${140 + ((i * 37) % 120)}px"></span>
              <span class="skeleton" style="width: ${90 + ((i * 53) % 140)}px; height: 9px; margin-top: 8px"></span></td>
          <td class="num"><span class="skeleton" style="width: 52px; margin-left: auto"></span></td>
          <td><span class="skeleton" style="width: 62px"></span></td>
          <td><span class="skeleton" style="width: 56px"></span></td>
          <td></td>
        </tr>`).join('');
    }

    async function load() {
      const seq = ++requestSeq; // typing fires several requests; only the latest may render
      if (items.length) rows.style.opacity = '0.55'; else showSkeleton();
      try {
        const data = await api(`/products?${query()}`);
        if (seq !== requestSeq) return;
        if (!data.items.length && state.page > 1) { state.page -= 1; load(); return; }
        state.total = data.total;
        items = data.items;
        render(data);
      } catch (err) {
        if (seq !== requestSeq) return;
        items = [];
        rows.innerHTML = '';
        showEmpty('error', err.message);
      } finally {
        if (seq === requestSeq) rows.style.opacity = '';
      }
    }

    function render({ total }) {
      $('#totalBadge').textContent = hasFilters() ? `${nf.format(total)} matching` : nf.format(total);
      $('#bulkDeleteLabel').textContent = hasFilters() ? `Delete ${nf.format(total)} matching` : 'Delete all';
      $('#bulkDeleteBtn').disabled = total === 0;

      if (!items.length) {
        rows.innerHTML = '';
        showEmpty(hasFilters() ? 'nomatch' : 'none');
        return;
      }
      $('#productsEmpty').hidden = true;
      rows.innerHTML = items.map((p) => `
        <tr>
          <td class="cell-sku">${escapeHtml(p.sku)}</td>
          <td>
            <div class="cell-name">${escapeHtml(p.name)}</div>
            ${p.description ? `<div class="cell-desc" title="${escapeHtml(p.description)}">${escapeHtml(p.description)}</div>` : ''}
          </td>
          <td class="num">${p.price == null ? '<span class="cell-muted">—</span>' : price.format(p.price)}</td>
          <td>${p.active ? '<span class="pill pill-success">Active</span>' : '<span class="pill pill-muted">Inactive</span>'}</td>
          <td class="cell-muted" title="${escapeHtml(new Date(p.updated_at).toLocaleString())}">${timeAgo(p.updated_at)}</td>
          <td class="actions">
            <div class="row-actions">
              <button type="button" class="icon-btn" data-edit="${p.id}" aria-label="Edit ${escapeHtml(p.sku)}">${ICON.edit}</button>
              <button type="button" class="icon-btn danger" data-delete="${p.id}" aria-label="Delete ${escapeHtml(p.sku)}">${ICON.trash}</button>
            </div>
          </td>
        </tr>`).join('');

      const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      const from = (state.page - 1) * PAGE_SIZE + 1;
      $('#pagination').hidden = false;
      $('#pageSummary').innerHTML = `Showing <span class="mono">${nf.format(from)}–${nf.format(from + items.length - 1)}</span> of <span class="mono">${nf.format(total)}</span>`;
      $('#pageLabel').textContent = `${nf.format(state.page)} / ${nf.format(pages)}`;
      $('#prevPage').disabled = state.page <= 1;
      $('#nextPage').disabled = state.page >= pages;
    }

    function showEmpty(kind, message = '') {
      const views = {
        none: [ICON.box, 'No products yet', 'Import a CSV to fill your catalog, or add a product by hand.', '<a class="btn btn-primary" href="/">Import a CSV</a>'],
        nomatch: [ICON.search, 'No matching products', 'Try a different name or SKU, or clear the filters.', '<button type="button" class="btn btn-secondary" data-clear>Clear filters</button>'],
        error: [ICON.alert, "Couldn't load products", message, '<button type="button" class="btn btn-secondary" data-retry>Try again</button>'],
      };
      const [icon, title, text, action] = views[kind];
      const box = $('#productsEmpty');
      box.hidden = false;
      $('#pagination').hidden = true;
      box.innerHTML = `<div class="empty"><div class="empty-icon">${icon}</div><h3>${title}</h3><p>${escapeHtml(text)}</p>${action}</div>`;
      $('[data-clear]', box)?.addEventListener('click', clearFilters);
      $('[data-retry]', box)?.addEventListener('click', load);
    }

    // Filters: live search with a 300 ms debounce, so typing doesn't fire a request per key.
    const applyTextFilters = debounce(() => {
      state.name = $('#filterName').value.trim();
      state.sku = $('#filterSku').value.trim();
      state.page = 1;
      load();
    }, 300);
    $('#filterName').addEventListener('input', applyTextFilters);
    $('#filterSku').addEventListener('input', applyTextFilters);

    const statusButtons = $$('.segmented button');
    statusButtons.forEach((btn) => btn.addEventListener('click', () => {
      statusButtons.forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
      state.active = btn.dataset.active;
      state.page = 1;
      load();
    }));

    function clearFilters() {
      $('#filterName').value = '';
      $('#filterSku').value = '';
      statusButtons.forEach((b, i) => b.setAttribute('aria-pressed', String(i === 0)));
      Object.assign(state, { name: '', sku: '', active: '', page: 1 });
      load();
    }

    $('#prevPage').addEventListener('click', () => { state.page -= 1; load(); });
    $('#nextPage').addEventListener('click', () => { state.page += 1; load(); });

    // Row actions (one delegated listener for the whole table)
    rows.addEventListener('click', async (e) => {
      const editBtn = e.target.closest('[data-edit]');
      const deleteBtn = e.target.closest('[data-delete]');
      if (editBtn) openModal(items.find((p) => String(p.id) === editBtn.dataset.edit));
      if (!deleteBtn) return;
      const product = items.find((p) => String(p.id) === deleteBtn.dataset.delete);
      const confirmed = await confirmAction({
        title: 'Delete this product?',
        text: `${product.sku} · ${product.name} will be permanently removed.`,
      });
      if (!confirmed) return;
      try {
        await api(`/products/${product.id}`, { method: 'DELETE' });
        toast(`Deleted ${product.sku}`);
        load();
      } catch (err) {
        toast(err.message, 'error');
      }
    });

    // Create / edit
    function openModal(product = null) {
      editingId = product ? product.id : null;
      $('#productModalTitle').textContent = product ? 'Edit product' : 'New product';
      $('#productSubmit').textContent = product ? 'Save changes' : 'Create product';
      $('#productSku').value = product?.sku ?? '';
      $('#productName').value = product?.name ?? '';
      $('#productDescription').value = product?.description ?? '';
      $('#productPrice').value = product?.price ?? '';
      $('#productActive').checked = product ? product.active : true;
      $('#productFormError').hidden = true;
      modal.showModal();
      $(product ? '#productName' : '#productSku').focus();
    }
    $('#newProductBtn').addEventListener('click', () => openModal());

    $('#productForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errorBox = $('#productFormError');
      const body = {
        sku: $('#productSku').value.trim(),
        name: $('#productName').value.trim(),
        description: $('#productDescription').value.trim() || null,
        price: $('#productPrice').value === '' ? null : Number($('#productPrice').value),
        active: $('#productActive').checked,
      };
      if (!body.sku || !body.name) {
        errorBox.textContent = 'SKU and name are required.';
        errorBox.hidden = false;
        return;
      }
      await withBusy($('#productSubmit'), 'Saving…', async () => {
        try {
          await api(editingId ? `/products/${editingId}` : '/products', { method: editingId ? 'PUT' : 'POST', body });
          modal.close();
          toast(editingId ? `Saved ${body.sku}` : `Created ${body.sku}`);
          load();
        } catch (err) {
          errorBox.textContent = err.message; // e.g. the API's 409 "SKU already exists"
          errorBox.hidden = false;
        }
      });
    });

    // Bulk delete: deletes exactly what the current filters match
    $('#bulkDeleteBtn').addEventListener('click', async () => {
      const count = nf.format(state.total);
      const confirmed = await confirmAction({
        title: hasFilters() ? `Delete ${count} matching products?` : `Delete all ${count} products?`,
        text: hasFilters()
          ? 'Every product matching the current filters will be permanently removed. This cannot be undone.'
          : 'Your whole catalog will be permanently removed. This cannot be undone.',
        confirmLabel: `Delete ${count}`,
      });
      if (!confirmed) return;
      try {
        await withBusy($('#bulkDeleteBtn'), 'Deleting…', () => api(`/products/all?${query({ paged: false })}`, { method: 'DELETE' }));
        toast(`Deleted ${count} products`);
        state.page = 1;
        load();
      } catch (err) {
        toast(err.message, 'error');
      }
    });

    load();
  }

  // ===========================================================================
  // Webhooks page
  // ===========================================================================

  function initWebhooks() {
    const rows = $('#webhookRows');
    const modal = $('#webhookModal');
    let hooks = [];
    let editing = null;

    async function load() {
      if (!hooks.length) {
        rows.innerHTML = Array.from({ length: 3 }, () => `
          <tr><td><span class="skeleton" style="width: 120px"></span></td><td><span class="skeleton" style="width: 260px"></span></td>
          <td><span class="skeleton" style="width: 60px"></span></td><td></td></tr>`).join('');
      }
      try {
        hooks = await api('/webhooks');
        render();
      } catch (err) {
        rows.innerHTML = '';
        showEmpty(ICON.alert, "Couldn't load webhooks", err.message, '<button type="button" class="btn btn-secondary" data-retry>Try again</button>');
      }
    }

    function render() {
      $('#webhookBadge').textContent = nf.format(hooks.length);
      if (!hooks.length) {
        rows.innerHTML = '';
        showEmpty(ICON.link, 'No webhooks yet', 'Add an endpoint to get a POST whenever an import completes.', '<button type="button" class="btn btn-primary" data-new>New webhook</button>');
        return;
      }
      $('#webhooksEmpty').hidden = true;
      rows.innerHTML = hooks.map((h) => `
        <tr>
          <td><span class="tag">${escapeHtml(h.event)}</span></td>
          <td class="cell-url" title="${escapeHtml(h.url)}">${escapeHtml(h.url)}</td>
          <td class="cell-muted">${h.created_at ? timeAgo(h.created_at) : '—'}</td>
          <td class="actions">
            <div class="row-actions">
              <button type="button" class="btn btn-secondary btn-sm" data-test="${h.id}">${ICON.send} Test</button>
              <button type="button" class="icon-btn" data-edit="${h.id}" aria-label="Edit webhook">${ICON.edit}</button>
              <button type="button" class="icon-btn danger" data-delete="${h.id}" aria-label="Delete webhook">${ICON.trash}</button>
            </div>
          </td>
        </tr>`).join('');
    }

    function showEmpty(icon, title, text, action) {
      const box = $('#webhooksEmpty');
      box.hidden = false;
      box.innerHTML = `<div class="empty"><div class="empty-icon">${icon}</div><h3>${title}</h3><p>${escapeHtml(text)}</p>${action}</div>`;
      $('[data-new]', box)?.addEventListener('click', () => openModal());
      $('[data-retry]', box)?.addEventListener('click', load);
    }

    rows.addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-test], [data-edit], [data-delete]');
      if (!btn) return;
      const hook = hooks.find((h) => String(h.id) === (btn.dataset.test || btn.dataset.edit || btn.dataset.delete));

      if (btn.dataset.test) {
        await withBusy(btn, 'Sending', async () => {
          try {
            await api(`/webhooks/test/${encodeURIComponent(hook.event)}`, { method: 'POST' });
            toast(`Test "${hook.event}" event queued for delivery to every subscribed URL.`, 'success', 5000);
          } catch (err) {
            toast(err.message, 'error');
          }
        });
      } else if (btn.dataset.edit) {
        openModal(hook);
      } else {
        const confirmed = await confirmAction({ title: 'Delete this webhook?', text: `${hook.url} will stop receiving "${hook.event}" events.` });
        if (!confirmed) return;
        try {
          await api(`/webhooks/${hook.id}`, { method: 'DELETE' });
          toast('Webhook deleted');
          load();
        } catch (err) {
          toast(err.message, 'error');
        }
      }
    });

    function openModal(hook = null) {
      editing = hook;
      $('#webhookModalTitle').textContent = hook ? 'Edit webhook' : 'New webhook';
      $('#webhookEvent').value = hook?.event ?? 'import.completed';
      $('#webhookUrl').value = hook?.url ?? '';
      $('#webhookEditNote').hidden = !hook;
      $('#webhookFormError').hidden = true;
      modal.showModal();
      $('#webhookUrl').focus();
    }
    $('#newWebhookBtn').addEventListener('click', () => openModal());

    $('#webhookForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errorBox = $('#webhookFormError');
      const body = { event: $('#webhookEvent').value.trim(), url: $('#webhookUrl').value.trim() };
      let validUrl = false;
      try { validUrl = ['http:', 'https:'].includes(new URL(body.url).protocol); } catch { /* invalid */ }
      if (!body.event || !validUrl) {
        errorBox.textContent = !body.event ? 'Event is required.' : 'Enter a full http(s):// URL.';
        errorBox.hidden = false;
        return;
      }
      await withBusy($('#webhookSubmit'), 'Saving…', async () => {
        try {
          // No update endpoint: create the new webhook first, then remove the old
          // one, so a failure never leaves you with neither.
          await api('/webhooks', { method: 'POST', body });
          if (editing) await api(`/webhooks/${editing.id}`, { method: 'DELETE' });
          modal.close();
          toast(editing ? 'Webhook updated' : 'Webhook created');
          load();
        } catch (err) {
          errorBox.textContent = err.message;
          errorBox.hidden = false;
        }
      });
    });

    load();
  }

  // --- Boot ------------------------------------------------------------------

  setupDialogs();
  const pages = { upload: initUpload, products: initProducts, webhooks: initWebhooks };
  pages[document.body.dataset.page]?.();
})();
