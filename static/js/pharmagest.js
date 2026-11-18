document.addEventListener('DOMContentLoaded', () => {
    const htmlEl = document.documentElement;
    const themeToggleBtn = document.getElementById('pg-theme-toggle');
    const themeIcon = document.getElementById('pg-theme-icon');

    const applyTheme = (theme) => {
        htmlEl.setAttribute('data-bs-theme', theme);
        localStorage.setItem('pharmagest-theme', theme);
        if (themeIcon) {
            themeIcon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
        }
        window.dispatchEvent(new CustomEvent('pharmagest:theme-change', { detail: { theme } }));
    };

    const savedTheme = localStorage.getItem('pharmagest-theme') || 'light';
    applyTheme(savedTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const current = htmlEl.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    }

    // Affichage / masquage du mot de passe (page de connexion et profil)
    document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-toggle-password');
            const input = document.getElementById(targetId);
            const icon = btn.querySelector('i');
            if (!input) return;

            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            if (icon) {
                icon.className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
            }
        });
    });

    // Activation automatique des notifications Toast Bootstrap
    document.querySelectorAll('.pg-toast').forEach((toastEl) => {
        if (window.bootstrap && window.bootstrap.Toast) {
            const toast = new window.bootstrap.Toast(toastEl, { delay: 4500 });
            toast.show();
        }
    });

    // Modale de confirmation globale pour les actions sensibles
    const confirmModalEl = document.getElementById('pgConfirmModal');
    if (confirmModalEl) {
        confirmModalEl.addEventListener('show.bs.modal', (event) => {
            const trigger = event.relatedTarget;
            if (!trigger) return;
            const title = trigger.getAttribute('data-confirm-title') || 'Confirmer l\'action';
            const message = trigger.getAttribute('data-confirm-message') || 'Voulez-vous vraiment continuer ?';
            const actionUrl = trigger.getAttribute('data-confirm-url') || '#';

            document.getElementById('pgConfirmModalTitle').textContent = title;
            document.getElementById('pgConfirmModalMessage').textContent = message;
            const form = document.getElementById('pgConfirmModalForm');
            if (form) form.setAttribute('action', actionUrl);
        });
    }
});