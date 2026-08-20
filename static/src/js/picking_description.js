/** @odoo-module **/

function applyPickingDescFusion() {
    // Solo actuar si hay celdas de picking en pantalla
    const rows = document.querySelectorAll('.o_data_row');
    if (!rows.length) return;
    const firstDesc = document.querySelector('td[name="description_picking"]');
    if (!firstDesc) return;

    rows.forEach(row => {
        const p = row.querySelector('td[name="product_id"]');
        const d = row.querySelector('td[name="description_picking"]');
        if (!p || !d) return;
        if (p.querySelector('.o_picking_desc_injected')) return;
        const t = (d.innerText || '').trim();
        const pt = (p.innerText || '').trim();
        if (t && t !== pt) {
            const el = document.createElement('div');
            el.className = 'o_picking_desc_injected';
            el.style.cssText = 'color:#999;font-size:0.80rem;font-style:italic;margin-top:2px;white-space:normal;word-break:break-word;';
            el.textContent = t;
            p.appendChild(el);
        }
        d.style.display = 'none';
    });

    document.querySelectorAll('th[data-name="description_picking"]').forEach(h => {
        h.style.display = 'none';
    });
}

// Debounce: esperar 150ms de inactividad antes de ejecutar
let debounceTimer;
function debouncedApply() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(applyPickingDescFusion, 150);
}

const observer = new MutationObserver(debouncedApply);

function startObserver() {
    const target = document.querySelector('.o_content') || document.body;
    observer.observe(target, { childList: true, subtree: true });
    applyPickingDescFusion();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startObserver);
} else {
    startObserver();
}
