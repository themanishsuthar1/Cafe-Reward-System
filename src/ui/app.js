// ═══════════════════════════════════════════════════════════════════════════
// Cafe Counter POS — Frontend Logic
// JWT auth (localStorage token), INR (₹) currency, full POS functionality
// ═══════════════════════════════════════════════════════════════════════════

// ── Auth Utilities ─────────────────────────────────────────────────────────
function getToken() {
  return localStorage.getItem("access_token");
}

function setToken(token) {
  localStorage.setItem("access_token", token);
}

function clearToken() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("auth_user");
}

function setAuthUser(userData) {
  localStorage.setItem("auth_user", JSON.stringify(userData));
}

function getAuthUser() {
  try { return JSON.parse(localStorage.getItem("auth_user") || "null"); }
  catch { return null; }
}

/** Appends Authorization: Bearer header to all authenticated API calls */
function authHeaders() {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {})
  };
}

/** Generic fetch wrapper — auto-handles 401 by logging out */
async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) }
  });
  if (res.status === 401) {
    logout(true);  // silent logout, show auth screen
    throw new Error("Session expired. Please log in again.");
  }
  return res;
}

// ── Auth Screen ────────────────────────────────────────────────────────────
function showAuthScreen() {
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("pos-app").classList.add("hidden");
}

function showPosApp(user) {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("pos-app").classList.remove("hidden");
  if (user) {
    document.getElementById("logged-in-user").textContent = user.username || "Staff";
    const roleTag = document.getElementById("user-role-tag");
    if (roleTag) roleTag.textContent = user.role || "staff";
  }
}

function switchAuthTab(tab) {
  const loginForm = document.getElementById("form-login");
  const registerForm = document.getElementById("form-register-auth");
  const tabLogin = document.getElementById("tab-login");
  const tabReg = document.getElementById("tab-register");

  if (tab === "login") {
    loginForm.classList.remove("hidden");
    registerForm.classList.add("hidden");
    tabLogin.classList.add("active");
    tabReg.classList.remove("active");
  } else {
    loginForm.classList.add("hidden");
    registerForm.classList.remove("hidden");
    tabLogin.classList.remove("active");
    tabReg.classList.add("active");
  }
  clearAuthMessages();
}

function clearAuthMessages() {
  const ids = ["login-error", "register-error", "register-success"];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.textContent = ""; el.classList.add("hidden"); }
  });
}

function showAuthError(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.classList.remove("hidden"); }
}

function showAuthSuccess(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.classList.remove("hidden"); }
}

function togglePw(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
  btn.textContent = input.type === "password" ? "👁" : "🙈";
}

function logout(silent = false) {
  clearToken();
  if (!silent) showToast("Logged out successfully.", "success");
  showAuthScreen();
}

// ── Login Form Submit ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {

  // ── Initialise: check existing token ──
  const existingToken = getToken();
  const existingUser = getAuthUser();
  if (existingToken && existingUser) {
    // Verify token is still valid by hitting /auth/me
    fetch("/auth/me", { headers: authHeaders() })
      .then(r => {
        if (r.ok) return r.json();
        throw new Error("token invalid");
      })
      .then(user => showPosApp(user))
      .catch(() => {
        clearToken();
        showAuthScreen();
      });
  } else {
    showAuthScreen();
  }

  // ── Login ──────────────────────────────────────────────────────────────
  const formLogin = document.getElementById("form-login");
  formLogin.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthMessages();
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    const btn = document.getElementById("btn-login");
    btn.disabled = true;
    btn.textContent = "Signing in...";

    try {
      // OAuth2PasswordRequestForm requires application/x-www-form-urlencoded
      const body = new URLSearchParams({ username, password });
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString()
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed.");

      setToken(data.access_token);
      setAuthUser({ username: data.username, role: data.role });
      showPosApp({ username: data.username, role: data.role });
      showToast(`Welcome back, ${data.username}! 🎉`, "success");

      // Initialise POS after login
      fetchRewards();
    } catch (err) {
      showAuthError("login-error", err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Sign In to POS";
    }
  });

  // ── Register ───────────────────────────────────────────────────────────
  const formRegisterAuth = document.getElementById("form-register-auth");
  formRegisterAuth.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthMessages();
    const username = document.getElementById("reg-auth-username").value.trim();
    const email = document.getElementById("reg-auth-email").value.trim();
    const password = document.getElementById("reg-auth-password").value;
    const btn = document.getElementById("btn-register-auth");
    btn.disabled = true;
    btn.textContent = "Creating account...";

    try {
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed.");

      showAuthSuccess("register-success",
        `✅ Account '${data.username}' created (${data.role})! Please sign in.`);
      // Pre-fill login username and switch to login tab
      document.getElementById("login-username").value = username;
      setTimeout(() => switchAuthTab("login"), 1800);
    } catch (err) {
      showAuthError("register-error", err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Create Staff Account";
    }
  });

  // ════════════════════════════════════════════════════════════════════════
  // POS LOGIC
  // ════════════════════════════════════════════════════════════════════════
  let activeMember = null;
  let rewardsList = [];

  // ── Pagination State ──────────────────────────────────────────────────────
  let searchPage = 1;
  const SEARCH_PAGE_SIZE = 5;
  let ledgerPage = 1;
  const LEDGER_PAGE_SIZE = 8;

  // ── Clock Advance ──────────────────────────────────────────────────────
  const btnAdvanceClock = document.getElementById("btn-advance-clock");
  if (btnAdvanceClock) {
    btnAdvanceClock.addEventListener("click", async () => {
      btnAdvanceClock.disabled = true;
      btnAdvanceClock.innerText = "⏳ Advancing...";
      try {
        const res = await apiFetch("/api/clock", {
          method: "POST",
          body: JSON.stringify({ advance_days: 90 })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Clock advance failed");

        const expired = data.total_points_expired || 0;
        const members = data.members_expired_count || 0;
        if (expired > 0) {
          showToast(`⏰ Clock advanced 90 days! Expired ${expired} pts across ${members} member(s).`, "success");
        } else {
          showToast("⏰ Clock advanced 90 days. No stale points found to expire.", "success");
        }
        if (activeMember) await selectMember(activeMember);
      } catch (err) {
        showToast("Clock advance error: " + err.message, "error");
      } finally {
        btnAdvanceClock.disabled = false;
        btnAdvanceClock.innerText = "⏰ Advance 90 Days";
      }
    });
  }

  // ── Outbox Modal ───────────────────────────────────────────────────────
  const btnViewOutbox = document.getElementById("btn-view-outbox");
  const modalOutbox = document.getElementById("modal-outbox");
  const btnCloseOutbox = document.getElementById("btn-close-outbox");
  const outboxList = document.getElementById("outbox-event-list");
  const btnProcessOutbox = document.getElementById("btn-process-outbox");

  if (btnViewOutbox) {
    btnViewOutbox.addEventListener("click", async () => {
      if (modalOutbox) modalOutbox.classList.remove("hidden");
      await loadOutboxEvents();
    });
  }
  if (btnCloseOutbox) {
    btnCloseOutbox.addEventListener("click", () => {
      if (modalOutbox) modalOutbox.classList.add("hidden");
    });
  }
  if (modalOutbox) {
    modalOutbox.addEventListener("click", (e) => {
      if (e.target === modalOutbox) modalOutbox.classList.add("hidden");
    });
  }
  if (btnProcessOutbox) {
    btnProcessOutbox.addEventListener("click", async () => {
      btnProcessOutbox.disabled = true;
      btnProcessOutbox.innerText = "Processing...";
      try {
        const res = await apiFetch("/api/outbox/process", { method: "POST" });
        const data = await res.json();
        showToast(`✅ Processed ${data.processed_count} pending notification(s).`, "success");
        await loadOutboxEvents();
      } catch (err) {
        showToast("Process error: " + err.message, "error");
      } finally {
        btnProcessOutbox.disabled = false;
        btnProcessOutbox.innerText = "✉️ Process Pending";
      }
    });
  }

  async function loadOutboxEvents() {
    if (!outboxList) return;
    outboxList.innerHTML = `<div class="outbox-loading">Loading events...</div>`;
    try {
      const res = await apiFetch("/api/outbox");
      const events = await res.json();
      renderOutboxEvents(events);
    } catch (err) {
      outboxList.innerHTML = `<div class="outbox-loading" style="color:var(--accent-red)">Failed to load events.</div>`;
    }
  }

  function renderOutboxEvents(events) {
    if (!outboxList) return;
    if (!events || events.length === 0) {
      outboxList.innerHTML = `<div class="outbox-loading" style="color:var(--text-muted)">No outbox events yet. Tier upgrades will appear here.</div>`;
      return;
    }
    outboxList.innerHTML = "";
    events.forEach(ev => {
      const p = ev.payload || {};
      const statusClass = ev.status === "PENDING" ? "outbox-status-pending" : "outbox-status-processed";
      const tierFrom = p.old_tier || "?";
      const tierTo = p.new_tier || "?";
      const ts = ev.created_at ? new Date(ev.created_at).toLocaleString() : "";
      const row = document.createElement("div");
      row.className = "outbox-event-row";
      row.innerHTML = `
        <div class="outbox-event-header">
          <span class="outbox-event-type">${ev.event_type}</span>
          <span class="${statusClass}">${ev.status}</span>
        </div>
        <div class="outbox-event-body">
          <div>Member: <strong>${p.member_id || ev.aggregate_id}</strong></div>
          <div>Tier: <span class="tier-badge ${tierFrom}" style="font-size:11px;padding:2px 8px;">${tierFrom}</span> → <span class="tier-badge ${tierTo}" style="font-size:11px;padding:2px 8px;">${tierTo}</span></div>
          <div>Lifetime Pts: <strong>${p.lifetime_points || "—"}</strong></div>
          <div style="font-size:11px;color:var(--text-dim);">${ts} | ID: ${ev.id}</div>
        </div>
      `;
      outboxList.appendChild(row);
    });
  }

  // ── DOM Elements ───────────────────────────────────────────────────────
  const inputSearch = document.getElementById("input-search");
  const dropdownResults = document.getElementById("search-results-dropdown");
  const memberCard = document.getElementById("member-card");
  const formPurchase = document.getElementById("form-purchase");
  const inputAmount = document.getElementById("input-amount");
  const previewPoints = document.getElementById("preview-points");
  const btnRecordPurchase = document.getElementById("btn-record-purchase");
  const activeMultiplierBadge = document.getElementById("active-multiplier-badge");
  const rewardsGrid = document.getElementById("rewards-grid");
  const ledgerRows = document.getElementById("ledger-rows");
  const btnReconcile = document.getElementById("btn-reconcile");
  const reconcileBanner = document.getElementById("reconcile-banner");
  const btnOpenRegister = document.getElementById("btn-open-register");
  const modalRegister = document.getElementById("modal-register");
  const btnCloseRegister = document.getElementById("btn-close-register");
  const btnCancelRegister = document.getElementById("btn-cancel-register");
  const formRegister = document.getElementById("form-register");

  // ── Search ─────────────────────────────────────────────────────────────
  let searchDebounceTimer;
  if (inputSearch) {
    inputSearch.addEventListener("input", (e) => {
      clearTimeout(searchDebounceTimer);
      const query = e.target.value.trim();
      if (!query) { dropdownResults.classList.add("hidden"); return; }
      searchDebounceTimer = setTimeout(() => handleSearch(query), 200);
    });
  }

  async function handleSearch(query, page = 1) {
    searchPage = page;
    try {
      const url = `/api/members/search?query=${encodeURIComponent(query)}&page=${page}&size=${SEARCH_PAGE_SIZE}`;
      const res = await apiFetch(url);
      const data = await res.json();
      renderSearchDropdown(data, query);
    } catch (err) {
      console.error("Search error:", err);
    }
  }

  function renderSearchDropdown(data, query) {
    dropdownResults.innerHTML = "";
    const members = data.items || [];
    const total = data.total || 0;
    const totalPages = data.total_pages || 1;
    const page = data.page || 1;

    if (members.length === 0) {
      dropdownResults.innerHTML = `<div class="dropdown-item"><span>No members found</span></div>`;
    } else {
      members.forEach((m) => {
        const item = document.createElement("div");
        item.className = "dropdown-item";
        item.innerHTML = `
          <div>
            <strong>${m.name}</strong>
            <div style="font-size:12px; color:#9ca3af;">${m.phone}</div>
          </div>
          <span class="tier-badge ${m.tier}">${m.tier} • ${m.current_points} pts</span>
        `;
        item.addEventListener("click", () => selectMember(m));
        dropdownResults.appendChild(item);
      });
    }

    // Pagination controls inside dropdown
    if (total > 0) {
      const pager = document.createElement("div");
      pager.className = "dropdown-pager";
      pager.innerHTML = `
        <button class="pager-btn" ${page <= 1 ? 'disabled' : ''} id="search-prev">‹ Prev</button>
        <span class="pager-info">Page ${page} / ${totalPages} &nbsp;·&nbsp; ${total} result${total !== 1 ? 's' : ''}</span>
        <button class="pager-btn" ${page >= totalPages ? 'disabled' : ''} id="search-next">Next ›</button>
      `;
      dropdownResults.appendChild(pager);

      const prevBtn = pager.querySelector("#search-prev");
      const nextBtn = pager.querySelector("#search-next");
      if (prevBtn) prevBtn.addEventListener("click", (e) => { e.stopPropagation(); handleSearch(query, page - 1); });
      if (nextBtn) nextBtn.addEventListener("click", (e) => { e.stopPropagation(); handleSearch(query, page + 1); });
    }

    dropdownResults.classList.remove("hidden");
  }

  // ── Select Member ──────────────────────────────────────────────────────
  async function selectMember(member) {
    dropdownResults.classList.add("hidden");
    inputSearch.value = member.phone;
    try {
      const res = await apiFetch(`/api/members/phone/${encodeURIComponent(member.phone)}`);
      if (!res.ok) throw new Error("Failed to fetch member details");
      activeMember = await res.json();
      renderMemberCard(activeMember);
      enableTransactionForm(true);
      ledgerPage = 1;  // reset ledger to page 1 on new member selection
      fetchLedgerHistory(activeMember.id, 1);
      renderRewardsGrid();
    } catch (err) {
      showToast("Error loading member: " + err.message, "error");
    }
  }

  function renderMemberCard(m) {
    const prog = m.tier_progress;
    const progressPercent = prog ? prog.progress_percent : 100;
    const nextText = prog && prog.next_tier ? `${prog.points_needed} pts to ${prog.next_tier}` : "Max Tier Reached!";

    memberCard.className = "member-card";
    memberCard.innerHTML = `
      <div class="member-info-header">
        <div>
          <div class="member-name">${m.name}</div>
          <div class="member-phone">📞 ${m.phone} | Joined ${new Date(m.join_date).toLocaleDateString()}</div>
        </div>
        <div class="points-badge-box">
          <div class="points-val">${m.current_points}</div>
          <div class="points-lbl">Available Points</div>
        </div>
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="tier-badge ${m.tier}">${m.tier} TIER (${m.points_multiplier}× Multiplier)</span>
        <span style="font-size:12px; color:#9ca3af;">Lifetime: ${m.lifetime_points} pts</span>
      </div>

      <div class="progress-container">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" style="width: ${progressPercent}%;"></div>
        </div>
        <div class="progress-text">
          <span>Tier Progress</span>
          <span>${nextText}</span>
        </div>
      </div>
    `;

    activeMultiplierBadge.innerText = `${m.points_multiplier}× ${m.tier} Rate`;
    activeMultiplierBadge.className = `badge badge-accent tier-badge ${m.tier}`;
  }

  function enableTransactionForm(enabled) {
    inputAmount.disabled = !enabled;
    btnRecordPurchase.disabled = !enabled;
    btnReconcile.disabled = !enabled;
    if (!enabled) {
      inputAmount.value = "";
      previewPoints.innerText = "0 pts";
    }
  }

  // ── Amount Points Preview (₹) ──────────────────────────────────────────
  inputAmount.addEventListener("input", () => {
    const amt = parseFloat(inputAmount.value) || 0;
    if (amt > 0 && activeMember) {
      const mult = activeMember.points_multiplier || 1.0;
      const pts = Math.floor(amt * mult);
      previewPoints.innerText = `${pts} pts`;
    } else {
      previewPoints.innerText = "0 pts";
    }
  });

  // ── Record Purchase ────────────────────────────────────────────────────
  formPurchase.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!activeMember) return;

    const amount = parseFloat(inputAmount.value);
    if (isNaN(amount) || amount <= 0) {
      showToast("Please enter a valid purchase amount in ₹.", "error");
      return;
    }

    const idempotencyKey = "purch_" + crypto.randomUUID();
    try {
      btnRecordPurchase.disabled = true;
      btnRecordPurchase.innerText = "Processing Transaction...";

      const res = await apiFetch("/api/purchases", {
        method: "POST",
        body: JSON.stringify({
          member_id: activeMember.id,
          amount_spent: amount,
          idempotency_key: idempotencyKey,
          terminal_id: "POS_TERM_1"
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Purchase failed");

      showToast(`Purchase of ₹${amount.toFixed(2)} recorded! Earned +${data.points_earned} points.`, "success");
      if (data.tier_upgraded) {
        showToast(`🎉 Tier upgraded to ${data.new_tier}!`, "success");
      }
      inputAmount.value = "";
      previewPoints.innerText = "0 pts";
      await selectMember(activeMember);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnRecordPurchase.disabled = false;
      btnRecordPurchase.innerText = "⚡ Confirm Purchase & Earn Points";
    }
  });

  // ── Rewards Catalog ────────────────────────────────────────────────────
  async function fetchRewards() {
    try {
      const res = await fetch("/api/rewards");
      const data = await res.json();
      rewardsList = Array.isArray(data) ? data : [];
      renderRewardsGrid();
    } catch (err) {
      console.error("Failed to load rewards:", err);
      rewardsList = [];
    }
  }

  function renderRewardsGrid() {
    if (!Array.isArray(rewardsList) || rewardsList.length === 0) {
      rewardsGrid.innerHTML = `<p class="placeholder-text">No active rewards available</p>`;
      return;
    }

    rewardsGrid.innerHTML = "";
    rewardsList.forEach((rw) => {
      const currentPoints = activeMember ? activeMember.current_points : 0;
      const isEligible = activeMember && currentPoints >= rw.points_cost;

      const card = document.createElement("div");
      card.className = `reward-item-card ${isEligible ? 'eligible' : ''}`;
      card.innerHTML = `
        <div>
          <div class="reward-title">${rw.name}</div>
          <div class="reward-cost">${rw.points_cost} points</div>
        </div>
        <button class="btn btn-sm ${isEligible ? 'btn-primary' : 'btn-secondary'}" ${!isEligible ? 'disabled' : ''}>
          ${isEligible ? 'Redeem' : 'Need ' + (rw.points_cost - currentPoints) + ' pts'}
        </button>
      `;

      if (isEligible) {
        const btnRedeem = card.querySelector("button");
        btnRedeem.addEventListener("click", () => redeemReward(rw));
      }
      rewardsGrid.appendChild(card);
    });
  }

  // ── Redeem Reward ──────────────────────────────────────────────────────
  async function redeemReward(reward) {
    if (!activeMember) return;
    const idempotencyKey = "red_" + crypto.randomUUID();

    try {
      const res = await apiFetch("/api/redemptions", {
        method: "POST",
        body: JSON.stringify({
          member_id: activeMember.id,
          reward_id: reward.id,
          idempotency_key: idempotencyKey,
          terminal_id: "POS_TERM_1"
        })
      });

      const data = await res.json();
      if (!res.ok) {
        if (data.detail && data.detail.error === "INSUFFICIENT_POINTS") {
          throw new Error(`Insufficient Points! Available: ${data.detail.available_points}, Required: ${data.detail.required_points}`);
        }
        throw new Error(data.detail || "Redemption failed");
      }

      showToast(`Redeemed ${reward.name}! -${reward.points_cost} points`, "success");
      await selectMember(activeMember);
    } catch (err) {
      showToast(err.message, "error");
      if (activeMember) selectMember(activeMember);
    }
  }

  // ── Ledger History ─────────────────────────────────────────────────────
  async function fetchLedgerHistory(memberId, page = 1) {
    ledgerPage = page;
    try {
      const res = await apiFetch(`/api/members/${memberId}/ledger?page=${page}&size=${LEDGER_PAGE_SIZE}`);
      const data = await res.json();
      renderLedgerTable(data, memberId);
    } catch (err) {
      console.error("Failed to load ledger history:", err);
    }
  }

  function renderLedgerTable(data, memberId) {
    ledgerRows.innerHTML = "";
    const rows = data.items || [];
    const total = data.total || 0;
    const totalPages = data.total_pages || 1;
    const page = data.page || 1;

    if (rows.length === 0) {
      ledgerRows.innerHTML = `<tr><td colspan="5" class="empty-table">No transaction history found</td></tr>`;
    } else {
      rows.forEach((r) => {
        const isPlus = r.points_delta > 0;
        const deltaText = isPlus ? `+${r.points_delta}` : `${r.points_delta}`;
        const deltaClass = isPlus ? "delta-plus" : "delta-minus";
        const timeStr = new Date(r.created_at).toLocaleTimeString([], {
          hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${timeStr}</td>
          <td><strong>${r.type}</strong></td>
          <td class="${deltaClass}">${deltaText}</td>
          <td><span class="tier-badge ${r.tier_at_time}">${r.tier_at_time}</span></td>
          <td style="font-family:monospace; font-size:11px; color:#9ca3af;" title="${r.idempotency_key}">${r.idempotency_key.substring(0, 16)}...</td>
        `;
        ledgerRows.appendChild(tr);
      });
    }

    // Pagination footer row
    if (total > 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td colspan="5">
          <div class="ledger-pager">
            <button class="pager-btn" ${page <= 1 ? 'disabled' : ''} id="ledger-prev">‹ Prev</button>
            <span class="pager-info">Page ${page} / ${totalPages} &nbsp;·&nbsp; ${total} transaction${total !== 1 ? 's' : ''}</span>
            <button class="pager-btn" ${page >= totalPages ? 'disabled' : ''} id="ledger-next">Next ›</button>
          </div>
        </td>
      `;
      ledgerRows.appendChild(tr);

      const prevBtn = tr.querySelector("#ledger-prev");
      const nextBtn = tr.querySelector("#ledger-next");
      if (prevBtn) prevBtn.addEventListener("click", () => fetchLedgerHistory(memberId, page - 1));
      if (nextBtn) nextBtn.addEventListener("click", () => fetchLedgerHistory(memberId, page + 1));
    }
  }

  // ── Reconcile ──────────────────────────────────────────────────────────
  btnReconcile.addEventListener("click", async () => {
    if (!activeMember) return;
    try {
      btnReconcile.disabled = true;
      btnReconcile.innerText = "Replaying...";

      const res = await apiFetch(`/api/members/${activeMember.id}/reconcile`);
      const data = await res.json();

      reconcileBanner.classList.remove("hidden");
      if (data.is_reconciled) {
        reconcileBanner.className = "reconcile-banner success";
        reconcileBanner.innerText = `✅ Audit Passed: Replayed SUM(points_delta) = ${data.recalculated_current_points} matches cached balance. 0 Discrepancy!`;
      } else {
        reconcileBanner.className = "reconcile-banner failed";
        reconcileBanner.innerText = `⚠️ Discrepancy Detected! Cached: ${data.cached_current_points}, Replayed: ${data.recalculated_current_points}`;
      }
    } catch (err) {
      showToast("Reconciliation failed: " + err.message, "error");
    } finally {
      btnReconcile.disabled = false;
      btnReconcile.innerText = "🔍 Replay Reconcile";
    }
  });

  // ── Register Member Modal (POS) ────────────────────────────────────────
  btnOpenRegister.addEventListener("click", () => modalRegister.classList.remove("hidden"));
  btnCloseRegister.addEventListener("click", () => modalRegister.classList.add("hidden"));
  btnCancelRegister.addEventListener("click", () => modalRegister.classList.add("hidden"));

  formRegister.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("reg-name").value.trim();
    const phone = document.getElementById("reg-phone").value.trim();

    try {
      const res = await apiFetch("/api/members", {
        method: "POST",
        body: JSON.stringify({ name, phone })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed");

      showToast(`Member '${data.name}' registered successfully!`, "success");
      modalRegister.classList.add("hidden");
      formRegister.reset();
      await selectMember(data);
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // ── Toast Notifications ────────────────────────────────────────────────
  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  // Make showToast globally accessible for inline onclick handlers
  window.showToast = showToast;

  // Fetch rewards on load (open endpoint, no auth needed)
  fetchRewards();

}); // end DOMContentLoaded

// Expose global helpers for inline HTML handlers
function switchAuthTab(tab) {
  // re-declared globally so inline onclick="switchAuthTab(...)" works
  const loginForm = document.getElementById("form-login");
  const registerForm = document.getElementById("form-register-auth");
  const tabLogin = document.getElementById("tab-login");
  const tabReg = document.getElementById("tab-register");
  if (!loginForm) return;

  if (tab === "login") {
    loginForm.classList.remove("hidden");
    registerForm.classList.add("hidden");
    tabLogin.classList.add("active");
    tabReg.classList.remove("active");
  } else {
    loginForm.classList.add("hidden");
    registerForm.classList.remove("hidden");
    tabLogin.classList.remove("active");
    tabReg.classList.add("active");
  }
}

function togglePw(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
  btn.textContent = input.type === "password" ? "👁" : "🙈";
}

function logout(silent = false) {
  localStorage.removeItem("access_token");
  localStorage.removeItem("auth_user");
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("pos-app").classList.add("hidden");
  if (!silent && window.showToast) window.showToast("Logged out successfully.", "success");
}
