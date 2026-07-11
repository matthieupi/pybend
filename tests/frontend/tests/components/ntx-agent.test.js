import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Permissions.js', () => ({
  permissions: { canAction: vi.fn(() => false) },
}));

import { NtxAgent } from '../../../../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js';

describe('ntx-agent hydrated tools', () => {
  let agent;

  beforeEach(() => {
    agent = new NtxAgent();
    agent.schema = { __name__: 'AgentActor', access: {} };
  });

  it('renders hydrated AgentTool targets and escaped descriptions', () => {
    agent.value = {
      id: 1,
      name: 'Researcher',
      tools: [
        { id: 2, target: 'grants', description: 'Grant <search>' },
        { id: 3, target: 'sources', description: 'Source lookup' },
      ],
    };

    const html = agent.renderTools();

    expect(html).toContain('grants');
    expect(html).toContain('sources');
    expect(html).toContain('Grant &lt;search&gt;');
    expect(html).not.toContain('[object Object]');
  });

  it('preserves actor-address and legacy URL labels', () => {
    expect(agent._toolName('grants')).toBe('grants');
    expect(agent._toolName('http://localhost:5000/AgentTool/4')).toBe('⚙ #4');
  });
});
