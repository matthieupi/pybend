import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { buildSkillAliasEntries, findPreferredSkillAlias, rewriteSkillAlias } from "./skill-aliases.mjs";

function buildMissingAliasMessage(input: string, commands: any[]) {
	const examples = buildSkillAliasEntries(commands)
		.slice(0, 5)
		.map((entry) => `/${entry.alias}`);

	if (examples.length === 0) {
		return `Unknown skill path alias: ${input}. No nested skill path aliases are currently loaded.`;
	}

	return `Unknown skill path alias: ${input}. Try one of: ${examples.join(", ")}`;
}

function buildCanonicalBlockedMessage(input: string, preferred: string) {
	return `Use the path form instead of ${input}: ${preferred}`;
}

function buildCommandForwardMessage(target: string, args: string) {
	const trimmed = args.trim();
	return trimmed ? `/${target} ${trimmed}` : `/${target}`;
}

export default function (pi: ExtensionAPI) {
	const registeredAliases = new Set<string>();

	const ensureAliasCommands = () => {
		const aliasEntries = buildSkillAliasEntries(pi.getCommands());
		for (const entry of aliasEntries) {
			if (registeredAliases.has(entry.alias)) continue;
			registeredAliases.add(entry.alias);
			pi.registerCommand(entry.alias, {
				description: `Path alias for /${entry.target}`,
				handler: async (args, ctx) => {
					const message = buildCommandForwardMessage(entry.target, args);
					if (ctx.isIdle()) {
						pi.sendUserMessage(message);
					} else {
						pi.sendUserMessage(message, { deliverAs: "steer" });
						if (ctx.hasUI) ctx.ui.notify(`Queued ${message}`, "info");
					}
				},
			});
		}
	};

	pi.on("session_start", async () => {
		ensureAliasCommands();
	});

	pi.on("input", async (event, ctx) => {
		if (event.source === "extension") return { action: "continue" };

		const commandText = event.text.split(/\s+/, 1)[0] || "";
		if (!commandText.startsWith("/skill:")) return { action: "continue" };

		const commands = pi.getCommands();
		const preferred = findPreferredSkillAlias(event.text, commands);
		if (preferred && preferred !== commandText) {
			if (ctx.hasUI) ctx.ui.notify(buildCanonicalBlockedMessage(commandText, preferred.split(/\s+/, 1)[0]), "warning");
			return { action: "handled" };
		}

		const rewritten = rewriteSkillAlias(event.text, commands);
		if (rewritten) {
			return { action: "transform", text: rewritten, images: event.images };
		}

		const isNestedPathAlias = commandText.slice(1).split(":").length > 2;
		if (!isNestedPathAlias) return { action: "continue" };

		if (ctx.hasUI) {
			ctx.ui.notify(buildMissingAliasMessage(commandText, commands), "warning");
		}

		return { action: "handled" };
	});
}
