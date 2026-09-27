/**
 * Multi-Agent Workflow — Frontend Application (Enhanced)
 * 
 * SSE ile gercek zamanli agent durum guncellemeleri alir.
 * Word (.docx) indirme destegi.
 */

// ============================================
// Configuration
// ============================================
const API_BASE_URL = "http://localhost:8000";

// ============================================
// State
// ============================================
let isRunning = false;
let currentDocId = "";
let currentResults = {
    research_data: "",
    draft: "",
    review: "",
    final_output: "",
};

// Chat Scoping State
let chatHistory = [];
let currentScope = {
    task: "",
    paper_title: "",
    focus_area: "",
    paper_type: "Hakemli Bilimsel Dergi Makalesi",
    target_platform: "DergiPark (TÜBİTAK ULAKBİM TR Dizin)",
    target_pages: "10-15 Sayfa (Standart)",
    target_images: 4,
    scope_details: ""
};

// ============================================
// Initialization & Enter Key Support
// ============================================

document.addEventListener("DOMContentLoaded", () => {
    const taskInput = document.getElementById("taskInput");
    if (taskInput) {
        taskInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleChatSubmit();
            }
        });
    }
});

// ============================================
// Interactive Scoping Chat Functions
// ============================================

async function handleChatSubmit() {
    const taskInput = document.getElementById("taskInput");
    if (!taskInput) return;
    const userText = taskInput.value.trim();

    if (!userText) {
        showNotification("Lütfen önce bir araştırma konusu veya danışmana iletmek istediğiniz soruyu yazın.", "warning");
        taskInput.focus();
        return;
    }

    // Buton durumunu 'İletiliyor...' yap
    const sendBtn = document.getElementById("sendChatBtn");
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = `<span class="loading-spinner"></span><span class="btn-text">Danışman İnceliyor...</span>`;
    }

    // Kullanici mesajini ekle
    appendChatBubble("user", userText);
    taskInput.value = "";

    // Eger ana konu henuz yoksa bu ilk mesaj ana konudur
    if (!currentScope.task) {
        currentScope.task = userText;
    }

    updateScopeBadges();

    // Danisman 'Yaziyor...' balonu
    const loadingBubbleId = appendLoadingBubble();

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat-scope`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: userText,
                history: chatHistory,
                current_scope: currentScope,
            }),
        });

        removeBubble(loadingBubbleId);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        
        // Danisman cevabini ekle
        appendChatBubble("advisor", data.reply || "Konunuz harika! Aşağıdaki odak alanlarından birini seçebilir veya doğrudan makaleyi başlatabilirsiniz.");

        // Kapsami guncelle
        if (data.updated_scope) {
            if (data.updated_scope.task) currentScope.task = data.updated_scope.task;
            if (data.updated_scope.paper_title) currentScope.paper_title = data.updated_scope.paper_title;
            if (data.updated_scope.focus_area) currentScope.focus_area = data.updated_scope.focus_area;
            if (data.updated_scope.paper_type) currentScope.paper_type = data.updated_scope.paper_type;
            if (data.updated_scope.target_platform) currentScope.target_platform = data.updated_scope.target_platform;
            if (data.updated_scope.target_pages) currentScope.target_pages = data.updated_scope.target_pages;
            if (data.updated_scope.target_images) currentScope.target_images = data.updated_scope.target_images;
            if (data.updated_scope.scope_details) currentScope.scope_details = data.updated_scope.scope_details;
        }

        updateScopeBadges();

        // Oneri chiplerini render et
        renderOptionChips(data);

        // Butonu hazir hale getir ve vurgula
        const startBtn = document.getElementById("startWorkflowBtn");
        if (startBtn) {
            startBtn.classList.add("pulse-highlight");
        }

    } catch (err) {
        removeBubble(loadingBubbleId);
        console.error("Danisman hatasi:", err);
        appendChatBubble("advisor", `Araştırma konunuzu kaydettim: **${currentScope.task}**. Dilerseniz aşağıdaki başlat butonuna basarak doğrudan makale yazımını başlatabilirsiniz.`);
    } finally {
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = `<span class="btn-icon">💬</span><span class="btn-text">Danışmana İlet</span>`;
        }
        taskInput.focus();
    }
}

function appendChatBubble(role, content) {
    const chatMessages = document.getElementById("chatMessages");
    if (!chatMessages) return;

    chatHistory.push({ role, content });

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;

    const isAdvisor = role === "advisor";
    const avatar = isAdvisor ? "👨‍🏫" : "👤";
    const sender = isAdvisor ? "Akademik Baş Editör" : "Siz";

    // Basit Markdown render
    const renderedHtml = formatMarkdown(content);

    bubble.innerHTML = `
        <div class="bubble-header">
            <span class="avatar">${avatar}</span>
            <span class="sender-name">${sender}</span>
        </div>
        <div class="bubble-content">
            ${renderedHtml}
        </div>
    `;

    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendLoadingBubble() {
    const chatMessages = document.getElementById("chatMessages");
    if (!chatMessages) return null;

    const id = "loading_" + Date.now();
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble advisor";
    bubble.id = id;
    bubble.innerHTML = `
        <div class="bubble-header">
            <span class="avatar">👨‍🏫</span>
            <span class="sender-name">Akademik Baş Editör</span>
        </div>
        <div class="bubble-content">
            <p><em>Konu analiz ediliyor, alt alanlar taranıyor...</em></p>
        </div>
    `;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeBubble(id) {
    if (!id) return;
    const elem = document.getElementById(id);
    if (elem) elem.remove();
}

function renderOptionChips(data) {
    const optionsBox = document.getElementById("optionsBox");
    if (!optionsBox) return;

    const titleGroup = document.getElementById("titleChipsGroup");
    const titleList = document.getElementById("titleChipsList");
    const focusGroup = document.getElementById("focusChipsGroup");
    const focusList = document.getElementById("focusChipsList");
    const platformGroup = document.getElementById("platformChipsGroup");
    const platformList = document.getElementById("platformChipsList");
    const pageGroup = document.getElementById("pageChipsGroup");
    const pageList = document.getElementById("pageChipsList");
    const typeGroup = document.getElementById("paperTypeChipsGroup");
    const typeList = document.getElementById("paperTypeChipsList");
    const imgGroup = document.getElementById("imageChipsGroup");
    const imgList = document.getElementById("imageChipsList");

    let hasAny = false;

    // 0. Academic Title Options
    if (titleGroup && titleList && data.title_options && data.title_options.length > 0) {
        titleList.innerHTML = "";
        data.title_options.forEach(opt => {
            const btn = document.createElement("button");
            btn.className = "chip-btn" + (currentScope.paper_title === opt ? " selected" : "");
            btn.textContent = opt;
            btn.onclick = () => selectTitleOption(opt, btn);
            titleList.appendChild(btn);
        });
        titleGroup.style.display = "flex";
        hasAny = true;
    }

    // 1. Focus Options
    if (data.focus_options && data.focus_options.length > 0) {
        focusList.innerHTML = "";
        data.focus_options.forEach(opt => {
            const btn = document.createElement("button");
            btn.className = "chip-btn" + (currentScope.focus_area === opt ? " selected" : "");
            btn.textContent = opt;
            btn.onclick = () => selectFocusOption(opt, btn);
            focusList.appendChild(btn);
        });
        focusGroup.style.display = "flex";
        hasAny = true;
    }

    // 2. Platform Options
    if (platformGroup && platformList && data.platform_options && data.platform_options.length > 0) {
        platformList.innerHTML = "";
        data.platform_options.forEach(opt => {
            const btn = document.createElement("button");
            btn.className = "chip-btn" + (currentScope.target_platform === opt ? " selected" : "");
            btn.textContent = opt;
            btn.onclick = () => selectPlatformOption(opt, btn);
            platformList.appendChild(btn);
        });
        platformGroup.style.display = "flex";
        hasAny = true;
    }

    // 3. Page / Volume Options
    if (pageGroup && pageList && data.page_options && data.page_options.length > 0) {
        pageList.innerHTML = "";
        data.page_options.forEach(opt => {
            const btn = document.createElement("button");
            btn.className = "chip-btn" + (currentScope.target_pages === opt ? " selected" : "");
            btn.textContent = opt;
            btn.onclick = () => selectPageOption(opt, btn);
            pageList.appendChild(btn);
        });
        pageGroup.style.display = "flex";
        hasAny = true;
    }

    // 4. Paper Types
    if (data.paper_type_options && data.paper_type_options.length > 0) {
        typeList.innerHTML = "";
        data.paper_type_options.forEach(opt => {
            const btn = document.createElement("button");
            btn.className = "chip-btn" + (currentScope.paper_type === opt ? " selected" : "");
            btn.textContent = opt;
            btn.onclick = () => selectPaperTypeOption(opt, btn);
            typeList.appendChild(btn);
        });
        typeGroup.style.display = "flex";
        hasAny = true;
    }

    // 5. Image Options
    if (data.image_options && data.image_options.length > 0) {
        imgList.innerHTML = "";
        data.image_options.forEach(opt => {
            const btn = document.createElement("button");
            btn.className = "chip-btn";
            btn.textContent = opt;
            btn.onclick = () => selectImageOption(opt, btn);
            imgList.appendChild(btn);
        });
        imgGroup.style.display = "flex";
        hasAny = true;
    }

    optionsBox.style.display = hasAny ? "block" : "none";
}

function selectTitleOption(text, btnElement) {
    currentScope.paper_title = text;
    updateScopeBadges();

    const list = document.getElementById("titleChipsList");
    if (list) {
        list.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("selected"));
    }
    if (btnElement) btnElement.classList.add("selected");

    appendChatBubble("user", `🏷️ Makale Başlığı: "${text}"`);
    appendChatBubble("advisor", `Mükemmel bir akademik başlık! Makalenin kapak sayfası, üstbilgileri ve editoryal akışı **"${text}"** başlığı esas alınarak kurgulanacaktır.`);
}

function selectFocusOption(text, btnElement) {
    currentScope.focus_area = text;
    updateScopeBadges();
    
    // Chip secimi gorsel guncelle
    const list = document.getElementById("focusChipsList");
    if (list) {
        list.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("selected"));
    }
    if (btnElement) btnElement.classList.add("selected");

    appendChatBubble("user", `🎯 Odak Alanı: ${text}`);
    appendChatBubble("advisor", `Harika bir seçim. Araştırma ve kaynak taramasını **"${text}"** ekseninde derinleştireceğiz. Dilerseniz hemen **"Seçilen Kapsamla Makaleyi Başlat"** butonuna basabilirsiniz.`);
}

function selectPlatformOption(text, btnElement) {
    currentScope.target_platform = text;
    updateScopeBadges();

    const list = document.getElementById("platformChipsList");
    if (list) {
        list.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("selected"));
    }
    if (btnElement) btnElement.classList.add("selected");

    appendChatBubble("user", `🏛️ Hedef Platform: ${text}`);
    appendChatBubble("advisor", `Yayın formatı ve editoryal şablon **"${text}"** standartlarına göre kurgulanacaktır (kaynakça stili, başlıklar, özet ve bölümlendirme bu standarda uyarlanır).`);
}

function selectPageOption(text, btnElement) {
    currentScope.target_pages = text;
    updateScopeBadges();

    const list = document.getElementById("pageChipsList");
    if (list) {
        list.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("selected"));
    }
    if (btnElement) btnElement.classList.add("selected");

    appendChatBubble("user", `📑 Hedef Sayfa / Hacim: ${text}`);
    appendChatBubble("advisor", `Hedef sayfa hacmi **"${text}"** olarak belirlendi. Makale bölümleri, vaka analizleri ve atıf sıklığı bu sayfa derinliğini tam karşılayacak biçimde kurgulanacaktır.`);
}

function selectPaperTypeOption(text, btnElement) {
    currentScope.paper_type = text;
    updateScopeBadges();

    const list = document.getElementById("paperTypeChipsList");
    if (list) {
        list.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("selected"));
    }
    if (btnElement) btnElement.classList.add("selected");
}

function selectImageOption(text, btnElement) {
    const num = parseInt(text) || 4;
    currentScope.target_images = num;
    updateScopeBadges();

    const list = document.getElementById("imageChipsList");
    if (list) {
        list.querySelectorAll(".chip-btn").forEach(b => b.classList.remove("selected"));
    }
    if (btnElement) btnElement.classList.add("selected");
}

function updateScopeBadges() {
    const badgeTopic = document.getElementById("badgeTopic");
    const badgeTitleContainer = document.getElementById("badgeTitleContainer");
    const badgeTitle = document.getElementById("badgeTitle");
    const badgeFocus = document.getElementById("badgeFocus");
    const badgePlatform = document.getElementById("badgePlatform");
    const badgePages = document.getElementById("badgePages");
    const badgeType = document.getElementById("badgeType");
    const badgeImages = document.getElementById("badgeImages");

    if (badgeTopic) badgeTopic.textContent = currentScope.task || "Belirtilmedi";
    if (badgeTitleContainer && badgeTitle) {
        if (currentScope.paper_title) {
            badgeTitle.textContent = currentScope.paper_title;
            badgeTitleContainer.style.display = "flex";
        } else {
            badgeTitleContainer.style.display = "none";
        }
    }
    if (badgeFocus) badgeFocus.textContent = currentScope.focus_area || "Tüm Kapsam";
    if (badgeType) badgeType.textContent = currentScope.paper_type || "Hakemli Dergi Makalesi";
    if (badgeImages) badgeImages.textContent = `${currentScope.target_images} Adet`;

    if (badgePlatform) {
        let platName = currentScope.target_platform || "DergiPark (TR Dizin)";
        if (platName.includes("DergiPark")) platName = "DergiPark (TR Dizin)";
        else if (platName.includes("IEEE")) platName = "IEEE / Elsevier";
        else if (platName.includes("arXiv")) platName = "arXiv (Preprint)";
        else if (platName.includes("ResearchGate")) platName = "ResearchGate";
        else if (platName.includes("Medium")) platName = "Medium (TDS)";
        badgePlatform.textContent = platName;
    }

    if (badgePages) {
        let pText = currentScope.target_pages || "10-15 Sayfa";
        badgePages.textContent = pText.split(" ")[0] + " Sayfa";
    }
}

function resetChat() {
    chatHistory = [];
    currentScope = {
        task: "",
        paper_title: "",
        focus_area: "",
        paper_type: "Hakemli Bilimsel Dergi Makalesi",
        target_platform: "DergiPark (TÜBİTAK ULAKBİM TR Dizin)",
        target_pages: "10-15 Sayfa (Standart)",
        target_images: 4,
        scope_details: ""
    };
    updateScopeBadges();

    const chatMessages = document.getElementById("chatMessages");
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="chat-bubble advisor">
                <div class="bubble-header">
                    <span class="avatar">👨‍🏫</span>
                    <span class="sender-name">Akademik Baş Editör</span>
                </div>
                <div class="bubble-content">
                    <p>Sohbet sıfırlandı. Yazmak istediğiniz yeni araştırma konusunu aşağıya yazıp <strong>Enter</strong> tuşuna basınız.</p>
                </div>
            </div>
        `;
    }

    const optionsBox = document.getElementById("optionsBox");
    if (optionsBox) optionsBox.style.display = "none";
}

// ============================================
// Main Workflow Execution
// ============================================

function startWorkflowWithCurrentScope() {
    const taskInput = document.getElementById("taskInput");
    if (!currentScope.task && taskInput && taskInput.value.trim()) {
        currentScope.task = taskInput.value.trim();
        updateScopeBadges();
    }

    if (!currentScope.task) {
        showNotification("Lütfen önce bir araştırma konusu belirtin.", "warning");
        if (taskInput) taskInput.focus();
        return;
    }

    runWorkflowExecution(currentScope);
}

function quickStartWorkflow() {
    const taskInput = document.getElementById("taskInput");
    let task = currentScope.task;
    if (taskInput && taskInput.value.trim()) {
        task = taskInput.value.trim();
        currentScope.task = task;
    }

    if (!task) {
        showNotification("Lütfen bir araştırma konusu girin.", "warning");
        if (taskInput) taskInput.focus();
        return;
    }

    runWorkflowExecution(currentScope);
}

async function runWorkflowExecution(scope) {
    if (isRunning) return;

    isRunning = true;
    currentDocId = "";
    resetUI();
    showPipeline();
    showLogs();
    updateButton(true);

    const mainTitle = scope.paper_title || scope.task;
    const desc = scope.focus_area ? `${mainTitle} (${scope.focus_area})` : mainTitle;
    addLog(`Akademik monografi süreci başlatılıyor: "${desc}"...`, "system");
    setAgentStatus("researcher", "active", "Akademik veri tabanları taranıyor...");

    try {
        const response = await fetch(`${API_BASE_URL}/api/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                task: scope.task,
                paper_title: scope.paper_title || "",
                focus_area: scope.focus_area || "",
                paper_type: scope.paper_type || "Hakemli Bilimsel Dergi Makalesi",
                target_platform: scope.target_platform || "DergiPark (TÜBİTAK ULAKBİM TR Dizin)",
                target_pages: scope.target_pages || "10-15 Sayfa (Standart)",
                target_images: scope.target_images || 4,
                scope_details: scope.scope_details || "",
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const data = JSON.parse(line.substring(6));
                    handleSSEEvent(data);
                }
            }
        }

        onWorkflowComplete();

    } catch (error) {
        console.error("Workflow hatasi:", error);
        showError(error.message);
    }
}

function handleSSEEvent(data) {
    const { agent, status, logs, data: agentData, message, doc_id } = data;

    if (logs && logs.length > 0) {
        const latestLog = logs[logs.length - 1];
        const agentType = latestLog.includes("[Researcher]") ? "researcher"
            : latestLog.includes("[Writer]") ? "writer"
            : latestLog.includes("[Reviewer]") ? "reviewer"
            : "system";
        addLog(latestLog, agentType);
    }

    if (agent === "system") {
        if (status === "error") {
            showError(message || "Bilinmeyen hata");
        } else {
            addLog(message || "Workflow tamamlandi", "system");
            if (doc_id) {
                currentDocId = doc_id;
            }
        }
        return;
    }

    if (agent === "researcher") {
        setAgentStatus("researcher", "completed", "Tamamlandi");
        setAgentStatus("writer", "active", "Calisiyor...");
        if (agentData?.research_data) {
            currentResults.research_data = agentData.research_data;
            updateResultContent("researchOutput", agentData.research_data);
        }
    }

    if (agent === "writer") {
        setAgentStatus("writer", "completed", "Tamamlandi");
        setAgentStatus("reviewer", "active", "Degerlendiriliyor...");
        if (agentData?.draft) {
            currentResults.draft = agentData.draft;
            updateResultContent("draftOutput", agentData.draft);
        }
    }

    if (agent === "reviewer") {
        if (agentData?.review) {
            currentResults.review = agentData.review;
            updateResultContent("reviewOutput", agentData.review);
        }

        if (agentData?.review_status === "REVISE") {
            const revCount = agentData.revision_count || 1;
            setAgentStatus("reviewer", "completed", "Revizyon İstendi");
            showRevisionInfo(revCount);

            setTimeout(() => {
                setAgentStatus("writer", "active", `Genişletiliyor & Uzatılıyor (Revizyon #${revCount})...`);
                setAgentStatus("reviewer", "pending", "Sıradaki Değerlendirme");
            }, 500);
        } else if (agentData?.review_status === "APPROVE") {
            setAgentStatus("reviewer", "completed", "Onaylandi");
            if (agentData?.final_output) {
                currentResults.final_output = agentData.final_output;
                updateResultContent("finalOutput", agentData.final_output);
            }
        }
    }
}

function onWorkflowComplete() {
    isRunning = false;
    updateButton(false);
    showResults();

    if (!currentResults.final_output && currentResults.draft) {
        currentResults.final_output = currentResults.draft;
    }

    updateResultContent("researchOutput", currentResults.research_data);
    updateResultContent("draftOutput", currentResults.draft);
    updateResultContent("reviewOutput", currentResults.review);
    updateResultContent("finalOutput", currentResults.final_output);

    addLog("Workflow basariyla tamamlandi!", "system");

    // Word indir butonunu goster
    if (currentDocId) {
        showDownloadButton(currentDocId);
        addLog("Word belgesi olusturuldu - indirmeye hazir!", "system");
    }

    switchTab("final");
    showNotification("Workflow tamamlandi! Sonuclari inceleyebilirsiniz.", "success");
}

// ============================================
// Download Function
// ============================================

function downloadWord() {
    if (!currentDocId) {
        showNotification("Henuz bir belge olusturulmadi.", "warning");
        return;
    }

    const url = `${API_BASE_URL}/api/download/${currentDocId}`;
    
    const a = document.createElement("a");
    a.href = url;
    a.download = `makale_${currentDocId}.docx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    showNotification("Word belgesi indiriliyor...", "success");
}

function showDownloadButton() {
    const container = document.getElementById("downloadContainer");
    if (container) {
        container.style.display = "flex";
    }
}

// ============================================
// UI Helper Functions
// ============================================

function setAgentStatus(agent, status, text) {
    const step = document.getElementById(`step-${agent}`);
    const statusEl = document.getElementById(`status-${agent}`);
    if (!step || !statusEl) return;

    step.classList.remove("active", "completed", "error", "pending");
    if (status !== "pending") {
        step.classList.add(status);
    }
    statusEl.textContent = text || status;
}

function addLog(message, type = "system") {
    const container = document.getElementById("logsContainer");
    if (!container) return;

    const entry = document.createElement("div");
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString("tr-TR");

    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-message">${escapeHtml(message)}</span>
    `;

    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function updateResultContent(elementId, content) {
    const element = document.getElementById(elementId);
    if (!element || !content) return;
    element.innerHTML = formatMarkdown(content);
}

function switchTab(tabName) {
    document.querySelectorAll(".tab").forEach(tab => tab.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));

    const tabBtn = document.getElementById(`tab-${tabName}`);
    const tabContent = document.getElementById(`content-${tabName}`);
    if (tabBtn) tabBtn.classList.add("active");
    if (tabContent) tabContent.classList.add("active");
}

function showRevisionInfo(count) {
    const revisionInfo = document.getElementById("revisionInfo");
    const revisionText = document.getElementById("revisionText");
    if (revisionInfo && revisionText) {
        revisionInfo.style.display = "flex";
        revisionText.textContent = `Revizyon #${count} - Icerik iyilestiriliyor...`;
    }
}

function copyToClipboard() {
    const content = currentResults.final_output;
    if (!content) {
        showNotification("Kopyalanacak icerik yok.", "warning");
        return;
    }

    navigator.clipboard.writeText(content).then(() => {
        const btn = document.querySelector(".copy-btn");
        if (btn) {
            btn.textContent = "Kopyalandi!";
            btn.classList.add("copied");
            setTimeout(() => {
                btn.textContent = "Kopyala";
                btn.classList.remove("copied");
            }, 2000);
        }
    });
}

function showNotification(message, type = "info") {
    document.querySelectorAll(".notification").forEach(n => n.remove());

    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed; top: 1rem; right: 1rem; z-index: 1000;
        padding: 0.875rem 1.25rem; border-radius: 8px;
        font-family: 'Inter', sans-serif; font-size: 0.9rem; font-weight: 500;
        color: white; cursor: pointer;
        background: ${type === "success" ? "#10b981" : type === "warning" ? "#f59e0b" : type === "error" ? "#ef4444" : "#3b82f6"};
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); animation: fadeIn 0.3s ease;
    `;
    notification.textContent = message;
    notification.onclick = () => notification.remove();

    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 4000);
}

// ============================================
// UI State Management
// ============================================

function showPipeline() {
    const el = document.getElementById("pipelineSection");
    if (el) el.style.display = "block";
}

function showLogs() {
    const el = document.getElementById("logsSection");
    if (el) el.style.display = "block";
}

function showResults() {
    const el = document.getElementById("resultsSection");
    if (el) el.style.display = "block";
}

function showError(message) {
    isRunning = false;
    updateButton(false);

    const errorSection = document.getElementById("errorSection");
    const errorMessage = document.getElementById("errorMessage");
    if (errorSection && errorMessage) {
        errorSection.style.display = "block";
        errorMessage.textContent = message;
    }
    addLog(`HATA: ${message}`, "error");
}

function updateButton(loading) {
    const startWorkflowBtn = document.getElementById("startWorkflowBtn");
    const quickStartBtn = document.getElementById("quickStartBtn");
    const sendChatBtn = document.getElementById("sendChatBtn");

    if (loading) {
        if (startWorkflowBtn) {
            startWorkflowBtn.disabled = true;
            startWorkflowBtn.innerHTML = `<span class="loading-spinner"></span><span class="btn-text">Makale Yazılıyor (Ajanlar Aktif)...</span>`;
        }
        if (quickStartBtn) quickStartBtn.disabled = true;
        if (sendChatBtn) sendChatBtn.disabled = true;
    } else {
        if (startWorkflowBtn) {
            startWorkflowBtn.disabled = false;
            startWorkflowBtn.innerHTML = `<span class="btn-icon">🚀</span><span class="btn-text">Seçilen Kapsamla Makaleyi Başlat</span>`;
        }
        if (quickStartBtn) quickStartBtn.disabled = false;
        if (sendChatBtn) sendChatBtn.disabled = false;
    }
}

function resetUI() {
    const errorSection = document.getElementById("errorSection");
    if (errorSection) errorSection.style.display = "none";

    const revisionInfo = document.getElementById("revisionInfo");
    if (revisionInfo) revisionInfo.style.display = "none";

    const downloadContainer = document.getElementById("downloadContainer");
    if (downloadContainer) downloadContainer.style.display = "none";

    const logsContainer = document.getElementById("logsContainer");
    if (logsContainer) logsContainer.innerHTML = "";

    currentResults = { research_data: "", draft: "", review: "", final_output: "" };
    currentDocId = "";

    ["researchOutput", "draftOutput", "reviewOutput", "finalOutput"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<p class="placeholder">Yukleniyor...</p>';
    });

    ["researcher", "writer", "reviewer"].forEach(agent => {
        setAgentStatus(agent, "pending", "Bekliyor");
    });

    switchTab("research");
}

// ============================================
// Utility Functions
// ============================================

function formatMarkdown(text) {
    if (!text) return "";

    let html = escapeHtml(text);

    // Callout Kutulari (> 💡, > ⚠️, > 👤, > 📌, > 📜)
    html = html.replace(/^&gt; 📜 \*\*(?:TARİHSEL KİLOMETRE TAŞI|TARİHÇE|DÖNÜM NOKTASI):\*\*(.+?)$/gm, 
        '<div style="background: rgba(245, 158, 11, 0.15); border-left: 4px solid #f59e0b; padding: 0.75rem 1rem; border-radius: 6px; margin: 1rem 0;"><strong style="color: #fbbf24;">📜 TARİHSEL KİLOMETRE TAŞI:</strong><div style="margin-top: 0.25rem;">$1</div></div>');
    html = html.replace(/^&gt; 💡 \*\*(?:BUNU DA BİL\?|DERİN TEKNİK ANALİZ):\*\*(.+?)$/gm, 
        '<div style="background: rgba(2, 132, 199, 0.12); border-left: 4px solid #0284c7; padding: 0.75rem 1rem; border-radius: 6px; margin: 1rem 0;"><strong style="color: #38bdf8;">💡 DERİN TEKNİK ANALİZ:</strong><div style="margin-top: 0.25rem;">$1</div></div>');
    html = html.replace(/^&gt; ⚠️ \*\*(?:UYARI|DİKKAT|KRİTİK DARBOĞAZ):\*\*(.+?)$/gm, 
        '<div style="background: rgba(217, 119, 6, 0.15); border-left: 4px solid #d97706; padding: 0.75rem 1rem; border-radius: 6px; margin: 1rem 0;"><strong style="color: #fbbf24;">⚠️ UYARI / DİKKAT:</strong><div style="margin-top: 0.25rem;">$1</div></div>');
    html = html.replace(/^&gt; 👤 \*\*(?:KİMDİR\?|ÖNCÜ İSİM|TEORİSYEN):\*\*(.+?)$/gm, 
        '<div style="background: rgba(124, 58, 237, 0.15); border-left: 4px solid #7c3aed; padding: 0.75rem 1rem; border-radius: 6px; margin: 1rem 0;"><strong style="color: #c084fc;">👤 KİMDİR?</strong><div style="margin-top: 0.25rem;">$1</div></div>');
    html = html.replace(/^&gt; 📌 \*\*NOT ALINIZ:\*\*(.+?)$/gm, 
        '<div style="background: rgba(71, 85, 105, 0.2); border-left: 4px solid #64748b; padding: 0.75rem 1rem; border-radius: 6px; margin: 1rem 0;"><strong style="color: #94a3b8;">📌 NOT ALINIZ:</strong><div style="margin-top: 0.25rem;">$1</div></div>');

    // Genel blockquote
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote style="border-left: 3px solid #3b82f6; padding-left: 1rem; color: #94a3b8; margin: 0.5rem 0;">$1</blockquote>');

    // Gorseller: ![Alt Text](URL)
    html = html.replace(/!\[(.*?)\]\((https?:\/\/[^\)]+)\)/g, 
        '<div style="text-align: center; margin: 1.5rem 0;"><img src="$2" alt="$1" style="max-width: 100%; max-height: 420px; border-radius: 8px; border: 1px solid #334155; box-shadow: 0 4px 15px rgba(0,0,0,0.4);" onerror="this.parentElement.style.display=\'none\'" /><div style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.5rem; font-style: italic;">$1</div></div>');

    // 1. Markdown Linkleri: [text](url)
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)\s]+)\)/g, function(m, label, url) {
        let cleanUrl = url.replace(/\\/g, '').replace(/%5d/gi, '').replace(/[\(\)\[\]]+/g, '').trim();
        let cleanLabel = label.replace(/\\/g, '').trim();
        return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: underline; font-weight: 500;">${cleanLabel}</a>`;
    });

    // 2. Ham URL'ler (<a> etiketi disinda kalanlar): https://...
    html = html.replace(/(^|[^"'>])(https?:\/\/[^\s<>"'\)\]]+)/g, function(m, prefix, url) {
        let cleanUrl = url.replace(/\\/g, '').replace(/%5d/gi, '').replace(/[\]\)\.]+$/, '').trim();
        return `${prefix}<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: underline; word-break: break-all;">${cleanUrl}</a>`;
    });

    // Basliklar
    html = html.replace(/^### (.+)$/gm, '<h4 style="color: #38bdf8; margin: 1.25rem 0 0.5rem; font-size: 1.05rem;">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 style="color: #60a5fa; margin: 1.5rem 0 0.6rem; font-size: 1.2rem; border-bottom: 1px solid #1e293b; padding-bottom: 0.3rem;">$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2 style="color: #f1f5f9; margin: 1.75rem 0 0.75rem; font-size: 1.4rem;">$1</h2>');
    
    // Bold ve Italik
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong style="color: #f8fafc;">$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em style="color: #cbd5e1;">$1</em>');

    // Listeler
    html = html.replace(/^- (.+)$/gm, '<li style="margin-left: 1.5rem; margin-bottom: 0.25rem; color: #cbd5e1;">$1</li>');
    html = html.replace(/^\d+\. (.+)$/gm, '<li style="margin-left: 1.5rem; margin-bottom: 0.25rem; list-style-type: decimal; color: #cbd5e1;">$1</li>');

    // Satir sonlari
    html = html.replace(/\n\n/g, '<br><br>');
    html = html.replace(/\n/g, '<br>');

    return html;
}

function simpleMarkdown(text) {
    return formatMarkdown(text);
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Keyboard Shortcuts
// ============================================
document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        startWorkflowWithCurrentScope();
    }
});

// ============================================
// Init
// ============================================
document.addEventListener("DOMContentLoaded", () => {
    console.log("Multi-Agent Workflow UI baslatildi");
    const textarea = document.getElementById("taskInput");
    if (textarea) textarea.focus();
});
