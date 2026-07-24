/**
 * Multi-Agent Orchestrator — Production Frontend
 *
 * Key improvements over v1:
 *  - No alert() — replaced by a toast notification system
 *  - DOMPurify sanitization on all LLM markdown (XSS prevention)
 *  - Abort controller to cancel in-flight runs
 *  - Live agent status cards in sidebar
 *  - Execution metadata display (steps, time, status)
 *  - Copy-to-clipboard on every code block
 *  - "Copy All" results button
 *  - Run history stored in localStorage (last 5 runs)
 *  - /api/status fetch on load to show mode badge
 *  - Character counter on textarea
 *  - Quick-start example chips
 */

document.addEventListener('DOMContentLoaded', () => {

    /* ── Element refs ───────────────────────────────────────────────────── */
    const form        = document.getElementById('task-form');
    const taskInput   = document.getElementById('task');
    const charCounter = document.getElementById('char-counter');
    const inputError  = document.getElementById('input-error');
    const runBtn      = document.getElementById('run-btn');
    const btnLabel    = document.getElementById('btn-label');
    const btnSpinner  = document.getElementById('btn-spinner');
    const abortBtn    = document.getElementById('abort-btn');

    const tracePanel  = document.getElementById('trace-panel');
    const traceBox    = document.getElementById('trace-container');
    const stepCounter = document.getElementById('step-counter');

    const resultsPanel  = document.getElementById('results-panel');
    const resultsContent = document.getElementById('results-content');
    const copyAllBtn    = document.getElementById('copy-all-btn');

    const errorPanel = document.getElementById('error-panel');
    const errorList  = document.getElementById('error-list');

    const runMeta   = document.getElementById('run-meta');
    const metaSteps  = document.getElementById('meta-steps');
    const metaTime   = document.getElementById('meta-time');
    const metaStatus = document.getElementById('meta-status');

    const modeBadge = document.getElementById('mode-badge');
    const modeText  = document.getElementById('mode-text');
    const historyList = document.getElementById('history-list');

    let abortController = null;
    let stepCount = 0;

    /* ── Fetch mode on load ─────────────────────────────────────────────── */
    // STATIC DEMO: Hardcoded status
    modeText.textContent = 'Static Demo';
    modeBadge.classList.add('live');

    /* ── Character counter ──────────────────────────────────────────────── */
    taskInput.addEventListener('input', () => {
        const len = taskInput.value.length;
        charCounter.textContent = `${len} / 2000`;
        charCounter.classList.toggle('near-limit', len > 1600);
        charCounter.classList.toggle('at-limit', len >= 2000);
    });

    /* ── Quick-start chips ──────────────────────────────────────────────── */
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            taskInput.value = chip.dataset.prompt;
            taskInput.dispatchEvent(new Event('input'));
            taskInput.focus();
        });
    });

    /* ── Run history (localStorage) ─────────────────────────────────────── */
    function loadHistory() {
        const runs = JSON.parse(localStorage.getItem('mao_history') || '[]');
        historyList.innerHTML = '';
        if (!runs.length) {
            historyList.innerHTML = '<p class="history-empty">No runs yet</p>';
            return;
        }
        runs.slice(0, 5).forEach(r => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.innerHTML = `
                <div>${r.task.slice(0, 55)}${r.task.length > 55 ? '…' : ''}</div>
                <div class="hi-meta">${r.date} · ${r.status}</div>`;
            item.addEventListener('click', () => {
                taskInput.value = r.task;
                taskInput.dispatchEvent(new Event('input'));
            });
            historyList.appendChild(item);
        });
    }

    function saveToHistory(task, status) {
        const runs = JSON.parse(localStorage.getItem('mao_history') || '[]');
        runs.unshift({
            task, status,
            date: new Date().toLocaleString('en-US', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }),
        });
        localStorage.setItem('mao_history', JSON.stringify(runs.slice(0, 10)));
        loadHistory();
    }

    loadHistory();

    /* ── Toast system ───────────────────────────────────────────────────── */
    const toastContainer = document.getElementById('toast-container');

    function showToast(message, type = 'info', duration = 4000) {
        const icons = { error: '✕', success: '✓', info: 'ℹ' };
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `<span>${icons[type]}</span><span>${message}</span>`;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.classList.add('removing');
            toast.addEventListener('animationend', () => toast.remove());
        }, duration);
    }

    /* ── Agent card state machine ───────────────────────────────────────── */
    const agentCards = {
        planner: document.getElementById('card-planner'),
        scheduler: document.getElementById('card-scheduler'),
        worker: document.getElementById('card-worker'),
    };

    const statusLabels = {
        idle:    'Idle',
        running: 'Working…',
        done:    'Done',
        error:   'Error',
    };

    function setAgentState(agent, state) {
        const card = agentCards[agent];
        if (!card) return;
        card.classList.remove('running', 'done', 'error');
        if (state !== 'idle') card.classList.add(state);
        card.querySelector('.agent-status-text').textContent = statusLabels[state] || state;
    }

    function resetAgents() {
        Object.keys(agentCards).forEach(a => setAgentState(a, 'idle'));
    }

    /* ── Trace builder ──────────────────────────────────────────────────── */
    function addNodeToTrace(text, colorClass) {
        if (traceBox.children.length > 0) {
            const arrow = document.createElement('div');
            arrow.className = 'trace-arrow';
            arrow.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>`;
            traceBox.appendChild(arrow);
        }
        const node = document.createElement('div');
        node.className = `trace-node ${colorClass} active`;
        const icons = { planner:'🧠', scheduler:'⚙️', worker:'🛠️', end:'🏁' };
        const key = text.toLowerCase();
        node.innerHTML = `${icons[key] || ''} ${text}`;
        traceBox.appendChild(node);

        const allNodes = traceBox.querySelectorAll('.trace-node');
        if (allNodes.length > 1) allNodes[allNodes.length - 2].classList.remove('active');

        traceBox.parentElement.scrollLeft = traceBox.parentElement.scrollWidth;
    }

    /* ── Copy helpers ───────────────────────────────────────────────────── */
    function attachCopyButtons(container) {
        container.querySelectorAll('pre').forEach(pre => {
            if (pre.querySelector('.code-copy-btn')) return;
            const btn = document.createElement('button');
            btn.className = 'code-copy-btn';
            btn.textContent = 'Copy';
            btn.addEventListener('click', () => {
                const code = pre.querySelector('code')?.innerText || pre.innerText;
                navigator.clipboard.writeText(code).then(() => {
                    btn.textContent = 'Copied!';
                    btn.classList.add('copied');
                    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
                });
            });
            pre.appendChild(btn);
        });
    }

    copyAllBtn.addEventListener('click', () => {
        const text = resultsContent.innerText;
        navigator.clipboard.writeText(text).then(() => showToast('Results copied to clipboard', 'success'));
    });

    /* ── Render final results (with DOMPurify) ──────────────────────────── */
    function renderFinalResults(finalState, meta) {
        // Show metadata
        if (meta) {
            metaSteps.textContent  = `${meta.step_count} steps`;
            metaTime.textContent   = `${meta.elapsed_seconds}s`;
            metaStatus.textContent = meta.status;
            runMeta.style.display  = 'flex';
        }

        // Show errors if any
        const errors = finalState?.errors || [];
        if (errors.length) {
            errorPanel.classList.remove('hidden');
            errorList.innerHTML = '';
            errors.forEach(e => {
                const li = document.createElement('li');
                li.textContent = e;
                errorList.appendChild(li);
            });
        }

        resultsPanel.classList.remove('hidden');
        resultsContent.innerHTML = '';

        if (!finalState?.messages) {
            resultsContent.innerHTML = '<p>No output produced.</p>';
            return;
        }

        finalState.messages.forEach(msg => {
            if (msg.role === 'user' || msg.name === 'user') return;

            const block = document.createElement('div');
            block.className = 'agent-result-block';

            let labelClass = 'worker';
            let icon = '🛠️';
            if (msg.name === 'Planner') {
                labelClass = 'planner';
                icon = '🧠';
            } else if (msg.name === 'Scheduler') {
                labelClass = 'scheduler';
                icon = '⚙️';
            }

            const label = document.createElement('div');
            label.className = `agent-label ${labelClass}`;
            label.textContent = `${icon} ${msg.name}`;

            const content = document.createElement('div');
            content.className = 'markdown-body';
            // DOMPurify sanitization — mandatory before innerHTML
            const rawHtml = marked.parse(msg.content || '');
            content.innerHTML = DOMPurify.sanitize(rawHtml);

            block.appendChild(label);
            block.appendChild(content);
            resultsContent.appendChild(block);

            attachCopyButtons(content);
        });

        resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /* ── Input validation ───────────────────────────────────────────────── */
    function validateTask(task) {
        if (!task || task.trim().length < 10) {
            return 'Please describe your objective in at least 10 characters.';
        }
        if (task.length > 2000) {
            return 'Objective must be under 2000 characters.';
        }
        return null;
    }

    /* ── Main form submit ───────────────────────────────────────────────── */
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const task = taskInput.value.trim();
        const validationError = validateTask(task);

        inputError.classList.add('hidden');
        if (validationError) {
            inputError.textContent = validationError;
            inputError.classList.remove('hidden');
            return;
        }

        // Hide keyboard on mobile to trigger zoom-out
        taskInput.blur();

        // Reset UI
        traceBox.innerHTML = '';
        resultsContent.innerHTML = '';
        errorList.innerHTML = '';
        tracePanel.classList.remove('hidden');
        resultsPanel.classList.add('hidden');
        errorPanel.classList.add('hidden');
        runMeta.style.display = 'none';
        stepCount = 0;
        stepCounter.textContent = 'Step 0';
        resetAgents();

        runBtn.disabled = true;
        btnLabel.textContent = 'Workflow Running…';
        btnSpinner.classList.remove('hidden');
        abortBtn.classList.remove('hidden');

        abortController = new AbortController();

        let finalMeta = null;

        try {
            // STATIC DEMO: Mock Streamer
            const delay = ms => new Promise(res => setTimeout(res, ms));

            const mockEvents = [
                { node: 'planner', update: null, delayMs: 800 },
                { node: 'scheduler',  update: null, delayMs: 400 },
                { node: 'worker', update: null, delayMs: 1500 },
                { node: 'scheduler',       update: null, delayMs: 400 },
                { node: 'worker', update: null, delayMs: 1200 },
                { node: 'scheduler',    update: null, delayMs: 400 },
                { 
                    node: 'END', 
                    update: { 
                        status: "finished",
                        step_count: 6,
                        messages: [
                            {
                                name: "Planner",
                                role: "system",
                                content: "Generated DAG of 2 tasks: [Research Objective, Build Solution]"
                            },
                            {
                                name: "Worker-t1",
                                role: "system",
                                content: "Task t1 completed:\nFound 3 relevant sources for the objective using Wikipedia Tool."
                            },
                            {
                                name: "Worker-t2",
                                role: "system",
                                content: "Task t2 completed:\nSuccessfully built the solution using Python FileSystem Tool.\n\n**To run real prompts and use live LLMs, please go to GitHub and follow the Quick Start instructions to clone the repo and add your API key!**"
                            }
                        ]
                    }, 
                    meta: { step_count: 6, elapsed_seconds: 4.7, status: "completed" }, 
                    delayMs: 200 
                }
            ];

            for (const event of mockEvents) {
                if (abortController.signal.aborted) throw new DOMException("Aborted", "AbortError");
                await delay(event.delayMs);
                if (abortController.signal.aborted) throw new DOMException("Aborted", "AbortError");
                
                const data = event;

                if (data.node === 'END') {
                    finalMeta = data.meta;
                    addNodeToTrace('End', 'node-end');
                    Object.keys(agentCards).forEach(a => {
                        const card = agentCards[a];
                        if (card.classList.contains('running')) setAgentState(a, 'done');
                    });
                    renderFinalResults(data.update, data.meta);
                    saveToHistory(task, data.meta?.status || 'completed');
                    showToast('Workflow completed successfully', 'success');

                } else if (data.node === 'ERROR') {
                    showToast(`Execution error: ${data.error}`, 'error', 6000);
                    addNodeToTrace('Error', 'node-end');
                    saveToHistory(task, 'error');

                } else {
                    // Normal node transition
                    stepCount++;
                    stepCounter.textContent = `Step ${stepCount}`;
                    const label = data.node.charAt(0).toUpperCase() + data.node.slice(1);
                    addNodeToTrace(label, `node-${data.node}`);

                    // Update sidebar agent card
                    resetAgents();
                    if (agentCards[data.node]) setAgentState(data.node, 'running');
                }
            }

        } catch (err) {
            if (err.name === 'AbortError') {
                showToast('Workflow aborted', 'info');
                addNodeToTrace('Aborted', 'node-end');
            } else {
                showToast(`Error: ${err.message}`, 'error', 7000);
                console.error(err);
            }
        } finally {
            runBtn.disabled = false;
            btnLabel.textContent = 'Execute Workflow';
            btnSpinner.classList.add('hidden');
            abortBtn.classList.add('hidden');
            abortController = null;
            resetAgents();
        }
    });

    /* ── Abort button ───────────────────────────────────────────────────── */
    abortBtn.addEventListener('click', () => {
        if (abortController) {
            abortController.abort();
            showToast('Aborting workflow…', 'info');
        }
    });

});
