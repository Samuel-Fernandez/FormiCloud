/* ─────────────────────────────────────────────────────────────────────────────
   FormiTodo — app.js
   ───────────────────────────────────────────────────────────────────────────── */

// ─── State ───────────────────────────────────────────────────────────────────
const state = {
  group: 'formicouple',
  view: 'today',
  tasks: [],
  priority: 'medium',
};

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const sidebar       = document.getElementById('sidebar');
const overlay       = document.getElementById('overlay');
const hamburger     = document.getElementById('hamburger');
const menuToggle    = document.getElementById('menuToggle');
const taskList      = document.getElementById('taskList');
const emptyState    = document.getElementById('emptyState');
const topbarTitle   = document.getElementById('topbarTitle');
const topbarSub     = document.getElementById('topbarSub');
const todayDate     = document.getElementById('todayDate');
const modalBackdrop = document.getElementById('modalBackdrop');
const taskForm      = document.getElementById('taskForm');
const taskTitle     = document.getElementById('taskTitle');
const taskDate      = document.getElementById('taskDate');
const taskRecurrence= document.getElementById('taskRecurrence');
const toast         = document.getElementById('toast');

const GROUPS = {
  samuel:      { label: 'Samuel',      sub: 'Vos tâches personnelles' },
  nadia:       { label: 'Nadia',       sub: 'Vos tâches personnelles' },
  formicouple: { label: 'Formicouple', sub: 'Tâches partagées du couple' },
};

const RECURRENCE_LABELS = {
  none: null,
  daily: '↺ Quotidienne',
  weekly: '↺ Hebdomadaire',
  monthly: '↺ Mensuelle',
};

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderDate();
  setDefaultDate();
  loadTasks();
  loadCounts();
  bindEvents();
  setupSSE();
});

// ─── Real-time Sync (SSE) ─────────────────────────────────────────────────────
function setupSSE() {
  const eventSource = new EventSource('/api/events');
  eventSource.onmessage = (event) => {
    if (event.data === 'update') {
      loadTasks();
      loadCounts();
    }
  };
  eventSource.onerror = (err) => {
    console.error('Erreur SSE, reconnexion automatique...', err);
  };
}

function renderDate() {
  const now = new Date();
  todayDate.textContent = now.toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
}

function setDefaultDate() {
  const today = new Date().toISOString().split('T')[0];
  taskDate.value = today;
}

// ─── Events ───────────────────────────────────────────────────────────────────
function bindEvents() {
  // Sidebar toggle (mobile)
  hamburger.addEventListener('click', openSidebar);
  menuToggle.addEventListener('click', closeSidebar);
  overlay.addEventListener('click', closeSidebar);

  // Group tabs
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const g = btn.dataset.group;
      switchGroup(g);
      if (window.innerWidth <= 768) closeSidebar();
    });
  });

  // View tabs
  document.querySelectorAll('.view-tab').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  // Open modal
  document.getElementById('btnAddTop').addEventListener('click', openModal);

  // Close modal
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('btnCancel').addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', e => {
    if (e.target === modalBackdrop) closeModal();
  });

  // Priority buttons
  document.querySelectorAll('.priority-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.priority = btn.dataset.priority;
    });
  });

  // Form submit
  taskForm.addEventListener('submit', handleAddTask);

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); openModal(); }
  });
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function openSidebar()  { sidebar.classList.add('open'); overlay.classList.add('open'); }
function closeSidebar() { sidebar.classList.remove('open'); overlay.classList.remove('open'); }

// ─── Group / View switch ──────────────────────────────────────────────────────
function switchGroup(group) {
  state.group = group;
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.group === group));
  topbarTitle.textContent = GROUPS[group].label;
  topbarSub.textContent   = GROUPS[group].sub;
  loadTasks();
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll('.view-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.view === view);
    b.setAttribute('aria-selected', b.dataset.view === view);
  });
  loadTasks();
}

// ─── API calls ────────────────────────────────────────────────────────────────
async function loadTasks() {
  try {
    const params = new URLSearchParams({ group: state.group, view: state.view });
    const res = await fetch(`/api/tasks?${params}`);
    if (!res.ok) throw new Error('Erreur réseau');
    state.tasks = await res.json();
    renderTasks();
    renderStats();
  } catch (err) {
    console.error(err);
    showToast('Erreur lors du chargement des tâches');
  }
}

async function loadCounts() {
  try {
    const res = await fetch('/api/tasks/counts');
    const counts = await res.json();
    ['samuel', 'nadia', 'formicouple'].forEach(g => {
      const badge = document.getElementById(`badge-${g}`);
      if (badge) {
        badge.textContent = counts[g] || 0;
        badge.dataset.count = counts[g] || 0;
      }
    });
  } catch (err) { console.error(err); }
}

async function handleAddTask(e) {
  e.preventDefault();

  const title = taskTitle.value.trim();
  const date  = taskDate.value || 'none';

  if (!title) { taskTitle.focus(); return; }

  const body = {
    group_name: state.group,
    title,
    date,
    priority: state.priority,
    recurrence: taskRecurrence.value,
  };

  const btnSubmit = document.getElementById('btnSubmit');
  if (btnSubmit) btnSubmit.disabled = true;

  try {
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error();
    closeModal();
    showToast('Tâche ajoutée ✓');
    loadTasks();
    loadCounts();
  } catch (err) {
    showToast('Erreur lors de l\'ajout');
  } finally {
    if (btnSubmit) btnSubmit.disabled = false;
  }
}

async function toggleTask(id) {
  try {
    await fetch(`/api/tasks/${id}/toggle`, { method: 'PATCH' });
    loadTasks();
    loadCounts();
  } catch (err) {
    showToast('Erreur lors de la mise à jour');
  }
}

async function deleteTask(id) {
  try {
    await fetch(`/api/tasks/${id}`, { method: 'DELETE' });
    // Animate removal
    const card = document.getElementById(`task-${id}`);
    if (card) {
      card.style.transition = 'opacity 200ms, transform 200ms';
      card.style.opacity = '0';
      card.style.transform = 'translateX(10px)';
      setTimeout(() => { loadTasks(); loadCounts(); }, 200);
    } else {
      loadTasks();
      loadCounts();
    }
    showToast('Tâche supprimée');
  } catch (err) {
    showToast('Erreur lors de la suppression');
  }
}

// ─── Render ───────────────────────────────────────────────────────────────────
function renderTasks() {
  // Clear previous tasks (keep empty state)
  const existing = taskList.querySelectorAll('.task-card, .date-group-label');
  existing.forEach(el => el.remove());

  if (state.tasks.length === 0) {
    emptyState.style.display = 'flex';
    return;
  }
  emptyState.style.display = 'none';

  // Group by date
  const byDate = {};
  state.tasks.forEach(t => {
    if (!byDate[t.date]) byDate[t.date] = [];
    byDate[t.date].push(t);
  });

  const sortedDates = Object.keys(byDate).sort();

  sortedDates.forEach(date => {
    // Date label
    const label = document.createElement('p');
    label.className = 'date-group-label';
    label.textContent = formatGroupDate(date);
    taskList.appendChild(label);

    byDate[date].forEach(task => {
      taskList.appendChild(createTaskCard(task));
    });
  });
}

function createTaskCard(task) {
  const card = document.createElement('div');
  card.className = `task-card${task.completed ? ' completed' : ''}`;
  card.id = `task-${task.id}`;

  const today = new Date().toISOString().split('T')[0];
  const isOverdue = task.date !== 'none' && task.date < today && !task.completed;
  const recLabel = RECURRENCE_LABELS[task.recurrence];

  card.innerHTML = `
    <button class="task-check" aria-label="${task.completed ? 'Marquer comme non-complété' : 'Marquer comme complété'}" data-id="${task.id}">
      <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
        <path d="M1 4.5L4 7.5L10 1" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
    <div class="task-body">
      <p class="task-title">${escapeHtml(task.title)}</p>
      <div class="task-meta">
        <span class="task-date${isOverdue ? ' overdue' : ''}">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><rect x="1" y="2" width="9" height="8" rx="1.5" stroke="currentColor" stroke-width="1.2"/><path d="M3.5 1v2M7.5 1v2M1 5h9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
          ${isOverdue ? '⚠ ' : ''}${formatDate(task.date)}
        </span>
        <span class="task-prio ${task.priority}">${prioLabel(task.priority)}</span>
        ${recLabel ? `<span class="task-recurrence">${recLabel}</span>` : ''}
      </div>
    </div>
    <button class="task-delete" aria-label="Supprimer la tâche" data-id="${task.id}">
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M2 4h11M5 4V3a1 1 0 011-1h3a1 1 0 011 1v1M6 7v4M9 7v4M3 4l1 8a1 1 0 001 1h5a1 1 0 001-1l1-8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  `;

  card.querySelector('.task-check').addEventListener('click', () => toggleTask(task.id));
  card.querySelector('.task-delete').addEventListener('click', () => deleteTask(task.id));

  return card;
}

function renderStats() {
  const total   = state.tasks.length;
  const done    = state.tasks.filter(t => t.completed).length;
  const pending = total - done;

  document.querySelector('#stat-total .stat-num').textContent   = total;
  document.querySelector('#stat-done .stat-num').textContent    = done;
  document.querySelector('#stat-pending .stat-num').textContent = pending;
}

// ─── Modal ────────────────────────────────────────────────────────────────────
function openModal() {
  taskForm.reset();
  setDefaultDate();
  state.priority = 'medium';
  document.querySelectorAll('.priority-btn').forEach(b => b.classList.toggle('active', b.dataset.priority === 'medium'));
  taskRecurrence.value = 'none';
  modalBackdrop.classList.add('open');
  setTimeout(() => taskTitle.focus(), 50);
}

function closeModal() {
  modalBackdrop.classList.remove('open');
}

// ─── Toast ────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function formatDate(dateStr) {
  if (dateStr === 'none') return 'Sans date';
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date(); today.setHours(0,0,0,0);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);

  if (d.getTime() === today.getTime())    return "Aujourd'hui";
  if (d.getTime() === tomorrow.getTime()) return 'Demain';

  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

function formatGroupDate(dateStr) {
  if (dateStr === 'none') return 'À faire';
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date(); today.setHours(0,0,0,0);
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);

  if (d.getTime() === today.getTime())    return "Aujourd'hui";
  if (d.getTime() === tomorrow.getTime()) return 'Demain';

  return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
}

function prioLabel(p) {
  return { low: 'Basse', medium: 'Moyenne', high: 'Haute' }[p] || p;
}

function escapeHtml(str) {
  const el = document.createElement('div');
  el.appendChild(document.createTextNode(str));
  return el.innerHTML;
}
