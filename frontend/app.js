// Global state
let currentTaskId = null;
let pollingInterval = null;

// DOM elements
const csvFileInput = document.getElementById('csvFile');
const fileNameSpan = document.getElementById('fileName');
const uploadBtn = document.getElementById('uploadBtn');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const statusSection = document.getElementById('statusSection');
const statusMessage = document.getElementById('statusMessage');
const statusDetails = document.getElementById('statusDetails');

// -----------------------------------------------------------------------------
// PAGE INITIALIZATION
// -----------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    if (path === '/' || path.endsWith('/index.html')) {
        // Find elements for the upload page
        const csvFileInput = document.getElementById('csvFile');
        const uploadBtn = document.getElementById('uploadBtn');

        if (csvFileInput && uploadBtn) {
            csvFileInput.addEventListener('change', handleFileSelect);
            uploadBtn.addEventListener('click', uploadCSVFile);
        }
    } else if (path.endsWith('/products.html')) {
        initializeProductsPage();
    } else if (path.endsWith('/webhooks.html')) {
        initializeWebhooksPage();
    }
});

/**
 * Handle file selection
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        fileNameSpan.textContent = file.name;
        uploadBtn.disabled = false;
    } else {
        fileNameSpan.textContent = 'Choose a CSV file';
        uploadBtn.disabled = true;
    }
}

/**
 * Upload CSV file to the backend
 */
function uploadCSVFile() {
    const file = csvFileInput.files[0];
    
    if (!file) {
        setStatus('error', 'Please select a file first.');
        return;
    }

    if (!file.name.endsWith('.csv')) {
        setStatus('error', 'Please select a valid CSV file.');
        return;
    }

    // Disable upload button during upload
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';

    // Reset UI
    progressSection.classList.remove('hidden');
    statusSection.classList.add('hidden');
    updateProgress(0);

    // Create FormData
    const formData = new FormData();
    formData.append('file', file);

    // Create XMLHttpRequest
    const xhr = new XMLHttpRequest();

    // Track upload progress
    xhr.upload.onprogress = function(event) {
        if (event.lengthComputable) {
            const percentComplete = (event.loaded / event.total) * 100;
            updateProgress(percentComplete);
        }
    };

    // Handle completion
    xhr.onload = function() {
        if (xhr.status === 202) {
            try {
                const response = JSON.parse(xhr.responseText);
                currentTaskId = response.task_id;
                
                // Upload complete, now start polling for processing status
                updateProgress(100);
                setStatus('info', 'File uploaded successfully. Processing...');
                
                // Start polling after a brief delay
                setTimeout(() => {
                    pollUploadStatus(currentTaskId);
                }, 500);
                
            } catch (error) {
                setStatus('error', 'Failed to parse server response.');
                resetUploadButton();
            }
        } else {
            try {
                const errorResponse = JSON.parse(xhr.responseText);
                setStatus('error', `Upload failed: ${errorResponse.detail || 'Unknown error'}`);
            } catch (error) {
                setStatus('error', `Upload failed with status: ${xhr.status}`);
            }
            resetUploadButton();
        }
    };

    // Handle network errors
    xhr.onerror = function() {
        setStatus('error', 'Network error occurred. Please check your connection and try again.');
        resetUploadButton();
    };

    // Handle timeout
    xhr.ontimeout = function() {
        setStatus('error', 'Upload timed out. Please try again.');
        resetUploadButton();
    };

    // Configure and send request
    xhr.open('POST', '/upload/start', true);
    xhr.timeout = 300000; // 5 minutes timeout
    xhr.send(formData);
}

/**
 * Poll upload status from the backend
 * @param {string} taskId - The task ID to poll
 */
function pollUploadStatus(taskId) {
    // Clear any existing polling interval
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }

    // Function to fetch status
    const fetchStatus = () => {
        const xhr = new XMLHttpRequest();
        
        xhr.onload = function() {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    const status = response.status.status;
                    const progress = response.progress;
                    
                    // Update status display
                    let message = '';
                    let details = '';
                    
                    if (status === 'QUEUED') {
                        message = 'Task queued, waiting to start...';
                        setStatus('info', message);
                    } else if (status === 'PROCESSING') {
                        if (progress) {
                            const total = parseInt(progress.total_rows) || 0;
                            const processed = parseInt(progress.processed_rows) || 0;
                            const successful = parseInt(progress.successful_rows) || 0;
                            const failed = parseInt(progress.failed_rows) || 0;
                            
                            message = `Processing: ${processed} / ${total} rows`;
                            details = `Successful: ${successful} | Failed: ${failed}`;
                            
                            // Calculate processing percentage
                            if (total > 0) {
                                const percent = (processed / total) * 100;
                                updateProgress(percent);
                            }
                        } else {
                            message = 'Processing...';
                        }
                        setStatus('info', message, details);
                    } else if (status === 'COMPLETED') {
                        // Stop polling
                        clearInterval(pollingInterval);
                        
                        if (progress) {
                            const total = parseInt(progress.total_rows) || 0;
                            const successful = parseInt(progress.successful_rows) || 0;
                            const failed = parseInt(progress.failed_rows) || 0;
                            
                            message = `Import completed successfully!`;
                            details = `Total: ${total} | Successful: ${successful} | Failed: ${failed}`;
                        } else {
                            message = 'Import completed successfully!';
                        }
                        
                        updateProgress(100);
                        setStatus('success', message, details);
                        resetUploadButton();
                    } else if (status === 'FAILED') {
                        // Stop polling
                        clearInterval(pollingInterval);
                        
                        const errorMsg = response.status.error || 'Unknown error occurred';
                        message = `Import failed: ${errorMsg}`;
                        
                        if (progress) {
                            const processed = parseInt(progress.processed_rows) || 0;
                            const successful = parseInt(progress.successful_rows) || 0;
                            const failed = parseInt(progress.failed_rows) || 0;
                            details = `Processed: ${processed} | Successful: ${successful} | Failed: ${failed}`;
                        }
                        
                        setStatus('error', message, details);
                        resetUploadButton();
                    }
                    
                } catch (error) {
                    clearInterval(pollingInterval);
                    setStatus('error', 'Failed to parse status response.');
                    resetUploadButton();
                }
            } else if (xhr.status === 404) {
                clearInterval(pollingInterval);
                setStatus('error', 'Task not found. It may have expired.');
                resetUploadButton();
            } else {
                clearInterval(pollingInterval);
                setStatus('error', `Failed to fetch status: ${xhr.status}`);
                resetUploadButton();
            }
        };
        
        xhr.onerror = function() {
            clearInterval(pollingInterval);
            setStatus('error', 'Network error while polling status.');
            resetUploadButton();
        };
        
        xhr.open('GET', `/upload/status/${taskId}`, true);
        xhr.send();
    };

    // Initial fetch
    fetchStatus();
    
    // Poll every 1 second
    pollingInterval = setInterval(fetchStatus, 1000);
}

/**
 * Update progress bar
 * @param {number} percent - Progress percentage (0-100)
 */
function updateProgress(percent) {
    const clampedPercent = Math.min(Math.max(percent, 0), 100);
    progressBar.style.width = `${clampedPercent}%`;
    progressText.textContent = `${Math.round(clampedPercent)}%`;
}

/**
 * Set status message
 * @param {string} type - Status type: 'info', 'success', 'error'
 * @param {string} message - Main status message
 * @param {string} details - Optional details message
 */
function setStatus(type, message, details = '') {
    statusSection.classList.remove('hidden');
    statusMessage.className = `status-message status-${type}`;
    statusMessage.textContent = message;
    
    if (details) {
        statusDetails.textContent = details;
        statusDetails.classList.remove('hidden');
    } else {
        statusDetails.textContent = '';
        statusDetails.classList.add('hidden');
    }
}

/**
 * Reset upload button to initial state
 */
function resetUploadButton() {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Upload';
    
    // Reset file input
    csvFileInput.value = '';
    fileNameSpan.textContent = 'Choose a CSV file';
    uploadBtn.disabled = true;
}

// =============================================================================
// PRODUCTS PAGE FUNCTIONALITY
// =============================================================================

// Global state for products page
let currentPage = 1;
let currentFilters = {};
const itemsPerPage = 20;

/**
 * Initialize products page
 */
function initializeProductsPage() {
    // DOM elements
    const createProductBtn = document.getElementById('createProductBtn');
    const deleteAllBtn = document.getElementById('deleteAllBtn');
    const applyFiltersBtn = document.getElementById('applyFiltersBtn');
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const cancelModalBtn = document.getElementById('cancelModalBtn');
    const productForm = document.getElementById('productForm');
    const productModal = document.getElementById('productModal');

    // Event listeners
    if (createProductBtn) {
        createProductBtn.addEventListener('click', openCreateModal);
    }
    
    if (deleteAllBtn) {
        deleteAllBtn.addEventListener('click', deleteAllProducts);
    }
    
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', applyFilters);
    }
    
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', clearFilters);
    }
    
    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                loadProducts(currentPage);
            }
        });
    }
    
    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', () => {
            currentPage++;
            loadProducts(currentPage);
        });
    }
    
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeProductModal);
    }
    
    if (cancelModalBtn) {
        cancelModalBtn.addEventListener('click', closeProductModal);
    }
    
    if (productForm) {
        productForm.addEventListener('submit', submitProductForm);
    }
    
    // Close modal when clicking outside
    if (productModal) {
        productModal.addEventListener('click', (e) => {
            if (e.target === productModal) {
                closeProductModal();
            }
        });
    }
    
    // Load products on page load
    loadProducts(1);
}

/**
 * Load products from the backend
 * @param {number} page - Page number to load
 */
function loadProducts(page = 1) {
    currentPage = page;
    
    // Build query parameters
    const params = new URLSearchParams();
    params.append('offset', (page - 1) * itemsPerPage);
    params.append('limit', itemsPerPage);
    
    // Add filters
    if (currentFilters.sku) {
        params.append('sku', currentFilters.sku);
    }
    if (currentFilters.name) {
        params.append('name', currentFilters.name);
    }
    if (currentFilters.active !== undefined && currentFilters.active !== '') {
        params.append('active', currentFilters.active);
    }
    
    // Show loading state
    const tableBody = document.getElementById('productsTableBody');
    tableBody.innerHTML = '<tr><td colspan="8" class="loading-cell">Loading products...</td></tr>';
    
    // Fetch products
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                const data = JSON.parse(xhr.responseText);
                renderProductsTable(data);
                updatePaginationControls(data);
            } catch (error) {
                showAlert('error', 'Failed to parse products data.');
            }
        } else {
            showAlert('error', `Failed to load products: ${xhr.status}`);
            tableBody.innerHTML = '<tr><td colspan="8" class="error-cell">Failed to load products</td></tr>';
        }
    };
    
    xhr.onerror = function() {
        showAlert('error', 'Network error while loading products.');
        tableBody.innerHTML = '<tr><td colspan="8" class="error-cell">Network error</td></tr>';
    };
    
    xhr.open('GET', `/products?${params.toString()}`, true);
    xhr.send();
}

/**
 * Apply filters
 */
function applyFilters() {
    currentFilters = getFilters();
    currentPage = 1;
    loadProducts(1);
}

/**
 * Clear filters
 */
function clearFilters() {
    document.getElementById('filterSku').value = '';
    document.getElementById('filterName').value = '';
    document.getElementById('filterActive').value = '';
    currentFilters = {};
    currentPage = 1;
    loadProducts(1);
}

/**
 * Get current filter values
 * @returns {Object} Filter values
 */
function getFilters() {
    const sku = document.getElementById('filterSku').value.trim();
    const name = document.getElementById('filterName').value.trim();
    const activeValue = document.getElementById('filterActive').value;
    
    const filters = {};
    
    if (sku) {
        filters.sku = sku;
    }
    if (name) {
        filters.name = name;
    }
    if (activeValue !== '') {
        filters.active = activeValue === 'true';
    }
    
    return filters;
}

/**
 * Render products table
 * @param {Object} data - Products data from API
 */
function renderProductsTable(data) {
    const tableBody = document.getElementById('productsTableBody');
    
    if (!data.items || data.items.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="8" class="empty-cell">No products found</td></tr>';
        return;
    }
    
    let html = '';
    
    data.items.forEach(product => {
        const createdAt = new Date(product.created_at).toLocaleString();
        const activeStatus = product.active 
            ? '<span class="badge badge-success">Active</span>' 
            : '<span class="badge badge-inactive">Inactive</span>';
        const price = product.price !== null ? `$${parseFloat(product.price).toFixed(2)}` : '-';
        const description = product.description || '-';
        
        html += `
            <tr>
                <td>${product.id}</td>
                <td><strong>${escapeHtml(product.sku)}</strong></td>
                <td>${escapeHtml(product.name)}</td>
                <td class="description-cell">${escapeHtml(description)}</td>
                <td>${price}</td>
                <td>${activeStatus}</td>
                <td>${createdAt}</td>
                <td class="actions-cell">
                    <button class="btn-small btn-edit" onclick="openEditModal(${product.id})">Edit</button>
                    <button class="btn-small btn-delete" onclick="deleteProduct(${product.id})">Delete</button>
                </td>
            </tr>
        `;
    });
    
    tableBody.innerHTML = html;
}

/**
 * Update pagination controls
 * @param {Object} data - Products data from API
 */
function updatePaginationControls(data) {
    const total = data.total || 0;
    const totalPages = Math.ceil(total / itemsPerPage) || 1;
    const currentPageNum = currentPage;
    
    // Update info text
    const paginationInfo = document.getElementById('paginationInfo');
    const start = (currentPageNum - 1) * itemsPerPage + 1;
    const end = Math.min(currentPageNum * itemsPerPage, total);
    paginationInfo.textContent = `Page ${currentPageNum} of ${totalPages} (${total} products total, showing ${start}-${end})`;
    
    // Update buttons
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    
    prevBtn.disabled = currentPageNum <= 1;
    nextBtn.disabled = currentPageNum >= totalPages;
}

/**
 * Open create product modal
 */
function openCreateModal() {
    const modal = document.getElementById('productModal');
    const modalTitle = document.getElementById('modalTitle');
    const form = document.getElementById('productForm');
    
    modalTitle.textContent = 'Create Product';
    form.reset();
    document.getElementById('productId').value = '';
    document.getElementById('productActive').checked = true;
    
    modal.classList.remove('hidden');
}

/**
 * Open edit product modal
 * @param {number} productId - Product ID to edit
 */
function openEditModal(productId) {
    // Fetch product details
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                // Find product in current table data
                const params = new URLSearchParams();
                params.append('offset', (currentPage - 1) * itemsPerPage);
                params.append('limit', itemsPerPage);
                
                // Add current filters
                if (currentFilters.sku) params.append('sku', currentFilters.sku);
                if (currentFilters.name) params.append('name', currentFilters.name);
                if (currentFilters.active !== undefined && currentFilters.active !== '') {
                    params.append('active', currentFilters.active);
                }
                
                const xhr2 = new XMLHttpRequest();
                xhr2.onload = function() {
                    if (xhr2.status === 200) {
                        const data = JSON.parse(xhr2.responseText);
                        const product = data.items.find(p => p.id === productId);
                        
                        if (product) {
                            const modal = document.getElementById('productModal');
                            const modalTitle = document.getElementById('modalTitle');
                            
                            modalTitle.textContent = 'Edit Product';
                            document.getElementById('productId').value = product.id;
                            document.getElementById('productSku').value = product.sku || '';
                            document.getElementById('productName').value = product.name || '';
                            document.getElementById('productDescription').value = product.description || '';
                            document.getElementById('productPrice').value = product.price || '';
                            document.getElementById('productActive').checked = product.active;
                            
                            modal.classList.remove('hidden');
                        }
                    }
                };
                xhr2.open('GET', `/products?${params.toString()}`, true);
                xhr2.send();
                
            } catch (error) {
                showAlert('error', 'Failed to load product details.');
            }
        }
    };
    
    xhr.onerror = function() {
        showAlert('error', 'Network error while loading product.');
    };
    
    // Just trigger a reload of the current page to get the product
    const params = new URLSearchParams();
    params.append('offset', (currentPage - 1) * itemsPerPage);
    params.append('limit', itemsPerPage);
    
    if (currentFilters.sku) params.append('sku', currentFilters.sku);
    if (currentFilters.name) params.append('name', currentFilters.name);
    if (currentFilters.active !== undefined && currentFilters.active !== '') {
        params.append('active', currentFilters.active);
    }
    
    xhr.open('GET', `/products?${params.toString()}`, true);
    xhr.send();
}

/**
 * Close product modal
 */
function closeProductModal() {
    const modal = document.getElementById('productModal');
    modal.classList.add('hidden');
}

/**
 * Submit product form (create or update)
 * @param {Event} event - Form submit event
 */
function submitProductForm(event) {
    event.preventDefault();
    
    const productId = document.getElementById('productId').value;
    const productData = {
        sku: document.getElementById('productSku').value.trim(),
        name: document.getElementById('productName').value.trim(),
        description: document.getElementById('productDescription').value.trim() || null,
        price: document.getElementById('productPrice').value ? parseFloat(document.getElementById('productPrice').value) : null,
        active: document.getElementById('productActive').checked
    };
    
    // Validate
    if (!productData.sku || !productData.name) {
        showAlert('error', 'SKU and Name are required fields.');
        return;
    }
    
    const xhr = new XMLHttpRequest();
    const isEdit = productId !== '';
    const url = isEdit ? `/products/${productId}` : '/products';
    const method = isEdit ? 'PUT' : 'POST';
    
    xhr.onload = function() {
        if (xhr.status === 200 || xhr.status === 201) {
            showAlert('success', `Product ${isEdit ? 'updated' : 'created'} successfully!`);
            closeProductModal();
            loadProducts(currentPage);
        } else {
            try {
                const errorData = JSON.parse(xhr.responseText);
                showAlert('error', `Failed to save product: ${errorData.detail || 'Unknown error'}`);
            } catch (error) {
                showAlert('error', `Failed to save product: ${xhr.status}`);
            }
        }
    };
    
    xhr.onerror = function() {
        showAlert('error', 'Network error while saving product.');
    };
    
    xhr.open(method, url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify(productData));
}

/**
 * Delete a single product
 * @param {number} productId - Product ID to delete
 */
function deleteProduct(productId) {
    if (!confirm('Are you sure you want to delete this product?')) {
        return;
    }
    
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 204) {
            showAlert('success', 'Product deleted successfully!');
            loadProducts(currentPage);
        } else if (xhr.status === 404) {
            showAlert('error', 'Product not found.');
        } else {
            showAlert('error', `Failed to delete product: ${xhr.status}`);
        }
    };
    
    xhr.onerror = function() {
        showAlert('error', 'Network error while deleting product.');
    };
    
    xhr.open('DELETE', `/products/${productId}`, true);
    xhr.send();
}

/**
 * Delete all products (bulk delete)
 */
function deleteAllProducts() {
    const confirmMsg = 'Are you sure you want to delete ALL products? This action cannot be undone!';
    
    if (!confirm(confirmMsg)) {
        return;
    }
    
    // Double confirmation for safety
    if (!confirm('This will permanently delete all products. Are you absolutely sure?')) {
        return;
    }
    
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 204) {
            showAlert('success', 'All products deleted successfully!');
            currentPage = 1;
            loadProducts(1);
        } else {
            showAlert('error', `Failed to delete products: ${xhr.status}`);
        }
    };
    
    xhr.onerror = function() {
        showAlert('error', 'Network error while deleting products.');
    };
    
    xhr.open('DELETE', '/products/all', true);
    xhr.send();
}

/**
 * Show alert message at top of page
 * @param {string} type - Alert type: 'success', 'error', 'info'
 * @param {string} message - Alert message
 */
function showAlert(type, message) {
    const alertSection = document.getElementById('alertSection');
    const alertMessage = document.getElementById('alertMessage');
    
    if (!alertSection || !alertMessage) {
        return;
    }
    
    alertMessage.className = `alert-message alert-${type}`;
    alertMessage.textContent = message;
    alertSection.classList.remove('hidden');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        alertSection.classList.add('hidden');
    }, 5000);
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================================================
// WEBHOOKS PAGE FUNCTIONALITY
// =============================================================================

/**
 * Initialize webhooks page
 */
function initializeWebhooksPage() {
    // DOM elements
    const createWebhookBtn = document.getElementById('createWebhookBtn');
    const closeWebhookModalBtn = document.getElementById('closeWebhookModalBtn');
    const cancelWebhookModalBtn = document.getElementById('cancelWebhookModalBtn');
    const webhookForm = document.getElementById('webhookForm');
    const webhookModal = document.getElementById('webhookModal');
    const closeTestResultBtn = document.getElementById('closeTestResultBtn');

    // Event listeners
    if (createWebhookBtn) {
        createWebhookBtn.addEventListener('click', openCreateWebhookModal);
    }
    
    if (closeWebhookModalBtn) {
        closeWebhookModalBtn.addEventListener('click', closeWebhookModal);
    }
    
    if (cancelWebhookModalBtn) {
        cancelWebhookModalBtn.addEventListener('click', closeWebhookModal);
    }
    
    if (webhookForm) {
        webhookForm.addEventListener('submit', submitWebhookForm);
    }
    
    if (closeTestResultBtn) {
        closeTestResultBtn.addEventListener('click', () => {
            document.getElementById('testResultSection').classList.add('hidden');
        });
    }
    
    // Close modal when clicking outside
    if (webhookModal) {
        webhookModal.addEventListener('click', (e) => {
            if (e.target === webhookModal) {
                closeWebhookModal();
            }
        });
    }
    
    // Load webhooks on page load
    loadWebhooks();
}

/**
 * Load webhooks from the backend
 */
function loadWebhooks() {
    const tableBody = document.getElementById('webhooksTableBody');
    tableBody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading webhooks...</td></tr>';
    
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                const data = JSON.parse(xhr.responseText);
                renderWebhooksTable(data);
            } catch (error) {
                showWebhookAlert('error', 'Failed to parse webhooks data.');
                tableBody.innerHTML = '<tr><td colspan="5" class="error-cell">Failed to parse data</td></tr>';
            }
        } else {
            showWebhookAlert('error', `Failed to load webhooks: ${xhr.status}`);
            tableBody.innerHTML = '<tr><td colspan="5" class="error-cell">Failed to load webhooks</td></tr>';
        }
    };
    
    xhr.onerror = function() {
        showWebhookAlert('error', 'Network error while loading webhooks.');
        tableBody.innerHTML = '<tr><td colspan="5" class="error-cell">Network error</td></tr>';
    };
    
    xhr.open('GET', '/webhooks', true);
    xhr.send();
}

/**
 * Render webhooks table
 * @param {Array} data - Webhooks array from API
 */
function renderWebhooksTable(data) {
    const tableBody = document.getElementById('webhooksTableBody');
    
    if (!data || data.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-cell">No webhooks configured</td></tr>';
        return;
    }
    
    let html = '';
    
    data.forEach(webhook => {
        const createdAt = webhook.created_at ? new Date(webhook.created_at).toLocaleString() : 'N/A';
        
        html += `
            <tr>
                <td>${webhook.id}</td>
                <td><span class="event-badge">${escapeHtml(webhook.event)}</span></td>
                <td class="url-cell"><a href="${escapeHtml(webhook.url)}" target="_blank" rel="noopener">${escapeHtml(webhook.url)}</a></td>
                <td>${createdAt}</td>
                <td class="actions-cell">
                    <button class="btn-small btn-test" onclick="testWebhook('${escapeHtml(webhook.event)}', ${webhook.id})">Test</button>
                    <button class="btn-small btn-edit" onclick="openEditWebhookModal(${webhook.id})">Edit</button>
                    <button class="btn-small btn-delete" onclick="deleteWebhook(${webhook.id})">Delete</button>
                </td>
            </tr>
        `;
    });
    
    tableBody.innerHTML = html;
}

/**
 * Open create webhook modal
 */
function openCreateWebhookModal() {
    const modal = document.getElementById('webhookModal');
    const modalTitle = document.getElementById('webhookModalTitle');
    const form = document.getElementById('webhookForm');
    
    modalTitle.textContent = 'Create Webhook';
    form.reset();
    document.getElementById('webhookId').value = '';
    
    modal.classList.remove('hidden');
}

/**
 * Open edit webhook modal
 * @param {number} webhookId - Webhook ID to edit
 */
function openEditWebhookModal(webhookId) {
    // Fetch current webhooks list to find the webhook
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                const data = JSON.parse(xhr.responseText);
                const webhook = data.find(w => w.id === webhookId);
                
                if (webhook) {
                    const modal = document.getElementById('webhookModal');
                    const modalTitle = document.getElementById('webhookModalTitle');
                    
                    modalTitle.textContent = 'Edit Webhook';
                    document.getElementById('webhookId').value = webhook.id;
                    document.getElementById('webhookEvent').value = webhook.event || '';
                    document.getElementById('webhookUrl').value = webhook.url || '';
                    
                    modal.classList.remove('hidden');
                } else {
                    showWebhookAlert('error', 'Webhook not found.');
                }
            } catch (error) {
                showWebhookAlert('error', 'Failed to load webhook details.');
            }
        }
    };
    
    xhr.onerror = function() {
        showWebhookAlert('error', 'Network error while loading webhook.');
    };
    
    xhr.open('GET', '/webhooks', true);
    xhr.send();
}

/**
 * Close webhook modal
 */
function closeWebhookModal() {
    const modal = document.getElementById('webhookModal');
    modal.classList.add('hidden');
}

/**
 * Submit webhook form (create or update)
 * @param {Event} event - Form submit event
 */
function submitWebhookForm(event) {
    event.preventDefault();
    
    const webhookId = document.getElementById('webhookId').value;
    const webhookData = {
        event: document.getElementById('webhookEvent').value.trim(),
        url: document.getElementById('webhookUrl').value.trim()
    };
    
    // Validate
    if (!webhookData.event || !webhookData.url) {
        showWebhookAlert('error', 'Event Type and URL are required fields.');
        return;
    }
    
    // Validate URL format
    try {
        new URL(webhookData.url);
    } catch (e) {
        showWebhookAlert('error', 'Please enter a valid URL.');
        return;
    }
    
    const xhr = new XMLHttpRequest();
    const isEdit = webhookId !== '';
    
    // Note: Backend doesn't support PUT/PATCH, so we delete and recreate for edit
    if (isEdit) {
        // Delete old webhook first
        deleteWebhookAndRecreate(parseInt(webhookId), webhookData);
        return;
    }
    
    // Create new webhook
    xhr.onload = function() {
        if (xhr.status === 201) {
            showWebhookAlert('success', 'Webhook created successfully!');
            closeWebhookModal();
            loadWebhooks();
        } else {
            try {
                const errorData = JSON.parse(xhr.responseText);
                showWebhookAlert('error', `Failed to save webhook: ${errorData.detail || 'Unknown error'}`);
            } catch (error) {
                showWebhookAlert('error', `Failed to save webhook: ${xhr.status}`);
            }
        }
    };
    
    xhr.onerror = function() {
        showWebhookAlert('error', 'Network error while saving webhook.');
    };
    
    xhr.open('POST', '/webhooks', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify(webhookData));
}

/**
 * Helper function to delete and recreate webhook (simulates update)
 * @param {number} webhookId - Webhook ID to delete
 * @param {Object} webhookData - New webhook data
 */
function deleteWebhookAndRecreate(webhookId, webhookData) {
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 204) {
            // Now create the new webhook
            const xhr2 = new XMLHttpRequest();
            
            xhr2.onload = function() {
                if (xhr2.status === 201) {
                    showWebhookAlert('success', 'Webhook updated successfully!');
                    closeWebhookModal();
                    loadWebhooks();
                } else {
                    showWebhookAlert('error', 'Webhook deleted but failed to recreate. Please create it manually.');
                    loadWebhooks();
                }
            };
            
            xhr2.onerror = function() {
                showWebhookAlert('error', 'Webhook deleted but network error on recreate.');
                loadWebhooks();
            };
            
            xhr2.open('POST', '/webhooks', true);
            xhr2.setRequestHeader('Content-Type', 'application/json');
            xhr2.send(JSON.stringify(webhookData));
        } else {
            showWebhookAlert('error', 'Failed to update webhook.');
        }
    };
    
    xhr.onerror = function() {
        showWebhookAlert('error', 'Network error while updating webhook.');
    };
    
    xhr.open('DELETE', `/webhooks/${webhookId}`, true);
    xhr.send();
}

/**
 * Delete a webhook
 * @param {number} webhookId - Webhook ID to delete
 */
function deleteWebhook(webhookId) {
    if (!confirm('Are you sure you want to delete this webhook?')) {
        return;
    }
    
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        if (xhr.status === 204) {
            showWebhookAlert('success', 'Webhook deleted successfully!');
            loadWebhooks();
        } else if (xhr.status === 404) {
            showWebhookAlert('error', 'Webhook not found.');
        } else {
            showWebhookAlert('error', `Failed to delete webhook: ${xhr.status}`);
        }
    };
    
    xhr.onerror = function() {
        showWebhookAlert('error', 'Network error while deleting webhook.');
    };
    
    xhr.open('DELETE', `/webhooks/${webhookId}`, true);
    xhr.send();
}

/**
 * Test a webhook by triggering its event
 * @param {string} eventType - Event type to trigger
 * @param {number} webhookId - Webhook ID (for display purposes)
 */
function testWebhook(eventType, webhookId) {
    showWebhookAlert('info', `Testing webhook for event: ${eventType}...`);
    
    const startTime = Date.now();
    const xhr = new XMLHttpRequest();
    
    xhr.onload = function() {
        const endTime = Date.now();
        const responseTime = endTime - startTime;
        
        if (xhr.status === 202) {
            try {
                const response = JSON.parse(xhr.responseText);
                showTestResult('success', {
                    webhookId: webhookId,
                    eventType: eventType,
                    statusCode: xhr.status,
                    responseTime: responseTime,
                    message: 'Test event dispatched successfully! Webhook will receive the request asynchronously.',
                    response: response
                });
                showWebhookAlert('success', 'Test webhook dispatched successfully!');
            } catch (error) {
                showTestResult('error', {
                    webhookId: webhookId,
                    eventType: eventType,
                    statusCode: xhr.status,
                    responseTime: responseTime,
                    message: 'Test dispatched but failed to parse response.',
                    error: xhr.responseText
                });
            }
        } else {
            showTestResult('error', {
                webhookId: webhookId,
                eventType: eventType,
                statusCode: xhr.status,
                responseTime: responseTime,
                message: `Test failed with status: ${xhr.status}`,
                error: xhr.responseText
            });
            showWebhookAlert('error', `Test failed: ${xhr.status}`);
        }
    };
    
    xhr.onerror = function() {
        const endTime = Date.now();
        const responseTime = endTime - startTime;
        
        showTestResult('error', {
            webhookId: webhookId,
            eventType: eventType,
            statusCode: 0,
            responseTime: responseTime,
            message: 'Network error occurred while testing webhook.',
            error: 'Network request failed'
        });
        showWebhookAlert('error', 'Network error while testing webhook.');
    };
    
    xhr.open('POST', `/webhooks/test/${encodeURIComponent(eventType)}`, true);
    xhr.send();
}

/**
 * Show test result in a dedicated section
 * @param {string} type - Result type: 'success' or 'error'
 * @param {Object} result - Test result data
 */
function showTestResult(type, result) {
    const testResultSection = document.getElementById('testResultSection');
    const testResultContent = document.getElementById('testResultContent');
    
    let html = `
        <div class="test-result-item">
            <strong>Event Type:</strong> ${escapeHtml(result.eventType)}
        </div>
        <div class="test-result-item">
            <strong>Status Code:</strong> <span class="status-code status-${type}">${result.statusCode}</span>
        </div>
        <div class="test-result-item">
            <strong>Response Time:</strong> ${result.responseTime}ms
        </div>
        <div class="test-result-item">
            <strong>Message:</strong> ${escapeHtml(result.message)}
        </div>
    `;
    
    if (result.response) {
        html += `
            <div class="test-result-item">
                <strong>Response:</strong>
                <pre>${escapeHtml(JSON.stringify(result.response, null, 2))}</pre>
            </div>
        `;
    }
    
    if (result.error) {
        html += `
            <div class="test-result-item test-result-error">
                <strong>Error:</strong>
                <pre>${escapeHtml(result.error)}</pre>
            </div>
        `;
    }
    
    testResultContent.innerHTML = html;
    testResultSection.classList.remove('hidden');
    testResultSection.className = `test-result-section test-result-${type}`;
}

/**
 * Show alert message for webhooks page
 * @param {string} type - Alert type: 'success', 'error', 'info'
 * @param {string} message - Alert message
 */
function showWebhookAlert(type, message) {
    const alertSection = document.getElementById('webhookAlertSection');
    const alertMessage = document.getElementById('webhookAlertMessage');
    
    if (!alertSection || !alertMessage) {
        return;
    }
    
    alertMessage.className = `alert-message alert-${type}`;
    alertMessage.textContent = message;
    alertSection.classList.remove('hidden');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        alertSection.classList.add('hidden');
    }, 5000);
}

