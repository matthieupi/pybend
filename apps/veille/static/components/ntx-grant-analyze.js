/**
 * <ntx-grant-analyze> — Grant analysis method renderer.
 *
 * Thin subclass of NTTStreamAgent that overrides TOOL_CALL
 * for friendly tool descriptions in the grant analysis context.
 *
 * Wired via Grant.__ui__['methods']['analyze']['renderer'] = 'ntx-grant-analyze'
 */
import { NTTStreamAgent } from './ntx-stream-agent.js';

class NTXGrantAnalyze extends NTTStreamAgent {

    TOOL_CALL(data, meta) {
        const tool = data?.tool || '';

        if (tool.includes('organizations_list') || tool.includes('organizations_read')) {
            data = { ...data, tool: 'Reading organisation profile' };
        } else if (tool.includes('grants_update')) {
            data = { ...data, tool: 'Saving analysis results' };
        } else if (tool.includes('grants_read')) {
            data = { ...data, tool: 'Reading grant details' };
        } else if (tool.includes('sources_list')) {
            data = { ...data, tool: 'Reading configured sources' };
        } else if (tool.includes('scrape_js')) {
            data = { ...data, tool: `Fetching (JS): ${data.args?.url || ''}` };
        } else if (tool.includes('scrape')) {
            data = { ...data, tool: `Fetching: ${data.args?.url || ''}` };
        }

        super.TOOL_CALL(data, meta);
    }
}

customElements.define('ntx-grant-analyze', NTXGrantAnalyze);
export { NTXGrantAnalyze };
