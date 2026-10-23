const path = require('path');
const { PassThrough } = require('stream');
const PImage = require('pureimage');

const W = 800;
const H = 480;
const TZ = 'Europe/Zurich';
const FONT = 'Roboto';

const TODO_URL = process.env.TODO_URL || 'http://formitodo:3000';
const BUS_API = 'https://transport.opendata.ch/v1/stationboard';

let fontLoaded = false;
const fontReady = PImage.registerFont(path.join(__dirname, 'Roboto-Regular.ttf'), FONT)
  .load()
  .then(() => { fontLoaded = true; console.log('✅ Roboto font loaded.'); })
  .catch(err => { console.error('❌ Roboto font load failed:', err); throw err; });

// ─── Bitmap helpers ──────────────────────────────────────────────────────────
function toBin(bitmap) {
  const buffer = Buffer.alloc((W * H) / 8);
  for (let y = 0; y < H; y++) {
    for (let b = 0; b < W / 8; b++) {
      let byteVal = 0;
      for (let bit = 0; bit < 8; bit++) {
        const i = (y * W + b * 8 + bit) * 4;
        const luminance = 0.299 * bitmap.data[i] + 0.587 * bitmap.data[i + 1] + 0.114 * bitmap.data[i + 2];
        if (luminance > 128) byteVal |= 1 << (7 - bit);
      }
      buffer[y * (W / 8) + b] = byteVal;
    }
  }
  return buffer;
}

async function toPng(bitmap) {
  const stream = new PassThrough();
  const chunks = [];
  stream.on('data', c => chunks.push(c));
  await PImage.encodePNGToStream(bitmap, stream);
  return Buffer.concat(chunks);
}

function roundedRect(ctx, x, y, w, h, r, fill) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();
}

function clock(date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false
  }).formatToParts(date);
  const get = type => parts.find(p => p.type === type).value;
  return `${get('hour')}:${get('minute')}`;
}

function truncate(text, max) {
  return text.length > max ? text.substring(0, max - 3) + '...' : text;
}

// ─── Bus (transport.opendata.ch) ─────────────────────────────────────────────
let busCache = { key: '', at: 0, data: null };

async function fetchDepartures(cfg) {
  const key = JSON.stringify([cfg.station, cfg.line, cfg.destination]);
  if (busCache.key === key && Date.now() - busCache.at < 20000) return busCache.data;

  try {
    const url = `${BUS_API}?station=${encodeURIComponent(cfg.station)}&limit=100&transportations[]=bus&transportations[]=tram`;
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();

    const wantedLine = String(cfg.line || '').trim().toLowerCase();
    const wantedDest = String(cfg.destination || '').trim().toLowerCase();

    const departures = (json.stationboard || [])
      .filter(e => !wantedLine || String(e.number || '').trim().toLowerCase() === wantedLine)
      .filter(e => !wantedDest || String(e.to || '').toLowerCase().startsWith(wantedDest))
      .map(e => {
        // La prévision temps réel prime sur l'horaire théorique
        const when = new Date((e.prognosis && e.prognosis.departure) || e.stop.departure);
        return { when, delay: e.stop.delay || 0, to: e.to, line: e.number };
      })
      .filter(d => !isNaN(d.when))
      .sort((a, b) => a.when - b.when);

    busCache = { key, at: Date.now(), data: { ok: true, departures, station: json.station && json.station.name } };
  } catch (err) {
    console.error('Bus API error:', err.message);
    // Données un peu périmées plutôt qu'un écran vide, tant qu'elles ont moins de 10 min
    if (busCache.key === key && busCache.data && Date.now() - busCache.at < 10 * 60 * 1000) return busCache.data;
    return { ok: false, departures: [] };
  }
  return busCache.data;
}

async function drawBus(cfg) {
  await fontReady;
  const bus = cfg.bus;
  const data = await fetchDepartures(bus);
  const now = new Date();

  const img = PImage.make(W, H);
  const ctx = img.getContext('2d');
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#000000';

  // En-tête
  ctx.font = `28pt '${FONT}'`;
  ctx.textAlign = 'left';
  ctx.fillText(`Bus ${bus.line || ''}`.trim(), 40, 46);
  ctx.font = `16pt '${FONT}'`;
  ctx.textAlign = 'right';
  const stationShort = (bus.station || '').replace(/^[^,]+,\s*/, '');
  ctx.fillText(truncate(`${stationShort}${bus.destination ? ' > ' + bus.destination : ''}`, 38), 760, 43);
  ctx.fillRect(40, 64, 720, 2);

  // Départs
  const rows = Math.min(Math.max(parseInt(bus.count, 10) || 6, 1), 6);
  const rowHeight = 60;
  const startY = 70;
  const upcoming = data.departures.filter(d => d.when.getTime() - now.getTime() > -30000).slice(0, rows);

  if (upcoming.length === 0) {
    ctx.textAlign = 'center';
    ctx.font = `22pt '${FONT}'`;
    ctx.fillText(data.ok ? 'Aucun départ prévu' : 'Horaires indisponibles', W / 2, 250);
  }

  upcoming.forEach((d, index) => {
    const yTop = startY + index * rowHeight;
    const yCenter = yTop + rowHeight / 2;
    const minutes = Math.round((d.when.getTime() - now.getTime()) / 60000);

    roundedRect(ctx, 40, yCenter - 16, 100, 32, 6, '#000000');
    ctx.fillStyle = '#FFFFFF';
    ctx.font = `14pt '${FONT}'`;
    ctx.textAlign = 'center';
    ctx.fillText(minutes <= 0 ? 'Départ' : `${minutes} min`, 90, yCenter + 6);

    ctx.fillStyle = '#000000';
    ctx.font = `22pt '${FONT}'`;
    ctx.textAlign = 'left';
    ctx.fillText(clock(d.when), 160, yCenter + 8);
    ctx.fillText(truncate(d.to, 24), 290, yCenter + 8);

    if (d.delay > 0) {
      ctx.font = `16pt '${FONT}'`;
      ctx.textAlign = 'right';
      ctx.fillText(`+${d.delay} min`, 760, yCenter + 6);
    }

    if (index < rows - 1) ctx.fillRect(40, yTop + rowHeight - 1, 720, 1);
  });

  // Pied de page
  ctx.fillStyle = '#000000';
  ctx.fillRect(40, 430, 720, 2);
  ctx.font = `14pt '${FONT}'`;
  ctx.textAlign = 'left';
  ctx.fillText('FormiInk · TL', 40, 460);
  ctx.textAlign = 'right';
  ctx.fillText(`Mis à jour : ${clock(now)}`, 760, 460);

  return img;
}

// ─── Todo : rendu fourni par FormiTodo ───────────────────────────────────────
async function fetchTodo(ext) {
  const res = await fetch(`${TODO_URL}/api/render/todo.${ext}`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`FormiTodo HTTP ${res.status}`);
  return Buffer.from(await res.arrayBuffer());
}

// ─── Registre des écrans ─────────────────────────────────────────────────────
// Pour ajouter un écran : une entrée avec un id, un libellé, et deux fonctions bin / png.
const screens = {
  todo: {
    label: 'Todo list',
    description: 'Les prochaines tâches de FormiTodo',
    bin: () => fetchTodo('bin'),
    png: () => fetchTodo('png'),
  },
  bus: {
    label: 'Départs de bus',
    description: 'Les prochains départs d\'une ligne (transport.opendata.ch)',
    bin: async cfg => toBin(await drawBus(cfg)),
    png: async cfg => toPng(await drawBus(cfg)),
  },
};

module.exports = { screens, W, H };
