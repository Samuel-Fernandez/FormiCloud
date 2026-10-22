const express = require('express');
const { OpenAI } = require('openai');
const path = require('path');

const app = express();
const PORT = 1000;

// OpenAI client
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY
});

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// API: Generate words from a theme
app.post('/api/generate-words', async (req, res) => {
    const { theme } = req.body;

    if (!theme || typeof theme !== 'string' || theme.trim().length === 0) {
        return res.status(400).json({ error: 'Un thème est requis.' });
    }

    try {
        const completion = await openai.chat.completions.create({
            model: 'gpt-4o-mini',
            temperature: 1.0,
            max_tokens: 4000,
            messages: [
                {
                    role: 'system',
                    content: `Tu es un générateur de mots pour un jeu de devinettes (type "Heads Up!" / "GuessUp").
Le joueur met le téléphone sur son front et ses amis doivent lui faire deviner le mot affiché.

RÈGLES STRICTES :
- Génère exactement 100 mots/noms en rapport avec le thème donné.
- Les mots doivent être variés : du très facile au plus difficile.
- Pas de doublons.
- Réponds UNIQUEMENT avec un tableau JSON de 100 chaînes de caractères.
- Pas d'explication, pas de texte avant ou après, juste le JSON.
- Les mots doivent être en français (sauf si le thème implique des noms propres étrangers).
- Format: ["mot1", "mot2", "mot3", ...]`
                },
                {
                    role: 'user',
                    content: `Thème: "${theme.trim()}"`
                }
            ]
        });

        const content = completion.choices[0].message.content.trim();

        // Parse the JSON array from the response
        let words;
        try {
            // Try to extract JSON array even if there's surrounding text
            const jsonMatch = content.match(/\[[\s\S]*\]/);
            if (jsonMatch) {
                words = JSON.parse(jsonMatch[0]);
            } else {
                throw new Error('No JSON array found');
            }
        } catch (parseError) {
            console.error('Failed to parse OpenAI response:', content);
            return res.status(500).json({ error: 'Erreur lors de la génération des mots. Réessayez.' });
        }

        // Validate
        if (!Array.isArray(words) || words.length < 10) {
            return res.status(500).json({ error: 'Pas assez de mots générés. Réessayez.' });
        }

        // Ensure all items are strings
        words = words.filter(w => typeof w === 'string' && w.trim().length > 0).map(w => w.trim());

        console.log(`Generated ${words.length} words for theme: "${theme}"`);
        res.json({ words });

    } catch (error) {
        console.error('OpenAI API error:', error.message);

        if (error.status === 401) {
            return res.status(500).json({ error: 'Clé API OpenAI invalide.' });
        }
        if (error.status === 429) {
            return res.status(500).json({ error: 'Trop de requêtes. Attendez un moment.' });
        }

        res.status(500).json({ error: 'Erreur serveur. Réessayez.' });
    }
});

// SPA fallback
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`FormiGuessUp server running on port ${PORT}`);
    console.log(`OpenAI API Key: ${process.env.OPENAI_API_KEY ? '✓ configured' : '✗ MISSING'}`);
});
