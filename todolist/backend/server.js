const express = require('express');
const path = require('path');
const fs = require('fs');
const PImage = require('pureimage');
const db = require('./database');

let fontLoaded = false;
const fontToUse = 'Roboto';
const fontRoboto = PImage.registerFont(path.join(__dirname, 'Roboto-Regular.ttf'), 'Roboto');

fontRoboto.load().then(() => {
  fontLoaded = true;
  console.log("✅ Roboto font loaded. Image generation ready.");
}).catch(err => {
  console.error("❌ Critical error loading Roboto font:", err);
});

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'frontend')));

// ─── SSE Active Clients ───────────────────────────────────────────────────────
const clients = new Set();

function notifyClients() {
  for (const client of clients) {
    client.write(`data: update\n\n`);
  }
}

// ─── SSE Endpoint ─────────────────────────────────────────────────────────────
app.get('/api/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no'); // Disable Nginx proxy buffering
  res.flushHeaders();

  // Send an initial event to establish the connection immediately
  res.write('data: connected\n\n');

  clients.add(res);

  req.on('close', () => {
    clients.delete(res);
  });
});

// ─── GET all tasks (with optional filters) ───────────────────────────────────
app.get('/api/tasks', (req, res) => {
  const { group, view } = req.query;

  let where = [];
  let params = {};

  if (group) {
    where.push(`group_name = $group`);
    params.group = group;
  }

  if (view === 'today') {
    where.push(`date = date('now')`);
  } else if (view === 'week') {
    where.push(`date != 'none' AND date >= date('now', 'weekday 1', '-7 days') AND date <= date('now', 'weekday 0')`);
  } else if (view === 'month') {
    where.push(`date != 'none' AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')`);
  } else if (view === 'todo') {
    where.push(`date = 'none'`);
  }

  const whereClause = where.length > 0 ? 'WHERE ' + where.join(' AND ') : '';
  const sql = `SELECT * FROM tasks ${whereClause} ORDER BY completed ASC, priority DESC, date ASC`;

  try {
    const tasks = db.prepare(sql).all(params);
    res.json(tasks);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur base de données' });
  }
});

// ─── GET task counts per group ────────────────────────────────────────────────
app.get('/api/tasks/counts', (req, res) => {
  try {
    const rows = db.prepare(`
      SELECT group_name, COUNT(*) as count
      FROM tasks
      WHERE completed = 0
      GROUP BY group_name
    `).all();

    const counts = { samuel: 0, nadia: 0, formicouple: 0 };
    rows.forEach(r => { counts[r.group_name] = r.count; });
    res.json(counts);
  } catch (err) {
    res.status(500).json({ error: 'Erreur base de données' });
  }
});

// ─── POST create task ─────────────────────────────────────────────────────────
app.post('/api/tasks', (req, res) => {
  const { group_name, title, date, priority = 'medium', recurrence = 'none' } = req.body;

  if (!group_name || !title || !date) {
    return res.status(400).json({ error: 'group_name, title et date sont requis' });
  }

  try {
    const stmt = db.prepare(`
      INSERT INTO tasks (group_name, title, date, priority, recurrence)
      VALUES ($group_name, $title, $date, $priority, $recurrence)
    `);
    const result = stmt.run({ group_name, title, date, priority, recurrence });
    const task = db.prepare('SELECT * FROM tasks WHERE id = ?').get(result.lastInsertRowid);
    notifyClients();
    res.status(201).json(task);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur base de données' });
  }
});

// ─── PATCH toggle task complete ───────────────────────────────────────────────
app.patch('/api/tasks/:id/toggle', (req, res) => {
  const { id } = req.params;
  try {
    db.prepare(`UPDATE tasks SET completed = CASE WHEN completed = 0 THEN 1 ELSE 0 END WHERE id = ?`).run(id);

    const task = db.prepare('SELECT * FROM tasks WHERE id = ?').get(id);
    if (!task) return res.status(404).json({ error: 'Tâche introuvable' });

    // Handle recurrence: if completing a recurring task, create next occurrence
    if (task.completed === 1 && task.recurrence !== 'none') {
      const nextDate = getNextDate(task.date, task.recurrence);
      if (nextDate) {
        const existing = db.prepare('SELECT id FROM tasks WHERE group_name = ? AND title = ? AND date = ?').get(task.group_name, task.title, nextDate);
        if (!existing) {
          db.prepare(`
            INSERT INTO tasks (group_name, title, date, priority, recurrence)
            VALUES (?, ?, ?, ?, ?)
          `).run(task.group_name, task.title, nextDate, task.priority, task.recurrence);
        }
      }
    }

    notifyClients();
    res.json(task);
  } catch (err) {
    res.status(500).json({ error: 'Erreur base de données' });
  }
});

// ─── DELETE task ──────────────────────────────────────────────────────────────
app.delete('/api/tasks/:id', (req, res) => {
  const { id } = req.params;
  try {
    const result = db.prepare('DELETE FROM tasks WHERE id = ?').run(id);
    if (result.changes === 0) return res.status(404).json({ error: 'Tâche introuvable' });
    notifyClients();
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Erreur base de données' });
  }
});

// ─── Helper: compute next recurrence date ────────────────────────────────────
function getNextDate(dateStr, recurrence) {
  const d = new Date(dateStr);
  if (isNaN(d)) return null;

  if (recurrence === 'daily')   d.setDate(d.getDate() + 1);
  if (recurrence === 'weekly')  d.setDate(d.getDate() + 7);
  if (recurrence === 'monthly') d.setMonth(d.getMonth() + 1);

  return d.toISOString().split('T')[0];
}

// ─── Helpers for display image ───────────────────────────────────────────────
function getFormattedDate(dateStr) {
  if (!dateStr || dateStr === 'none') return "À faire";
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    const day = parseInt(parts[2], 10);
    const months = ["janv.", "févr.", "mars", "avril", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
    const monthIndex = parseInt(parts[1], 10) - 1;
    if (monthIndex >= 0 && monthIndex < 12) {
      return `${day} ${months[monthIndex]}`;
    }
    return `${parts[2]}/${parts[1]}`;
  }
  return dateStr;
}

function drawRoundedRect(ctx, x, y, width, height, radius, fill, stroke) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
  if (fill) {
    ctx.fillStyle = fill;
    ctx.fill();
  }
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}

function convertBitmapToEInkBin(bitmap) {
  const width = bitmap.width;   // 800
  const height = bitmap.height; // 480
  const buffer = Buffer.alloc((width * height) / 8);

  for (let y = 0; y < height; y++) {
    for (let b = 0; b < width / 8; b++) {
      let byteVal = 0;
      for (let bit = 0; bit < 8; bit++) {
        const x = b * 8 + bit;
        const pixelIdx = (y * width + x) * 4;
        const r = bitmap.data[pixelIdx];
        const g = bitmap.data[pixelIdx + 1];
        const bVal = bitmap.data[pixelIdx + 2];
        
        // Luminance threshold
        const luminance = 0.299 * r + 0.587 * g + 0.114 * bVal;
        const isWhite = luminance > 128 ? 1 : 0;
        
        if (isWhite) {
          byteVal |= (1 << (7 - bit));
        }
      }
      buffer[y * (width / 8) + b] = byteVal;
    }
  }
  return buffer;
}

async function generateDashboardBitmap() {
  const img = PImage.make(800, 480);
  const ctx = img.getContext('2d');

  // Fill white background
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, 800, 480);

  // ─── Draw Header ──────────────────────────────────────────────────────────
  // FormiTodo Title
  ctx.fillStyle = '#000000';
  ctx.font = "28pt '" + fontToUse + "'";
  ctx.textAlign = 'left';
  ctx.fillText("FormiTodo", 40, 46);

  // Current Date
  const now = new Date();
  const days = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
  const months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  const currentDayStr = days[now.getDay()];
  const currentDateStr = `${currentDayStr} ${now.getDate()} ${months[now.getMonth()]}`;
  
  ctx.fillStyle = '#000000';
  ctx.font = "18pt '" + fontToUse + "'";
  ctx.textAlign = 'right';
  ctx.fillText(currentDateStr, 760, 43);

  // Header Divider (sleek thin line)
  ctx.fillStyle = '#000000';
  ctx.fillRect(40, 64, 720, 2);

  // ─── Draw Tasks ───────────────────────────────────────────────────────────
  const paddingX = 40;
  const rowHeight = 60;
  const startY = 70;

  // Get next 6 tasks across all groups
  const tasks = db.prepare(`SELECT * FROM tasks WHERE completed = 0 ORDER BY priority DESC, date ASC LIMIT 6`).all();

  for (let index = 0; index < 6; index++) {
    const task = tasks[index];
    const yTop = startY + index * rowHeight;
    const yCenter = yTop + rowHeight / 2;

    if (task) {
      // 1. Draw Date or Status Pill at X=40 (replacing checkbox and shift left)
      const formattedDate = getFormattedDate(task.date);
      if (task.date && task.date !== 'none') {
        // High-contrast solid black filled pill for dated tasks
        drawRoundedRect(ctx, 40, yCenter - 16, 100, 32, 6, '#000000', null);
        ctx.fillStyle = '#FFFFFF';
        ctx.font = "14pt '" + fontToUse + "'";
        ctx.textAlign = 'center';
        ctx.fillText(formattedDate, 90, yCenter + 6);
      } else {
        // High-contrast outlined black pill for "À faire" (drawn via double-fill to bypass pureimage stroke skew bugs)
        drawRoundedRect(ctx, 40, yCenter - 16, 100, 32, 6, '#000000', null);
        drawRoundedRect(ctx, 42, yCenter - 14, 96, 28, 4, '#FFFFFF', null);
        ctx.fillStyle = '#000000';
        ctx.font = "14pt '" + fontToUse + "'";
        ctx.textAlign = 'center';
        ctx.fillText("À faire", 90, yCenter + 6);
      }

      // 2. Draw Task Title aligned at X=160
      let title = task.title;
      // Truncate to fit on the screen with larger font
      if (title.length > 35) {
        title = title.substring(0, 33) + '...';
      }
      
      ctx.fillStyle = '#000000';
      ctx.font = "22pt '" + fontToUse + "'";
      ctx.textAlign = 'left';
      ctx.fillText(title, 160, yCenter + 8);
    }

    // 3. Draw Row Divider (except the last item)
    if (index < 5) {
      ctx.fillStyle = '#000000';
      ctx.fillRect(40, yTop + rowHeight - 1, 720, 1);
    }
  }

  // ─── Draw Footer ──────────────────────────────────────────────────────────
  // Footer Divider
  ctx.fillStyle = '#000000';
  ctx.fillRect(40, 430, 720, 2);

  // Left status info
  ctx.fillStyle = '#000000';
  ctx.font = "14pt '" + fontToUse + "'";
  ctx.textAlign = 'left';
  ctx.fillText("Système FormiTodo", 40, 460);

  // Right Refresh time
  const hhmm = now.toLocaleTimeString('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit' }).replace('h', ':');
  const refreshText = "Dernière synchro : " + hhmm;
  ctx.textAlign = 'right';
  ctx.fillText(refreshText, 760, 460);

  return img;
}

// ─── GET display image ────────────────────────────────────────────────────────
app.get('/api/display.png', async (req, res) => {
  if (!fontLoaded) {
    return res.status(503).send('Image generation not ready');
  }

  try {
    const img = await generateDashboardBitmap();
    res.setHeader('Content-Type', 'image/png');
    await PImage.encodePNGToStream(img, res);
  } catch (err) {
    console.error(err);
    res.status(500).send('Erreur génération image');
  }
});

// ─── Rendu de l'écran todo, utilisé par FormiInk (réseau interne uniquement) ──
app.get('/api/render/todo.png', async (req, res) => {
  if (!fontLoaded) return res.status(503).send('Image generation not ready');
  try {
    const img = await generateDashboardBitmap();
    res.setHeader('Content-Type', 'image/png');
    await PImage.encodePNGToStream(img, res);
  } catch (err) {
    console.error(err);
    res.status(500).send('Erreur génération image');
  }
});

app.get('/api/render/todo.bin', async (req, res) => {
  if (!fontLoaded) return res.status(503).send('Image generation not ready');
  try {
    const img = await generateDashboardBitmap();
    res.setHeader('Content-Type', 'application/octet-stream');
    res.send(convertBitmapToEInkBin(img));
  } catch (err) {
    console.error(err);
    res.status(500).send('Erreur génération image binaire');
  }
});

// ─── GET display bin (E-ink 1-bit buffer) ─────────────────────────────────────
// L'écran appelle toujours cette URL. FormiInk (INK_URL) choisit ce qui s'affiche ;
// s'il est arrêté ou en erreur, on retombe sur l'écran todo pour ne jamais laisser l'écran vide.
const INK_URL = process.env.INK_URL;
const EINK_BIN_SIZE = (800 * 480) / 8;

app.get('/api/display.bin', async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');

  if (INK_URL) {
    try {
      const inkRes = await fetch(`${INK_URL}/display.bin`, { signal: AbortSignal.timeout(8000) });
      if (inkRes.ok) {
        const buffer = Buffer.from(await inkRes.arrayBuffer());
        if (buffer.length === EINK_BIN_SIZE) {
          res.setHeader('Content-Type', 'application/octet-stream');
          return res.send(buffer);
        }
        console.error(`FormiInk a renvoyé ${buffer.length} octets au lieu de ${EINK_BIN_SIZE}`);
      } else {
        console.error(`FormiInk HTTP ${inkRes.status}`);
      }
    } catch (err) {
      console.error('FormiInk injoignable, secours sur l\'écran todo:', err.message);
    }
  }

  if (!fontLoaded) {
    return res.status(503).send('Image generation not ready');
  }

  try {
    const img = await generateDashboardBitmap();
    res.setHeader('Content-Type', 'application/octet-stream');
    res.send(convertBitmapToEInkBin(img));
  } catch (err) {
    console.error(err);
    res.status(500).send('Erreur génération image binaire');
  }
});

// ─── Fallback: serve frontend ─────────────────────────────────────────────────
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'frontend', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`✅ FormiTodo running on port ${PORT}`);
});
