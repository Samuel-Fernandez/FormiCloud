// Synchronisation temps réel : si quelqu'un d'autre modifie les données, la page se rafraîchit.
(function liveSync() {
    const POLL_MS = 2000;
    let knownVersion = document.body.dataset.version;
    let dragging = false;

    if (!knownVersion) return;

    // Nos propres modifications mettent à jour la version connue (pas de rechargement inutile)
    const originalFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
        const isWrite = init && init.method && init.method.toUpperCase() === 'POST';
        return originalFetch(input, init).then(response => {
            const version = response.headers.get('X-Data-Version');
            if (isWrite && version) knownVersion = version;
            return response;
        });
    };

    document.addEventListener('dragstart', () => { dragging = true; });
    document.addEventListener('dragend', () => { dragging = false; });

    // Ne pas recharger si l'utilisateur est en train de saisir, de glisser un plat ou a une fenêtre ouverte
    function isBusy() {
        const el = document.activeElement;
        if (el && ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return true;
        if (dragging) return true;
        return [...document.querySelectorAll('.modal')].some(m => getComputedStyle(m).display !== 'none');
    }

    async function check() {
        if (document.hidden) return;
        try {
            const res = await originalFetch('/api/version', { cache: 'no-store' });
            const { version } = await res.json();
            if (version !== knownVersion && !isBusy()) {
                window.location.reload();
            }
        } catch (err) {
            // Serveur injoignable : on réessaiera au prochain tick
        }
    }

    setInterval(check, POLL_MS);
    document.addEventListener('visibilitychange', check);
})();
