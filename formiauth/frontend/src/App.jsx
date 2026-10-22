import { useState, useEffect } from 'react';
import './index.css';

function App() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [redirectUrl, setRedirectUrl] = useState('');

  useEffect(() => {
    // Check if there's a redirect URL in the query parameters
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect');
    // N'accepter qu'un retour vers un sous-domaine de FormiCloud (évite la redirection ouverte)
    if (redirect) {
      try {
        const target = new URL(redirect);
        const parent = window.location.hostname.split('.').slice(1).join('.');
        const sameFamily = target.hostname === parent || target.hostname.endsWith('.' + parent);
        if (target.protocol === 'https:' && sameFamily) {
          setRedirectUrl(target.href);
        }
      } catch {
        // URL invalide : on ignore
      }
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ password }),
      });

      const data = await response.json();

      if (data.success) {
        // Redirect back to the requested app, or default to formicloud
        if (redirectUrl) {
          window.location.href = redirectUrl;
        } else {
          window.location.href = 'https://' + window.location.hostname.split('.').slice(1).join('.');
        }
      } else {
        setError(data.message || 'Mot de passe incorrect');
      }
    } catch (err) {
      setError('Erreur de connexion au serveur');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-background">
        <div className="blob blob-1"></div>
        <div className="blob blob-2"></div>
        <div className="blob blob-3"></div>
      </div>
      
      <div className="auth-card">
        <div className="auth-header">
          <div className="logo-container">
            <span className="logo-text">Formi</span>
            <span className="logo-highlight">Auth</span>
          </div>
          <p className="auth-subtitle">Accès sécurisé à l'écosystème FormiCloud</p>
        </div>

        <form onSubmit={handleLogin} className="auth-form">
          <div className="input-group">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mot de passe"
              required
              className={error ? 'input-error' : ''}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="login-button">
            {loading ? <span className="loader"></span> : 'Connexion'}
          </button>
        </form>

        <div className="auth-footer">
          <p>Authentification unique par appareil</p>
        </div>
      </div>
    </div>
  );
}

export default App;
