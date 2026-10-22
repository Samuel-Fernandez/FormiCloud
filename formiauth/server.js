import express from 'express';
import cookieParser from 'cookie-parser';
import crypto from 'crypto';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const COOKIE_NAME = 'formiauth_token';
const SESSION_DAYS = 30;

// Pas de valeur par défaut : un secret absent ne doit jamais ouvrir l'accès avec une valeur publique.
const AUTH_PASSWORD = process.env.AUTH_PASSWORD;
const COOKIE_SECRET = process.env.COOKIE_SECRET;
if (!AUTH_PASSWORD || !COOKIE_SECRET) {
    console.error('AUTH_PASSWORD et COOKIE_SECRET sont obligatoires.');
    process.exit(1);
}
if (COOKIE_SECRET.length < 32) {
    console.error('COOKIE_SECRET doit faire au moins 32 caractères (ex: openssl rand -hex 32).');
    process.exit(1);
}

// Derrière Nginx Proxy Manager : req.ip doit être l'IP réelle du client (X-Forwarded-For)
app.set('trust proxy', 1);

app.use(express.json({ limit: '1kb' }));
app.use(express.urlencoded({ extended: true, limit: '1kb' }));
app.use(cookieParser());

// --- Sessions signées -------------------------------------------------------
// Jeton = <expiration>.<aléa>.<signature HMAC>. Il expire et n'est pas le secret lui-même :
// un cookie volé ne donne pas le secret, et changer COOKIE_SECRET révoque toutes les sessions.
function sign(payload) {
    return crypto.createHmac('sha256', COOKIE_SECRET).update(payload).digest('base64url');
}

function createSessionToken() {
    const exp = Date.now() + SESSION_DAYS * 24 * 60 * 60 * 1000;
    const payload = `${exp}.${crypto.randomBytes(16).toString('base64url')}`;
    return `${payload}.${sign(payload)}`;
}

function safeEqual(a, b) {
    // Hash des deux côtés : longueur identique, comparaison en temps constant
    const ha = crypto.createHash('sha256').update(String(a)).digest();
    const hb = crypto.createHash('sha256').update(String(b)).digest();
    return crypto.timingSafeEqual(ha, hb);
}

function isValidToken(token) {
    if (typeof token !== 'string') return false;
    const parts = token.split('.');
    if (parts.length !== 3) return false;
    const [exp, nonce, signature] = parts;
    if (!safeEqual(signature, sign(`${exp}.${nonce}`))) return false;
    return Number(exp) > Date.now();
}

// --- Limitation des essais de connexion -------------------------------------
const MAX_FAILURES = 5;
const WINDOW_MS = 15 * 60 * 1000;
const failures = new Map(); // ip -> { count, resetAt }

function lockedFor(ip) {
    const entry = failures.get(ip);
    if (!entry) return 0;
    if (entry.resetAt <= Date.now()) {
        failures.delete(ip);
        return 0;
    }
    return entry.count >= MAX_FAILURES ? entry.resetAt - Date.now() : 0;
}

function recordFailure(ip) {
    const now = Date.now();
    const entry = failures.get(ip);
    if (!entry || entry.resetAt <= now) {
        failures.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    } else {
        entry.count += 1;
    }
}

// Nettoyage périodique pour ne pas faire grossir la mémoire
setInterval(() => {
    const now = Date.now();
    for (const [ip, entry] of failures) {
        if (entry.resetAt <= now) failures.delete(ip);
    }
}, 5 * 60 * 1000).unref();

// Serve the Vite frontend in production
app.use(express.static(path.join(__dirname, 'frontend/dist')));

// Endpoint for Nginx auth_request
app.get('/verify', (req, res) => {
    if (isValidToken(req.cookies[COOKIE_NAME])) {
        return res.status(200).send('OK');
    }
    return res.status(401).send('Unauthorized');
});

// Login endpoint
app.post('/api/login', async (req, res) => {
    const ip = req.ip;

    const wait = lockedFor(ip);
    if (wait > 0) {
        res.set('Retry-After', String(Math.ceil(wait / 1000)));
        return res.status(429).json({
            success: false,
            message: `Trop d'essais. Réessaie dans ${Math.ceil(wait / 60000)} min.`
        });
    }

    const { password } = req.body || {};

    if (typeof password === 'string' && safeEqual(password, AUTH_PASSWORD)) {
        failures.delete(ip);
        // Cookie valable pour tous les sous-domaines (COOKIE_DOMAIN = .<DOMAIN>)
        res.cookie(COOKIE_NAME, createSessionToken(), {
            domain: process.env.COOKIE_DOMAIN,
            path: '/',
            maxAge: SESSION_DAYS * 24 * 60 * 60 * 1000,
            httpOnly: true,
            secure: true, // Only send over HTTPS
            sameSite: 'lax'
        });
        return res.json({ success: true });
    }

    recordFailure(ip);
    // Petit délai pour ralentir encore l'énumération
    await new Promise(resolve => setTimeout(resolve, 500));
    return res.status(401).json({ success: false, message: 'Mot de passe incorrect' });
});

// Déconnexion (supprime le cookie sur tous les sous-domaines)
app.post('/api/logout', (req, res) => {
    res.clearCookie(COOKIE_NAME, { domain: process.env.COOKIE_DOMAIN, path: '/' });
    res.json({ success: true });
});

// For any other route, serve the frontend
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'frontend/dist/index.html'));
});

app.listen(PORT, () => {
    console.log(`FormiAuth server running on port ${PORT}`);
});
