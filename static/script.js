const API_BASE = '/api';
const IMAGE_EXT = ['png','jpg','jpeg','gif','webp','bmp','svg','ico','tiff','heic'];
let _allProviderKeys = {};

const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const messagesContainer = document.getElementById('messages');
const welcomeMessage = document.getElementById('welcomeMessage');
const configModal = document.getElementById('configModal');
const configBtn = document.getElementById('configBtn');
const closeConfigBtn = document.getElementById('closeConfigBtn');
const cancelConfigBtn = document.getElementById('cancelConfigBtn');
const saveConfigBtn = document.getElementById('saveConfigBtn');
const newChatBtn = document.getElementById('newChatBtn');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const searchToggle = document.getElementById('searchToggle');
const statusIndicator = document.getElementById('statusIndicator');
const stopBtn = document.getElementById('stopBtn');
const statusDot = statusIndicator.querySelector('.status-dot');
const statusText = statusIndicator.querySelector('.status-text');
const providerSelect = document.getElementById('providerSelect');
const modelSelect = document.getElementById('modelSelect');
const apiKeyInput = document.getElementById('apiKeyInput');
const enableSearchConfig = document.getElementById('enableSearchConfig');
const attachBtn = document.getElementById('attachBtn');
const fileAttachInput = document.getElementById('fileAttachInput');
const genImgBtn = document.getElementById('genImgBtn');
const faceRecBtn = document.getElementById('faceRecBtn');
const faceRecInput = document.getElementById('faceRecInput');
const inputWrapper = document.getElementById('inputWrapper');
const attachmentsBar = document.getElementById('attachmentsBar');
const dropHint = document.getElementById('dropHint');
const searchBtn = document.getElementById('searchBtn');
const multiSelectBtn = document.getElementById('multiSelectBtn');
const collapseBtn = document.getElementById('collapseBtn');
const sidebar = document.querySelector('.sidebar');
const sidebarSearch = document.getElementById('sidebarSearch');
const searchInput = document.getElementById('searchInput');
const multiSelectActions = document.getElementById('multiSelectActions');
const cancelMultiSelect = document.getElementById('cancelMultiSelect');
const deleteSelected = document.getElementById('deleteSelected');

let isConfigured = false;
let isLoading = false;
let attachments = [];
let isMultiSelectMode = false;
let searchKeyword = '';
let allConversations = [];

document.addEventListener('DOMContentLoaded', () => {
    initUIState();
    loadConfig();
    setupEventListeners();
    loadHistory();
});

function initUIState() {
    isMultiSelectMode = false;
    searchKeyword = '';
    if (multiSelectActions) multiSelectActions.classList.remove('active');
    if (sidebarSearch) sidebarSearch.style.display = 'none';
    if (searchInput) searchInput.value = '';
}

async function loadHistory() {
    // Load conversation list first
    await loadConversationList();
    
    // Try to load the most recent conversation
    try {
        const response = await fetch(`${API_BASE}/conversations`);
        const data = await response.json();
        if (data.success && data.conversations.length > 0) {
            // Load the most recent conversation
            const latestConv = data.conversations[0];
            await loadConversation(latestConv.id);
        }
    } catch (error) {
        console.warn('加载对话失败:', error);
    }
}

async function loadConversationList() {
    try {
        const response = await fetch(`${API_BASE}/conversations`);
        const data = await response.json();
        if (data.success) {
            displayConversationList(data.conversations);
        }
    } catch (error) {
        console.warn('加载对话列表失败:', error);
    }
}

function displayConversationList(conversations) {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;
    
    allConversations = conversations || [];
    
    renderHistoryList();
}

function renderHistoryList() {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;
    
    historyList.innerHTML = '';
    
    let filtered = allConversations;
    if (searchKeyword) {
        filtered = allConversations.filter(c => {
            const title = (c.title || '').toLowerCase();
            return title.includes(searchKeyword);
        });
    }
    
    if (filtered.length === 0) {
        const msg = searchKeyword ? '未找到匹配的历史对话' : '暂无历史对话';
        historyList.innerHTML = `<div style="text-align:center;color:#999;padding:20px;font-size:13px;">${msg}</div>`;
        return;
    }
    
    filtered.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'history-item';
        item.dataset.id = conv.id;
        
        if (isMultiSelectMode) item.classList.add('multi-select-mode');
        
        const date = new Date(conv.timestamp);
        const timeStr = date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
        
        item.innerHTML = `
            <span class="history-item-title">${escapeHtml(conv.title)}</span>
            <span class="history-item-time">${timeStr}</span>
            ${isMultiSelectMode ? '' : `
            <button class="history-item-delete" title="删除">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            </button>`}
        `;
        
        item.addEventListener('click', (e) => {
            if (isMultiSelectMode) {
                e.stopPropagation();
                item.classList.toggle('selected');
                return;
            }
            if (e.target.closest('.history-item-delete')) return;
            loadConversation(conv.id);
        });
        
        if (!isMultiSelectMode) {
            const deleteBtn = item.querySelector('.history-item-delete');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                });
            }
        }
        
        if (!isMultiSelectMode && currentConversationId === conv.id) {
            item.classList.add('active');
        }
        
        historyList.appendChild(item);
    });
}

function filterHistoryList() {
    renderHistoryList();
}

function toggleSidebar() {
    sidebar.classList.toggle('collapsed');
}

function enterMultiSelectMode() {
    isMultiSelectMode = true;
    multiSelectActions.classList.add('active');
    sidebarSearch.style.display = 'none';
    renderHistoryList();
}

function exitMultiSelectMode() {
    isMultiSelectMode = false;
    multiSelectActions.classList.remove('active');
    renderHistoryList();
}

async function deleteSelectedConversations() {
    const selectedIds = Array.from(document.querySelectorAll('.history-item.selected'))
        .map(el => el.dataset.id);
    
    if (selectedIds.length === 0) {
        showToast('请先选择要删除的对话');
        return;
    }
    
    if (!confirm(`确定要删除选中的 ${selectedIds.length} 个对话吗？`)) return;
    
    try {
        let successCount = 0;
        for (const id of selectedIds) {
            const response = await fetch(`${API_BASE}/conversations/${id}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            if (data.success) successCount++;
            
            if (currentConversationId === id) {
                currentConversationId = null;
                messagesContainer.innerHTML = '';
                welcomeMessage.style.display = 'block';
            }
        }
        
        showToast(`已删除 ${successCount} 个对话`);
        exitMultiSelectMode();
        await loadConversationList();
    } catch (error) {
        console.error('批量删除失败:', error);
        showToast('删除失败');
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadConversation(convId) {
    try {
        const response = await fetch(`${API_BASE}/conversations/${convId}`);
        const data = await response.json();
        
        if (data.success) {
            currentConversationId = convId;
            
            // Clear current messages
            messagesContainer.innerHTML = '';
            welcomeMessage.style.display = 'none';
            
            // Load messages
            const messages = data.conversation.messages || [];
            messages.forEach(msg => {
                addMessage(msg.role, msg.content);
            });
            
            // Update active state in list
            document.querySelectorAll('.history-item').forEach(item => {
                item.classList.remove('active');
                if (item.dataset.id === convId) {
                    item.classList.add('active');
                }
            });
        }
    } catch (error) {
        console.error('加载对话失败:', error);
        showToast('加载对话失败');
    }
}

async function createNewConversation() {
    try {
        const response = await fetch(`${API_BASE}/conversations`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await response.json();
        
        if (data.success) {
            currentConversationId = data.conversation.id;
            
            // Clear current messages
            messagesContainer.innerHTML = '';
            welcomeMessage.style.display = 'block';
            
            // Reload conversation list
            loadConversationList();
            
            showToast('已创建新对话');
        }
    } catch (error) {
        console.error('创建新对话失败:', error);
        showToast('创建新对话失败');
    }
}

async function deleteConversation(convId) {
    if (!confirm('确定要删除这个对话吗？')) return;
    
    try {
        const response = await fetch(`${API_BASE}/conversations/${convId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            // Remove from list
            const item = document.querySelector(`.history-item[data-id="${convId}"]`);
            if (item) item.remove();
            
            // If deleted current conversation, clear chat
            if (currentConversationId === convId) {
                currentConversationId = null;
                messagesContainer.innerHTML = '';
                welcomeMessage.style.display = 'block';
            }
            
            showToast('对话已删除');
        }
    } catch (error) {
        console.error('删除对话失败:', error);
        showToast('删除对话失败');
    }
}

async function clearAllConversations() {
    if (!confirm('确定要清空所有历史对话吗？此操作不可恢复。')) return;
    
    try {
        const response = await fetch(`${API_BASE}/conversations/clear`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            currentConversationId = null;
            messagesContainer.innerHTML = '';
            welcomeMessage.style.display = 'block';
            
            // Reload conversation list
            loadConversationList();
            
            showToast('已清空所有历史对话');
        }
    } catch (error) {
        console.error('清空历史失败:', error);
        showToast('清空历史失败');
    }
}

function setupEventListeners() {
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            sendMessage();
        }
    });
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 180) + 'px';
        updateSendButton();
    });
    messageInput.addEventListener('paste', handlePaste);
    
    attachBtn.addEventListener('click', () => fileAttachInput.click());
    fileAttachInput.addEventListener('change', (e) => {
        Array.from(e.target.files).forEach(addAttachment);
        fileAttachInput.value = '';
    });
    
    const dragArea = document.querySelector('.input-container');
    ['dragenter', 'dragover'].forEach(evt => {
        dragArea.addEventListener(evt, (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer.types.includes('Files')) {
                inputWrapper.classList.add('drag-over');
                dropHint.style.display = 'flex';
            }
        });
    });
    ['dragleave', 'drop'].forEach(evt => {
        dragArea.addEventListener(evt, (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (evt === 'dragleave' && e.target !== dragArea && !dragArea.contains(e.relatedTarget)) return;
            inputWrapper.classList.remove('drag-over');
            dropHint.style.display = 'none';
        });
    });
    dragArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        Array.from(files).forEach(addAttachment);
    });
    
    configBtn.addEventListener('click', () => configModal.classList.add('active'));
    closeConfigBtn.addEventListener('click', () => configModal.classList.remove('active'));
    cancelConfigBtn.addEventListener('click', () => configModal.classList.remove('active'));
    saveConfigBtn.addEventListener('click', saveConfig);
    newChatBtn.addEventListener('click', createNewConversation);
    clearHistoryBtn.addEventListener('click', clearAllConversations);
    searchToggle.addEventListener('change', toggleSearch);
    stopBtn.addEventListener('click', stopGeneration);
    providerSelect.addEventListener('change', () => {
        updateModelList(providerSelect.value);
        if (typeof _allProviderKeys !== 'undefined') {
            apiKeyInput.value = _allProviderKeys[providerSelect.value] || '';
        }
    });
    
    updateModelList(providerSelect.value);
    
    genImgBtn.addEventListener('click', () => {
        if (!isConfigured) { alert('请先配置API Key'); return; }
        if (isLoading) return;
        const text = messageInput.value.trim();
        if (text) {
            doGenerateImage(text);
        } else {
            const prompt = prompt('请输入图片描述（提示词）：\n\n例如：一只可爱的橘猫在阳光下睡觉');
            if (prompt && prompt.trim()) {
                doGenerateImage(prompt.trim());
            }
        }
    });
    
    faceRecBtn.addEventListener('click', () => {
        if (isLoading) return;
        faceRecInput.value = '';
        faceRecInput.click();
    });
    faceRecInput.addEventListener('change', (e) => {
        const file = e.target.files?.[0];
        if (file) doFaceRecognition(file);
    });
    
    collapseBtn.addEventListener('click', toggleSidebar);
    
    searchBtn.addEventListener('click', () => {
        const hidden = sidebarSearch.style.display === 'none' || sidebarSearch.style.display === '';
        sidebarSearch.style.display = hidden ? 'block' : 'none';
        if (hidden) {
            exitMultiSelectMode();
            setTimeout(() => searchInput.focus(), 100);
        } else {
            searchInput.value = '';
            searchKeyword = '';
            filterHistoryList();
        }
    });
    
    searchInput.addEventListener('input', (e) => {
        searchKeyword = e.target.value.trim().toLowerCase();
        filterHistoryList();
    });
    
    multiSelectBtn.addEventListener('click', enterMultiSelectMode);
    cancelMultiSelect.addEventListener('click', exitMultiSelectMode);
    deleteSelected.addEventListener('click', deleteSelectedConversations);
}

function handlePaste(e) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
        if (item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
                e.preventDefault();
                addAttachment(file);
            }
        }
    }
}

function isImageFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (IMAGE_EXT.includes(ext)) return true;
    if (file.type && file.type.startsWith('image/')) return true;
    return false;
}

function addAttachment(file) {
    if (isLoading) return;
    if (!isConfigured) { alert('请先在设置中配置 API Key'); return; }
    
    const isImg = isImageFile(file);
    const MAX_IMG = 12 * 1024 * 1024;
    const MAX_FILE = 15 * 1024 * 1024;
    
    if (isImg && file.size > MAX_IMG) {
        alert('图片太大（超过12MB），请压缩后再上传'); return;
    }
    if (!isImg && file.size > MAX_FILE) {
        alert('文件太大（超过15MB），请上传更小的文件'); return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
        const att = {
            id: 'att-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7),
            file: file,
            name: file.name || (isImg ? '粘贴图片.png' : '文件'),
            size: file.size,
            isImage: isImg,
            preview: isImg ? e.target.result : null,
        };
        attachments.push(att);
        renderAttachments();
        updateSendButton();
    };
    reader.onerror = () => alert('读取文件失败');
    if (isImg) {
        reader.readAsDataURL(file);
    } else {
        reader.readAsArrayBuffer(file);
    }
}

function removeAttachment(id) {
    attachments = attachments.filter(a => a.id !== id);
    renderAttachments();
    updateSendButton();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

function renderAttachments() {
    if (attachments.length === 0) {
        attachmentsBar.style.display = 'none';
        attachmentsBar.innerHTML = '';
        return;
    }
    attachmentsBar.style.display = 'flex';
    attachmentsBar.innerHTML = '';
    attachments.forEach(att => {
        const card = document.createElement('div');
        card.className = 'attachment-card ' + (att.isImage ? 'image-card' : 'file-card');
        card.innerHTML = '<button type="button" class="remove-attachment" title="移除">✕</button>';
        if (att.isImage) {
            const img = document.createElement('img');
            img.src = att.preview;
            img.alt = att.name;
            card.appendChild(img);
        } else {
            const ext = att.name.split('.').pop().toUpperCase().slice(0, 5);
            card.innerHTML += `
                <div class="file-icon">${ext}</div>
                <div class="file-info">
                    <div class="file-name" title="${att.name}">${att.name}</div>
                    <div class="file-size">${formatFileSize(att.size)}</div>
                </div>`;
        }
        card.querySelector('.remove-attachment').addEventListener('click', () => removeAttachment(att.id));
        attachmentsBar.appendChild(card);
    });
}

function updateSendButton() {
    const hasText = messageInput.value.trim().length > 0;
    const hasAtt = attachments.length > 0;
    const active = (hasText || hasAtt) && isConfigured && !isLoading;
    sendBtn.classList.toggle('active', active);
    sendBtn.disabled = !active;
    
    // Show/hide stop button
    if (isLoading) {
        stopBtn.style.display = 'flex';
        sendBtn.style.display = 'none';
    } else {
        stopBtn.style.display = 'none';
        sendBtn.style.display = 'flex';
    }
}

async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/config`);
        const data = await response.json();
        if (data.success) {
            const c = data.config;
            _allProviderKeys = c.api_keys || {};
            providerSelect.value = c.provider;
            updateModelList(c.provider, c.model);
            apiKeyInput.value = c.api_key;
            enableSearchConfig.checked = c.enable_search;
            searchToggle.checked = c.enable_search;
            updateConfigStatus(!!c.api_key);
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

async function saveConfig() {
    const config = {
        provider: providerSelect.value,
        model: modelSelect.value,
        api_key: apiKeyInput.value.trim(),
        enable_search: enableSearchConfig.checked
    };
    if (!config.api_key) { alert('请输入API Key'); return; }
    try {
        const response = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await response.json();
        if (data.success) {
            configModal.classList.remove('active');
            updateConfigStatus(true);
            searchToggle.checked = config.enable_search;
            alert('配置已保存');
        } else {
            alert('保存失败: ' + data.error);
        }
    } catch (error) {
        alert('保存失败');
    }
}

function updateConfigStatus(configured) {
    isConfigured = configured;
    if (configured) {
        statusDot.classList.add('active');
        statusText.textContent = '已配置';
    } else {
        statusDot.classList.remove('active');
        statusText.textContent = '未配置';
    }
    updateSendButton();
}

const PROVIDER_MODELS = {
    deepseek: {
        default: 'deepseek-chat',
        chat: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-chat-v3'],
        vision: [],
        image: []
    },
    qwen: {
        default: 'qwen-plus',
        chat: ['qwen-plus', 'qwen-max', 'qwen-turbo', 'qwen-long'],
        vision: ['qwen-vl-plus', 'qwen-vl-max'],
        image: ['qwen-image', 'wanx2.1-t2i-turbo', 'wanx2.1-t2i-plus', 'wanx-v1']
    },
    wenxin: {
        default: 'ernie-4.5-turbo-128k',
        chat: ['ernie-4.5-turbo-128k', 'ernie-4.0-turbo-8k', 'ernie-lite-8k', 'ernie-speed-128k', 'ernie-4.0-8k'],
        vision: ['ernie-5.0', 'ernie-4.5-vision'],
        image: ['qwen-image', 'ernie-image', 'ernie-image-turbo', 'ERNIE-ViLG-2.0', 'sd_xl', 'irag-1.0']
    },
    openai: {
        default: 'gpt-4o-mini',
        chat: ['gpt-4o-mini', 'gpt-4o', 'gpt-4o-2024-11-20', 'o1-mini', 'gpt-4-turbo'],
        vision: ['gpt-4o-mini', 'gpt-4o'],
        image: ['dall-e-3', 'dall-e-2']
    }
};

function updateModelList(provider, presetModel) {
    const info = PROVIDER_MODELS[provider] || PROVIDER_MODELS.deepseek;
    modelSelect.innerHTML = '';
    
    const groups = [
        {label: '💬 对话模型', items: info.chat},
        {label: '👁️ 视觉模型', items: info.vision},
        {label: '🎨 生图模型', items: info.image},
    ];
    
    let firstOption = null;
    groups.forEach(g => {
        if (!g.items || g.items.length === 0) return;
        const optgroup = document.createElement('optgroup');
        optgroup.label = g.label;
        g.items.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m + (m === info.default ? ' (默认)' : '');
            optgroup.appendChild(opt);
            if (!firstOption) firstOption = opt;
        });
        modelSelect.appendChild(optgroup);
    });
    
    const targetModel = presetModel || info.default;
    let found = false;
    for (let opt of modelSelect.options) {
        if (opt.value === targetModel) {
            modelSelect.value = targetModel;
            found = true;
            break;
        }
    }
    if (!found && firstOption) {
        modelSelect.value = info.default;
    }
}

async function sendMessage() {
    if (isLoading || !isConfigured) return;
    const text = messageInput.value.trim();
    if (!text && attachments.length === 0) return;
    
    const images = attachments.filter(a => a.isImage);
    const files = attachments.filter(a => !a.isImage);
    
    if (images.length > 0 && files.length > 0) {
        alert('暂不支持同时发送图片和文件，请分开发送');
        return;
    }
    
    welcomeMessage.style.display = 'none';
    messageInput.value = '';
    messageInput.style.height = 'auto';
    const currentAttachments = [...attachments];
    attachments = [];
    renderAttachments();
    
    isLoading = true;
    updateSendButton();
    
    if (images.length > 0) {
        for (let i = 0; i < images.length; i++) {
            const isLast = (i === images.length - 1);
            const prompt = (images.length > 1 && !isLast) 
                ? `识别这张图片（${i+1}/${images.length}）` 
                : (text || '请描述这张图片的内容');
            await doRecognizeImage(images[i], prompt);
        }
    } else if (files.length > 0) {
        for (let i = 0; i < files.length; i++) {
            const isLast = (i === files.length - 1);
            const prompt = (text && isLast) ? text : '';
            await doAnalyzeFile(files[i], prompt);
        }
    } else {
        await doChat(text);
    }
    
    isLoading = false;
    updateSendButton();
}

async function doChat(question) {
    let forceSearch = false;
    let q = question;
    if (q.toLowerCase().startsWith('search:')) {
        forceSearch = true;
        q = q.substring(7).trim();
    }
    addMessage('user', question);
    const loadingId = addMessage('assistant', '<span class="loading">正在思考...</span>', true);
    
    // Create abort controller for this request
    currentAbortController = new AbortController();
    
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({question: q, force_search: forceSearch}),
            signal: currentAbortController.signal
        });
        const data = await response.json();
        const answer = data.success ? data.answer : ('错误: ' + data.error);
        updateMessage(loadingId, answer);
    } catch (error) {
        if (error.name === 'AbortError') {
            updateMessage(loadingId, '已停止生成');
        } else {
            updateMessage(loadingId, '网络错误，请重试');
        }
    } finally {
        currentAbortController = null;
        await loadConversationList();
    }
}

async function doRecognizeImage(att, prompt) {
    addMessage('user', `🖼️ ${att.name}${prompt ? '\n' + prompt : ''}
        <img src="${att.preview}" style="max-width:200px;border-radius:8px;margin-top:8px;border:1px solid rgba(0,0,0,0.1);">`
    );
    const loadingId = addMessage('assistant', '<span class="loading">正在识别图片...</span>', true);
    
    currentAbortController = new AbortController();
    
    try {
        const uploadFile = att.file;
        const formData = new FormData();
        formData.append('image', uploadFile);
        formData.append('prompt', prompt);
        const response = await fetch(`${API_BASE}/recognize_image`, {
            method: 'POST',
            body: formData,
            signal: currentAbortController.signal
        });
        const data = await response.json();
        updateMessage(loadingId, data.success ? data.result : ('错误: ' + data.error));
    } catch (error) {
        if (error.name === 'AbortError') {
            updateMessage(loadingId, '已停止识别');
        } else {
            updateMessage(loadingId, '图片识别失败');
        }
    } finally {
        currentAbortController = null;
        await loadConversationList();
    }
}

async function doAnalyzeFile(att, extraPrompt) {
    addMessage('user', `📄 ${att.name}${extraPrompt ? '\n' + extraPrompt : ''}`);
    const loadingId = addMessage('assistant', '<span class="loading">正在分析文件...</span>', true);
    
    currentAbortController = new AbortController();
    
    try {
        const formData = new FormData();
        formData.append('file', att.file);
        const response = await fetch(`${API_BASE}/analyze_file`, {
            method: 'POST',
            body: formData,
            signal: currentAbortController.signal
        });
        const data = await response.json();
        if (data.success) {
            let result = data.result;
            if (extraPrompt) {
                result += `\n\n---\n\n（你可以继续追问关于「${att.name}」的问题）`;
            }
            updateMessage(loadingId, result);
        } else {
            updateMessage(loadingId, '错误: ' + data.error);
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            updateMessage(loadingId, '已停止分析');
        } else {
            updateMessage(loadingId, '文件分析失败');
        }
    } finally {
        currentAbortController = null;
        await loadConversationList();
    }
}

async function doGenerateImage(prompt) {
    addMessage('user', `🎨 生成图片: ${prompt}`);
    const loadingId = addMessage('assistant', '<span class="loading">🖼️ 正在生成图片，请稍候...</span>', true);
    isLoading = true;
    updateSendButton();
    
    currentAbortController = new AbortController();
    
    try {
        const response = await fetch(`${API_BASE}/generate_image`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt: prompt, size: '1024x1024'}),
            signal: currentAbortController.signal
        });
        const data = await response.json();
        if (data.success && data.image_data) {
            let mime = 'image/png';
            const b64 = data.image_data;
            const imagePath = data.image_path || '';
            
            if (b64.startsWith('/9j')) mime = 'image/jpeg';
            else if (b64.startsWith('iVB')) mime = 'image/png';
            
            const revised = data.revised_prompt ? `\n\n**提示词**: ${data.revised_prompt}` : '';
            
            // Use file path if available, otherwise use base64
            const imgSrc = imagePath ? imagePath : `data:${mime};base64,${b64}`;
            const content = `已为你生成图片：\n\n<img src="${imgSrc}" style="max-width:100%;border-radius:8px;margin:8px 0;">${revised}`;
            
            updateMessage(loadingId, content);
        } else {
            updateMessage(loadingId, '错误: ' + (data.error || '图片生成失败'));
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            updateMessage(loadingId, '已停止生成');
        } else {
            updateMessage(loadingId, '网络错误，请重试');
        }
    } finally {
        currentAbortController = null;
        isLoading = false;
        updateSendButton();
        await loadConversationList();
    }
}

async function doFaceRecognition(file) {
    const originalDataUrl = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.readAsDataURL(file);
    });

    addMessage('user', `<div style="margin:4px 0;">👤 人脸识别: ${file.name}</div><img src="${originalDataUrl}" style="max-width:200px;border-radius:8px;margin-top:6px;border:1px solid #eee;">`);
    const loadingId = addMessage('assistant', '<span class="loading">正在识别人脸...</span>', true);
    isLoading = true;
    updateSendButton();

    try {
        const formData = new FormData();
        formData.append('image', file);
        const response = await fetch(`${API_BASE}/face_recognize`, {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();

        if (!data.success) {
            updateMessage(loadingId, '❌ 人脸识别失败: ' + (data.error || '未知错误'));
        } else if (data.faces_found === 0) {
            updateMessage(loadingId, `
                <div style="margin:8px 0;">🤔 未检测到人脸，请上传包含清晰人脸的图片</div>
                <div style="display:flex;gap:12px;margin-top:10px;align-items:flex-start;">
                    <div style="flex:1;">
                        <div style="font-size:12px;color:#888;margin-bottom:4px;">📷 原始图片</div>
                        <img src="${originalDataUrl}" style="max-width:100%;border-radius:8px;border:1px solid #eee;">
                    </div>
                </div>
            `);
        } else {
            const results = data.results;
            let html = `<div style="margin:8px 0;"><strong>检测到 ${data.faces_found} 张人脸：</strong></div>`;
            html += `<div style="display:flex;gap:12px;margin-top:10px;align-items:flex-start;flex-wrap:wrap;">`;
            html += `<div style="flex:1;min-width:200px;">
                <div style="font-size:12px;color:#888;margin-bottom:4px;">📷 原始图片</div>
                <img src="${originalDataUrl}" style="max-width:100%;border-radius:8px;border:1px solid #eee;">
            </div>`;
            if (data.annotated_image) {
                html += `<div style="flex:1;min-width:200px;">
                    <div style="font-size:12px;color:#888;margin-bottom:4px;">🎯 识别标注</div>
                    <img src="${data.annotated_image}" style="max-width:100%;border-radius:8px;border:1px solid #eee;">
                </div>`;
            }
            html += `</div>`;
            results.forEach((r, i) => {
                const isUnknown = r.name === 'Unknown';
                const topProbs = Object.entries(r.all_probs || {})
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 3);
                html += `
                    <div style="margin:10px 0;padding:10px 14px;background:${isUnknown ? '#fff5f5' : '#f0f9ff'};border-radius:8px;border-left:3px solid ${isUnknown ? '#ef4444' : '#22c55e'};">
                        <div style="font-weight:600;color:${isUnknown ? '#dc2626' : '#16a34a'};">
                            ${isUnknown ? '❓ 陌生人' : '✅ ' + r.name}
                            <span style="float:right;color:#666;font-weight:400;">置信度 ${(r.confidence * 100).toFixed(1)}%</span>
                        </div>
                        ${topProbs.length > 0 ? `<div style="margin-top:6px;font-size:12px;color:#888;">概率排名: ${topProbs.map(([n, p]) => `${n} ${(p * 100).toFixed(1)}%`).join(' · ')}</div>` : ''}
                    </div>
                `;
            });
            updateMessage(loadingId, html);
        }
    } catch (error) {
        updateMessage(loadingId, '人脸识别出错: ' + error.message);
    } finally {
        isLoading = false;
        updateSendButton();
        await loadConversationList();
    }
}

function addMessage(role, content, isLoading = false) {
    const messageId = 'msg-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + role;
    messageDiv.id = messageId;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '你' : 'AI';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatMessage(content);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    
    // Add action buttons for assistant messages
    if (role === 'assistant' && !isLoading) {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'message-actions';
        actionsDiv.innerHTML = `
            <button class="action-btn" data-action="copy" title="复制">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
            </button>
            <button class="action-btn" data-action="refresh" title="重新生成">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="23 4 23 10 17 10"></polyline>
                    <polyline points="1 20 1 14 7 14"></polyline>
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                </svg>
            </button>
            <button class="action-btn" data-action="thumbs-up" title="点赞">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                </svg>
            </button>
            <button class="action-btn" data-action="thumbs-down" title="点踩">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
                </svg>
            </button>
            <button class="action-btn" data-action="speak" title="朗读">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                </svg>
            </button>
            <button class="action-btn" data-action="share" title="分享">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="18" cy="5" r="3"></circle>
                    <circle cx="6" cy="12" r="3"></circle>
                    <circle cx="18" cy="19" r="3"></circle>
                    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
                </svg>
            </button>
            <button class="web-refs-btn" data-action="web-refs" title="查看引用来源">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"></path>
                </svg>
                <span class="web-refs-count">0 个网页</span>
            </button>
            <button class="action-btn" data-action="download" title="下载">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
            </button>
        `;
        
        // Store original content for actions
        contentDiv.dataset.originalContent = content;
        
        // Add event listeners for actions
        actionsDiv.querySelectorAll('.action-btn, .web-refs-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = btn.dataset.action;
                handleAction(action, messageId, contentDiv);
            });
        });
        
        messageDiv.appendChild(actionsDiv);
    }
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Update web references count for new messages
    if (role === 'assistant' && !isLoading) {
        updateWebRefsCount(messageId, content);
    }
    
    return messageId;
}

function updateMessage(messageId, content) {
    const div = document.getElementById(messageId);
    if (div) {
        const contentDiv = div.querySelector('.message-content');
        contentDiv.innerHTML = formatMessage(content);
        contentDiv.dataset.originalContent = content;
        
        // Update web references count
        updateWebRefsCount(messageId, content);
        
        // Remove existing actions if any
        const existingActions = div.querySelector('.message-actions');
        if (existingActions) {
            existingActions.remove();
        }
        
        // Add action buttons for assistant messages
        if (div.classList.contains('assistant')) {
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';
            actionsDiv.innerHTML = `
                <button class="action-btn" data-action="copy" title="复制">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                </button>
                <button class="action-btn" data-action="refresh" title="重新生成">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 4 23 10 17 10"></polyline>
                        <polyline points="1 20 1 14 7 14"></polyline>
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                    </svg>
                </button>
                <button class="action-btn" data-action="thumbs-up" title="点赞">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                    </svg>
                </button>
                <button class="action-btn" data-action="thumbs-down" title="点踩">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
                    </svg>
                </button>
                <button class="action-btn" data-action="speak" title="朗读">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                    </svg>
                </button>
                <button class="action-btn" data-action="share" title="分享">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="18" cy="5" r="3"></circle>
                        <circle cx="6" cy="12" r="3"></circle>
                        <circle cx="18" cy="19" r="3"></circle>
                        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                        <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
                    </svg>
                </button>
                <button class="web-refs-btn" data-action="web-refs" title="查看引用来源">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"></path>
                    </svg>
                    <span class="web-refs-count">0 个网页</span>
                </button>
                <button class="action-btn" data-action="download" title="下载">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                </button>
            `;
            
            actionsDiv.querySelectorAll('.action-btn, .web-refs-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const action = btn.dataset.action;
                    handleAction(action, messageId, contentDiv);
                });
            });
            
            div.appendChild(actionsDiv);
        }
        
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function formatMessage(content) {
    if (!content) return '';
    return content
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

async function clearHistory() {
    attachments = [];
    renderAttachments();
    try {
        const response = await fetch(`${API_BASE}/clear`, {method: 'POST'});
        const data = await response.json();
        if (data.success) {
            messagesContainer.innerHTML = '';
            welcomeMessage.style.display = 'block';
        }
    } catch (error) {
        alert('清空失败');
    }
}

async function toggleSearch() {
    try {
        const response = await fetch(`${API_BASE}/toggle_search`, {method: 'POST'});
        const data = await response.json();
        if (!data.success) {
            searchToggle.checked = !searchToggle.checked;
            alert('切换失败: ' + data.error);
        }
    } catch (error) {
        searchToggle.checked = !searchToggle.checked;
        alert('切换失败');
    }
}

let lastDragTarget = null;
let currentSpeech = null;
let currentConversationId = null;
let currentAbortController = null;

function stopGeneration() {
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
        showToast('已停止生成');
    }
    
    isLoading = false;
    updateSendButton();
}

function handleAction(action, messageId, contentDiv) {
    const originalContent = contentDiv.dataset.originalContent || contentDiv.textContent;
    const plainText = originalContent.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/<br>/g, '\n');
    
    switch(action) {
        case 'copy':
            copyToClipboard(plainText);
            break;
        case 'refresh':
            regenerateResponse(messageId);
            break;
        case 'thumbs-up':
            handleFeedback(messageId, 'up');
            break;
        case 'thumbs-down':
            handleFeedback(messageId, 'down');
            break;
        case 'speak':
            speakText(plainText);
            break;
        case 'share':
            shareContent(plainText);
            break;
        case 'web-refs':
            handleWebRefs(messageId, contentDiv);
            break;
        case 'download':
            downloadContent(plainText);
            break;
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('已复制到剪贴板');
    }).catch(err => {
        console.error('复制失败:', err);
        showToast('复制失败，请手动复制');
    });
}

function regenerateResponse(messageId) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;
    
    // Find the previous user message
    const previousMessage = messageDiv.previousElementSibling;
    if (!previousMessage || !previousMessage.classList.contains('user')) {
        showToast('无法重新生成：找不到用户问题');
        return;
    }
    
    const userQuestion = previousMessage.querySelector('.message-content').textContent;
    
    // Remove the current assistant message
    messageDiv.remove();
    
    // Send the question again
    if (isLoading) return;
    isLoading = true;
    updateSendButton();
    
    doChat(userQuestion).then(() => {
        isLoading = false;
        updateSendButton();
    });
}

function handleFeedback(messageId, type) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;
    
    // Toggle the active state
    const actionsDiv = messageDiv.querySelector('.message-actions');
    const upBtn = actionsDiv.querySelector('[data-action="thumbs-up"]');
    const downBtn = actionsDiv.querySelector('[data-action="thumbs-down"]');
    
    if (type === 'up') {
        upBtn.classList.toggle('active');
        downBtn.classList.remove('active');
        if (upBtn.classList.contains('active')) {
            showToast('已点赞');
        }
    } else {
        downBtn.classList.toggle('active');
        upBtn.classList.remove('active');
        if (downBtn.classList.contains('active')) {
            showToast('已点踩');
        }
    }
    
    // Here you could send feedback to your backend
    console.log(`Feedback: ${type} for message ${messageId}`);
}

function speakText(text) {
    if (currentSpeech) {
        window.speechSynthesis.cancel();
        currentSpeech = null;
        showToast('已停止朗读');
        return;
    }
    
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'zh-CN';
        utterance.rate = 1;
        utterance.pitch = 1;
        
        utterance.onend = () => {
            currentSpeech = null;
        };
        
        utterance.onerror = () => {
            currentSpeech = null;
            showToast('朗读失败');
        };
        
        currentSpeech = utterance;
        window.speechSynthesis.speak(utterance);
        showToast('正在朗读...');
    } else {
        showToast('您的浏览器不支持语音合成');
    }
}

function shareContent(text) {
    if (navigator.share) {
        navigator.share({
            title: '智面 AI',
            text: text
        }).catch(err => {
            console.log('分享失败:', err);
        });
    } else {
        // Fallback: copy to clipboard
        copyToClipboard(text);
        showToast('已复制内容，可手动分享');
    }
}

function showToast(message) {
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

function handleWebRefs(messageId, contentDiv) {
    const originalContent = contentDiv.dataset.originalContent || contentDiv.textContent;
    
    // Extract URLs from the content
    const urlRegex = /https?:\/\/[^\s<>"{}|\\^`\[\]]+/g;
    const urls = originalContent.match(urlRegex) || [];
    
    if (urls.length === 0) {
        showToast('此回答未引用网页来源');
        return;
    }
    
    // Create a modal to show the references
    const modal = document.createElement('div');
    modal.className = 'web-refs-modal';
    modal.innerHTML = `
        <div class="web-refs-content">
            <div class="web-refs-header">
                <h3>引用来源 (${urls.length} 个网页)</h3>
                <button class="web-refs-close">&times;</button>
            </div>
            <div class="web-refs-list">
                ${urls.map((url, index) => `
                    <div class="web-ref-item">
                        <span class="web-ref-number">${index + 1}</span>
                        <a href="${url}" target="_blank" class="web-ref-link">${url}</a>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close modal functionality
    const closeBtn = modal.querySelector('.web-refs-close');
    closeBtn.addEventListener('click', () => {
        modal.classList.add('closing');
        setTimeout(() => modal.remove(), 300);
    });
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('closing');
            setTimeout(() => modal.remove(), 300);
        }
    });
    
    setTimeout(() => modal.classList.add('show'), 10);
}

function updateWebRefsCount(messageId, content) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;
    
    const urlRegex = /https?:\/\/[^\s<>"{}|\\^`\[\]]+/g;
    const urls = content.match(urlRegex) || [];
    
    const webRefsBtn = messageDiv.querySelector('.web-refs-btn');
    if (webRefsBtn) {
        const countSpan = webRefsBtn.querySelector('.web-refs-count');
        if (countSpan) {
            countSpan.textContent = `${urls.length} 个网页`;
        }
        
        // Hide the button if no references
        if (urls.length === 0) {
            webRefsBtn.style.display = 'none';
        }
    }
}

function downloadContent(content) {
    // Create download format selection modal
    const modal = document.createElement('div');
    modal.className = 'download-modal';
    modal.innerHTML = `
        <div class="download-content">
            <div class="download-header">
                <h3>下载内容</h3>
                <button class="download-close">&times;</button>
            </div>
            <div class="download-body">
                <div class="form-group">
                    <label for="fileFormat">文件格式</label>
                    <select id="fileFormat">
                        <option value="txt">纯文本 (.txt)</option>
                        <option value="md">Markdown (.md)</option>
                        <option value="html">HTML (.html)</option>
                        <option value="json">JSON (.json)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="fileName">文件名</label>
                    <input type="text" id="fileName" value="ai_response_${new Date().getTime()}" placeholder="输入文件名">
                </div>
            </div>
            <div class="download-footer">
                <button class="btn-secondary download-cancel">取消</button>
                <button class="btn-primary download-confirm">下载</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close modal functionality
    const closeBtn = modal.querySelector('.download-close');
    const cancelBtn = modal.querySelector('.download-cancel');
    const confirmBtn = modal.querySelector('.download-confirm');
    
    const closeModal = () => {
        modal.classList.add('closing');
        setTimeout(() => modal.remove(), 300);
    };
    
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
    
    // Download functionality
    confirmBtn.addEventListener('click', () => {
        const format = document.getElementById('fileFormat').value;
        let fileName = document.getElementById('fileName').value.trim() || 'ai_response';
        
        // Add extension if not present
        if (!fileName.includes('.')) {
            fileName += '.' + format;
        }
        
        let fileContent = content;
        let mimeType = 'text/plain';
        
        switch(format) {
            case 'md':
                // Convert to Markdown format
                fileContent = content
                    .replace(/\*\*([^*]+)\*\*/g, '**$1**')
                    .replace(/\*([^*]+)\*/g, '*$1*')
                    .replace(/```(\w*)\n([\s\S]*?)```/g, '```$1\n$2```')
                    .replace(/`([^`]+)`/g, '`$1`')
                    .replace(/<br>/g, '\n')
                    .replace(/<[^>]*>/g, '');
                mimeType = 'text/markdown';
                break;
            case 'html':
                // Convert to HTML format
                fileContent = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI回复</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        pre { background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }
        code { font-family: 'Courier New', monospace; }
        strong { font-weight: 600; }
    </style>
</head>
<body>
    ${content.replace(/\n/g, '<br>')}
</body>
</html>`;
                mimeType = 'text/html';
                break;
            case 'json':
                // Convert to JSON format
                fileContent = JSON.stringify({
                    content: content,
                    timestamp: new Date().toISOString(),
                    type: 'ai_response'
                }, null, 2);
                mimeType = 'application/json';
                break;
            default:
                // Plain text - remove HTML tags
                fileContent = content.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ');
                mimeType = 'text/plain';
        }
        
        // Create download link
        const blob = new Blob([fileContent], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('下载已开始');
        closeModal();
    });
    
    setTimeout(() => modal.classList.add('show'), 10);
}

messagesContainer.addEventListener('click', (e) => {
    const img = e.target.closest('.message-content img');
    if (img) {
        openImageViewer(img.src, img.alt || 'AI生成图片');
    }
});

function openImageViewer(src, alt) {
    const existing = document.querySelector('.image-viewer');
    if (existing) existing.remove();

    const viewer = document.createElement('div');
    viewer.className = 'image-viewer';
    viewer.innerHTML = `
        <button class="image-viewer-close" title="关闭 (ESC)">&times;</button>
        <div class="image-viewer-content">
            <img src="${src}" alt="${alt}" draggable="false">
        </div>
        <div class="image-viewer-toolbar">
            <button class="image-viewer-btn" id="viewerDownload">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                下载
            </button>
            <button class="image-viewer-btn" id="viewerOpenNew">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                    <polyline points="15 3 21 3 21 9"></polyline>
                    <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
                新窗口打开
            </button>
        </div>
    `;
    document.body.appendChild(viewer);

    const closeViewer = () => {
        viewer.classList.add('closing');
        setTimeout(() => viewer.remove(), 300);
        document.removeEventListener('keydown', onKeyDown);
        document.body.style.overflow = '';
    };

    const onKeyDown = (ev) => {
        if (ev.key === 'Escape') closeViewer();
    };

    viewer.addEventListener('click', (ev) => {
        if (ev.target === viewer || ev.target.classList.contains('image-viewer-close')) {
            closeViewer();
        }
    });

    viewer.querySelector('#viewerOpenNew').addEventListener('click', () => {
        window.open(src, '_blank');
    });

    viewer.querySelector('#viewerDownload').addEventListener('click', () => {
        const a = document.createElement('a');
        a.href = src;
        a.download = `image_${Date.now()}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('图片下载中...');
    });

    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';

    requestAnimationFrame(() => viewer.classList.add('show'));
}