/* ── TriBet – JavaScript principal ── */

const TriBet = (() => {
  let currentSelection = null;

  function init() {
    initOddsButtons();
    initSlip();
    initQuickAmounts();
    initPlaceBet();
    initSlipToggle();
  }

  // ── Boutons de cote ─────────────────────────────────────────────────────────

  function initOddsButtons() {
    document.querySelectorAll('.odds-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        if (document.body.dataset.loggedIn !== 'true') {
          showToast('Connectez-vous pour parier.', 'error');
          setTimeout(() => window.location.href = '/login', 1200);
          return;
        }
        selectOddsBtn(btn);
      });
    });
  }

  function selectOddsBtn(btn) {
    document.querySelectorAll('.odds-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    currentSelection = {
      id:     btn.dataset.selectionId,
      name:   btn.dataset.selectionName,
      market: btn.dataset.marketName,
      odds:   parseFloat(btn.dataset.odds),
    };
    openSlip(currentSelection);
  }

  // ── Bulletin de pari ─────────────────────────────────────────────────────────

  function initSlip() {
    const input = document.getElementById('bet-amount-input');
    if (input) input.addEventListener('input', updatePotentialWin);
  }

  function openSlip(selection) {
    const slip = document.getElementById('betting-slip');
    if (!slip) return;
    slip.classList.remove('collapsed');
    document.getElementById('slip-selection-name').textContent = selection.name;
    document.getElementById('slip-market-name').textContent    = selection.market;
    document.getElementById('slip-odds').textContent           = selection.odds.toFixed(2);
    const input = document.getElementById('bet-amount-input');
    if (input.value) updatePotentialWin();
    input.focus();
  }

  function initSlipToggle() {
    const header = document.querySelector('.slip-header');
    if (header) {
      header.addEventListener('click', () => {
        document.getElementById('betting-slip').classList.toggle('collapsed');
      });
    }
    const closeBtn = document.getElementById('slip-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', e => { e.stopPropagation(); clearSlip(); });
    }
  }

  function updatePotentialWin() {
    if (!currentSelection) return;
    const amount = parseFloat(document.getElementById('bet-amount-input').value) || 0;
    const win    = Math.round(amount * currentSelection.odds);
    const el     = document.getElementById('potential-win');
    if (el) el.textContent = `${win} pts`;
  }

  function clearSlip() {
    currentSelection = null;
    document.querySelectorAll('.odds-btn').forEach(b => b.classList.remove('selected'));
    const slip  = document.getElementById('betting-slip');
    const input = document.getElementById('bet-amount-input');
    const el    = document.getElementById('potential-win');
    if (slip)  slip.classList.add('collapsed');
    if (input) input.value = '';
    if (el)    el.textContent = '0 pts';
  }

  // ── Mises rapides ────────────────────────────────────────────────────────────

  function initQuickAmounts() {
    document.querySelectorAll('.quick-amount').forEach(btn => {
      btn.addEventListener('click', () => {
        const input = document.getElementById('bet-amount-input');
        if (!input) return;
        const current = parseFloat(input.value) || 0;
        input.value   = (current + parseFloat(btn.dataset.amount)).toFixed(0);
        updatePotentialWin();
      });
    });
    const clearBtn = document.getElementById('clear-amount');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        const input = document.getElementById('bet-amount-input');
        if (input) { input.value = ''; updatePotentialWin(); }
      });
    }
  }

  // ── Placer le pari ───────────────────────────────────────────────────────────

  function initPlaceBet() {
    const btn = document.getElementById('place-bet-btn');
    if (btn) btn.addEventListener('click', placeBet);
  }

  async function placeBet() {
    if (!currentSelection) { showToast('Sélectionnez une cote.', 'error'); return; }
    const amount = parseFloat(document.getElementById('bet-amount-input').value);
    if (!amount || amount < 1) { showToast('Mise minimum : 1 point', 'error'); return; }

    const btn = document.getElementById('place-bet-btn');
    btn.disabled    = true;
    btn.textContent = 'Envoi…';

    try {
      const res  = await fetch('/api/bet', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ selection_id: currentSelection.id, amount }),
      });
      const data = await res.json();

      if (data.success) {
        showToast(data.message, 'success');
        // Mise à jour du solde affiché
        document.querySelectorAll('.user-balance').forEach(el => {
          el.textContent = `${Math.round(data.new_balance)} pts`;
        });
        // Animation des cotes mises à jour
        if (data.updated_odds) {
          Object.entries(data.updated_odds).forEach(([selId, newOdds]) => {
            const b = document.querySelector(`.odds-btn[data-selection-id="${selId}"]`);
            if (!b) return;
            const oldOdds = parseFloat(b.dataset.odds);
            b.dataset.odds = newOdds;
            const oddsEl = b.querySelector('.odds-value');
            if (oddsEl) {
              oddsEl.textContent        = newOdds.toFixed(2);
              oddsEl.style.transition   = 'color 0.3s';
              oddsEl.style.color        = newOdds < oldOdds ? '#ef4444' : '#22c55e';
              setTimeout(() => { oddsEl.style.color = ''; }, 1400);
            }
          });
        }
        clearSlip();
      } else {
        showToast(data.message, 'error');
      }
    } catch {
      showToast('Erreur réseau. Réessayez.', 'error');
    }

    btn.disabled    = false;
    btn.innerHTML   = '<i class="fa-solid fa-check me-2"></i>Valider le pari';
  }

  // ── Toasts ───────────────────────────────────────────────────────────────────

  function showToast(message, type = 'success') {
    document.querySelectorAll('.tribet-toast').forEach(t => t.remove());
    const toast = document.createElement('div');
    toast.className = `tribet-toast ${type}`;
    const icon = type === 'success'
      ? '<i class="fa-solid fa-check-circle" style="color:var(--green)"></i>'
      : '<i class="fa-solid fa-circle-xmark" style="color:var(--red)"></i>';
    toast.innerHTML = `<div style="display:flex;align-items:center;gap:10px">${icon}<span>${message}</span></div>`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  // ── Auto-dismiss flash messages ──────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', () => {
    init();
    setTimeout(() => {
      document.querySelectorAll('.alert').forEach(a => {
        a.style.transition = 'opacity 0.5s';
        a.style.opacity = '0';
        setTimeout(() => a.remove(), 500);
      });
    }, 4500);
  });

  return { showToast };
})();
