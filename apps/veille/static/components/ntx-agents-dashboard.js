class NTXAgentsDashboard extends HTMLElement {
    connectedCallback() {
        this.innerHTML = `
            <section class="agents-dashboard-shell">
                <header class="agents-dashboard-header">
                    <div>
                        <p class="dashboard-kicker">Industrial Intel</p>
                        <h2 class="agents-dashboard-title">Featured Agents</h2>
                        <p class="agents-dashboard-copy">Start from the assistant, then jump into Veille's operational agents.</p>
                    </div>
                </header>
                <div class="agents-dashboard-grid" data-dashboard-grid></div>
            </section>`;
        this.#load();
    }

    async #load() {
        const grid = this.querySelector('[data-dashboard-grid]');
        if (!grid) return;

        const token = localStorage.getItem('jwtToken');
        const headers = token ? { 'x-access-token': token } : {};

        try {
            const [metaResp, agentsResp] = await Promise.all([
                fetch('/_meta'),
                fetch('/agents?limit=100', { headers }),
            ]);

            const meta = metaResp.ok ? await metaResp.json() : {};
            const agentPayload = agentsResp.ok ? await agentsResp.json() : { data: [] };
            const featured = meta?.app?.featured_agents || [];
            const rows = Array.isArray(agentPayload?.data) ? agentPayload.data : [];
            const ordered = this.#selectFeatured(rows, featured);

            if (!ordered.length) {
                grid.innerHTML = '<div class="agents-dashboard-empty">No featured agents configured.</div>';
                return;
            }

            grid.innerHTML = ordered.map((agent) => `
                <a class="agents-dashboard-card" href="#AgentActor/${agent.id}">
                    <div class="agents-dashboard-card-head">
                        <ntx-agent ref="AgentActor/${agent.id}" display="sm"></ntx-agent>
                    </div>
                    <p class="agents-dashboard-card-copy">${this.#escape(this.#summary(agent.prompt))}</p>
                    <div class="agents-dashboard-card-meta">
                        <span>${this.#escape(agent.llm || 'default llm')}</span>
                        <span>Open agent →</span>
                    </div>
                </a>`).join('');
        } catch (error) {
            grid.innerHTML = `<div class="agents-dashboard-empty">${this.#escape(error?.message || 'Failed to load featured agents.')}</div>`;
        }
    }

    #selectFeatured(rows, featured) {
        const selected = [];
        for (const spec of featured) {
            const match = rows.find((row) => {
                if (spec.system_key) return row.system_key === spec.system_key;
                if (spec.name) return row.name === spec.name;
                return false;
            });
            if (match) selected.push(match);
        }
        return selected;
    }

    #summary(prompt = '') {
        const trimmed = (prompt || '').trim();
        if (!trimmed) return 'Ready to help.';
        return trimmed.length > 160 ? `${trimmed.slice(0, 157)}...` : trimmed;
    }

    #escape(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
}

customElements.define('ntx-agents-dashboard', NTXAgentsDashboard);
