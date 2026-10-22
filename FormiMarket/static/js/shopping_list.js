function toggleIngredient(checkbox) {
    const name = checkbox.dataset.name;
    const parentItem = checkbox.closest('.ingredient-item');

    // Optimistic Update
    if (checkbox.checked) {
        parentItem.classList.add('checked');
    } else {
        parentItem.classList.remove('checked');
    }

    // Update total price immediately
    if (window.calculateTotal) window.calculateTotal();

    fetch('/api/toggle', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: name }),
    })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('Erreur lors de la mise à jour.');
                // Revert
                checkbox.checked = !checkbox.checked;
                if (checkbox.checked) {
                    parentItem.classList.add('checked');
                } else {
                    parentItem.classList.remove('checked');
                }
                if (window.calculateTotal) window.calculateTotal();
            }
        })
        .catch(err => {
            console.error(err);
            // Revert UI on error
            checkbox.checked = !checkbox.checked;
            if (checkbox.checked) {
                parentItem.classList.add('checked');
            } else {
                parentItem.classList.remove('checked');
            }
            if (window.calculateTotal) window.calculateTotal();
        });
}

// Global modal variables
let modal, editOriginalNameInput, editNameInput, editCategoryInput, editPriceInput;

document.addEventListener('DOMContentLoaded', () => {
    modal = document.getElementById('edit-modal');
    editOriginalNameInput = document.getElementById('edit-original-name');
    editNameInput = document.getElementById('edit-name');
    editCategoryInput = document.getElementById('edit-category');
    editPriceInput = document.getElementById('edit-price');

    // Close modal when clicking outside
    window.onclick = function (event) {
        if (event.target == modal) {
            closeEditModal();
        }
    }

    // Category Custom Dropdown
    const categoryInput = document.getElementById('category-input');
    const categoryDropdown = document.getElementById('category-dropdown');

    if (categoryInput && categoryDropdown && typeof availableCategories !== 'undefined') {
        const categories = availableCategories;

        function showDropdown(filterText = '') {
            categoryDropdown.innerHTML = '';
            const filtered = categories.filter(c => c.toLowerCase().includes(filterText.toLowerCase()));

            if (filtered.length === 0) {
                categoryDropdown.style.display = 'none';
                return;
            }

            filtered.forEach(cat => {
                const li = document.createElement('li');
                li.textContent = cat;
                li.addEventListener('click', () => {
                    categoryInput.value = cat;
                    categoryDropdown.style.display = 'none';
                });
                categoryDropdown.appendChild(li);
            });
            categoryDropdown.style.display = 'block';
        }

        categoryInput.addEventListener('input', (e) => showDropdown(e.target.value));

        categoryInput.addEventListener('focus', () => {
            // Show all if empty, or filter
            showDropdown(categoryInput.value);
        });

        // Hide when clicking outside
        document.addEventListener('click', (e) => {
            if (!categoryInput.contains(e.target) && !categoryDropdown.contains(e.target)) {
                categoryDropdown.style.display = 'none';
            }
        });
    }

    // Market Mode & Price Logic
    const marketModeCheckbox = document.getElementById('market-mode-checkbox');
    const container = document.querySelector('.shopping-list-container');
    const totalPriceSpan = document.getElementById('total-price');

    function calculateTotal() {
        const checkedItems = document.querySelectorAll('.ingredient-item.checked input[type="checkbox"]');
        let total = 0;
        checkedItems.forEach(item => {
            total += parseFloat(item.dataset.price || 0);
        });
        if (totalPriceSpan) {
            totalPriceSpan.textContent = total.toFixed(2);
        }
    }

    if (marketModeCheckbox && container) {
        function applyMarketMode() {
            const isMarketMode = localStorage.getItem('marketMode') === 'true';
            marketModeCheckbox.checked = isMarketMode;
            if (isMarketMode) {
                container.classList.add('market-mode');
            } else {
                container.classList.remove('market-mode');
            }
        }
        applyMarketMode();

        marketModeCheckbox.addEventListener('change', () => {
            localStorage.setItem('marketMode', marketModeCheckbox.checked);
            applyMarketMode();
        });

        // Periodic check to handle synchronization that might replace the DOM
        setInterval(applyMarketMode, 1000);
    }

    // Initial calculation
    calculateTotal();

    // Expose calculateTotal to global scope for toggleIngredient
    window.calculateTotal = calculateTotal;
});

function openEditModal(name, category, price) {
    if (!modal) return;
    document.getElementById('edit-original-name').value = name;
    document.getElementById('edit-name').value = name;
    document.getElementById('edit-category').value = category;
    document.getElementById('edit-price').value = price;
    modal.style.display = 'block';
}

function closeEditModal() {
    if (modal) modal.style.display = 'none';
}

function saveEdit(event) {
    event.preventDefault();
    const originalName = document.getElementById('edit-original-name').value;
    const newName = document.getElementById('edit-name').value;
    const category = document.getElementById('edit-category').value;
    const price = document.getElementById('edit-price').value;

    fetch('/api/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            original_name: originalName,
            new_name: newName,
            category: category,
            price: price
        }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert(data.message || 'Erreur lors de la mise à jour.');
            }
        });
}

function deleteFromModal() {
    const name = document.getElementById('edit-original-name').value;
    if (!confirm('Voulez-vous vraiment supprimer cet ingrédient ?')) return;

    fetch('/api/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: name }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Erreur lors de la suppression.');
            }
        });
}
