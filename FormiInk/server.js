const express = require('express');
const fs = require('fs');
const path = require('path');
const { screens } = require('./screens');

const app = express();
const PORT = process.env.PORT || 3000;
const CONFIG_FILE = path.join(__dirname, 'data', 'config.json');

const DEFAULT_CONFIG = {
  active: 'todo',
  bus: {
    station: 'Lausanne, Pont-de-Chailly',
    line: '7',
    destination: 'Prilly',
    count: 6,
  },
};

// ─── Configuration persistante ───────────────────────────────────────────────
function loadConfig() {
  try {
    const saved = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    return { ...DEFAULT_CONFIG, ...saved, bus: { ...DEFAULT_CONFIG.bus, ...(saved.bus || {}) } };
  } catch {
    return structuredClone(DEFAULT_CONFIG);
  }
}

function saveConfig(config) {
  fs.mkdirSync(path.dirname(CONFIG_FILE), { recursive: true });
  const tmp = CONFIG_FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
  fs.renameSync(tmp, CONFIG_FILE);
}

function cleanText(value, max = 80) {
  return String(value ?? '').trim().slice(0, max);
}

app.use(express.json({ limit: '5kb' }));
app.use(express.static(path.join(__dirname, 'public')));

// ─── Ce que lit l'écran (appelé par FormiTodo) ───────────────────────────────
app.get('/display.bin', async (req, res) => {
  const config = loadConfig();
  const screen = screens[config.active] || screens.todo;
  try {
    const bin = await screen.bin(config);
    res.set('Cache-Control', 'no-store');
    res.type('application/octet-stream').send(bin);
  } catch (err) {
    console.error(`Rendu "${config.active}" impossible:`, err.message);
    res.status(502).send('Rendu indisponible');
  }
});

// ─── API de l'interface ──────────────────────────────────────────────────────
app.get('/api/screens', (req, res) => {
  res.json(Object.entries(screens).map(([id, s]) => ({ id, label: s.label, description: s.description })));
});

app.get('/api/config', (req, res) => res.json(loadConfig()));

app.post('/api/config', (req, res) => {
  const body = req.body || {};
  const config = loadConfig();

  if (body.active !== undefined) {
    if (!screens[body.active]) return res.status(400).json({ error: 'Écran inconnu' });
    config.active = body.active;
  }
  if (body.bus && typeof body.bus === 'object') {
    config.bus = {
      station: cleanText(body.bus.station) || config.bus.station,
      line: cleanText(body.bus.line, 10),
      destination: cleanText(body.bus.destination),
      count: Math.min(Math.max(parseInt(body.bus.count, 10) || 6, 1), 6),
    };
  }
  saveConfig(config);
  res.json(config);
});

app.get('/api/preview.png', async (req, res) => {
  const config = loadConfig();
  const screen = screens[req.query.screen || config.active];
  if (!screen) return res.status(404).send('Écran inconnu');
  try {
    const png = await screen.png(config);
    res.set('Cache-Control', 'no-store');
    res.type('image/png').send(png);
  } catch (err) {
    console.error('Aperçu impossible:', err.message);
    res.status(502).send('Aperçu indisponible');
  }
});

// Autocomplétion des arrêts
app.get('/api/stations', async (req, res) => {
  const q = cleanText(req.query.q, 60);
  if (q.length < 2) return res.json([]);
  try {
    const r = await fetch(`https://transport.opendata.ch/v1/locations?type=station&query=${encodeURIComponent(q)}`,
      { signal: AbortSignal.timeout(6000) });
    const json = await r.json();
    res.json((json.stations || []).slice(0, 8).map(s => s.name).filter(Boolean));
  } catch {
    res.json([]);
  }
});

app.get('/health', (req, res) => res.send('ok'));

app.listen(PORT, () => console.log(`✅ FormiInk running on port ${PORT}`));
