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

// Initialize event listeners
if (csvFileInput && uploadBtn) {
    csvFileInput.addEventListener('change', handleFileSelect);
    uploadBtn.addEventListener('click', uploadCSVFile);
}

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

