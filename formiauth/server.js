import express from 'express';
import cookieParser from 'cookie-parser';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const AUTH_PASSWORD = process.env.AUTH_PASSWORD || 'formicloud'; // Default password, can be overridden via env
const COOKIE_NAME = 'formiauth_token';
const COOKIE_SECRET = process.env.COOKIE_SECRET || 'secret_token_12345';

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// Serve the Vite frontend in production
app.use(express.static(path.join(__dirname, 'frontend/dist')));

// Endpoint for Nginx auth_request
app.get('/verify', (req, res) => {
    const token = req.cookies[COOKIE_NAME];
    
    if (token === COOKIE_SECRET) {
        return res.status(200).send('OK');
    }
    
    return res.status(401).send('Unauthorized');
});

// Login endpoint
app.post('/api/login', (req, res) => {
    const { password } = req.body;

    if (password === AUTH_PASSWORD) {
        // Set cookie valid across all formicloud.duckdns.org subdomains
        res.cookie(COOKIE_NAME, COOKIE_SECRET, {
            domain: process.env.COOKIE_DOMAIN || '.formicloud.duckdns.org',
            path: '/',
            maxAge: 365 * 24 * 60 * 60 * 1000, // 1 year
            httpOnly: true,
            secure: true, // Only send over HTTPS
            sameSite: 'lax'
        });
        return res.json({ success: true });
    }

    return res.status(401).json({ success: false, message: 'Invalid password' });
});

// For any other route, serve the frontend
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'frontend/dist/index.html'));
});

app.listen(PORT, () => {
    console.log(`FormiAuth server running on port ${PORT}`);
});
