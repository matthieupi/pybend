function normalizePath(filePath) {
	return String(filePath || "").replaceAll("\\", "/");
}

function normalizeTailSegments(segments) {
	if (segments.length === 0) return [];
	const tail = [...segments];
	const last = tail[tail.length - 1] || "";
	if (last.toLowerCase() === "skill.md") {
		tail.pop();
	} else if (last.toLowerCase().endsWith(".md")) {
		tail[tail.length - 1] = last.replace(/\.md$/i, "");
	}
	return tail.filter(Boolean);
}

function splitSlashCommand(text) {
	const input = String(text || "");
	if (!input.startsWith("/")) return null;
	const withoutSlash = input.slice(1);
	const boundary = withoutSlash.search(/\s/);
	if (boundary === -1) return { command: withoutSlash, rest: "" };
	return {
		command: withoutSlash.slice(0, boundary),
		rest: withoutSlash.slice(boundary),
	};
}

export function inferSkillAliasSegments(skillPath) {
	const parts = normalizePath(skillPath).split("/").filter(Boolean);
	if (parts.length === 0) return [];

	const skillsIndex = parts.lastIndexOf("skills");
	if (skillsIndex !== -1) {
		return normalizeTailSegments(parts.slice(skillsIndex + 1));
	}

	const last = parts[parts.length - 1] || "";
	if (last.toLowerCase() === "skill.md" && parts.length >= 2) {
		return [parts[parts.length - 2]].filter(Boolean);
	}

	return last ? [last.replace(/\.md$/i, "")].filter(Boolean) : [];
}

export function buildSkillAliasEntries(commands) {
	const aliasEntries = [];
	const seenAliases = new Set();

	for (const command of commands || []) {
		if (command?.source !== "skill") continue;
		if (typeof command?.name !== "string" || !command.name.startsWith("skill:")) continue;

		const skillPath = command?.sourceInfo?.path;
		const rawSegments = inferSkillAliasSegments(skillPath);
		if (rawSegments.length < 2) continue;

		const segments = [...rawSegments];
		const alias = `skill:${segments.join(":")}`;
		if (seenAliases.has(alias)) continue;
		seenAliases.add(alias);

		aliasEntries.push({
			alias,
			target: command.name,
			path: skillPath,
			rawSegments,
			segments,
		});
	}

	return aliasEntries.sort((a, b) => a.alias.localeCompare(b.alias));
}

export function rewriteSkillAlias(text, commands) {
	const parsed = splitSlashCommand(text);
	if (!parsed) return null;
	if (!parsed.command.startsWith("skill:")) return null;

	const aliasMap = new Map(buildSkillAliasEntries(commands).map((entry) => [entry.alias, entry.target]));
	const target = aliasMap.get(parsed.command);
	if (!target) return null;
	return `/${target}${parsed.rest}`;
}

export function findPreferredSkillAlias(text, commands) {
	const parsed = splitSlashCommand(text);
	if (!parsed) return null;
	if (!parsed.command.startsWith("skill:")) return null;

	const preferredMap = new Map(buildSkillAliasEntries(commands).map((entry) => [entry.target, `/${entry.alias}`]));
	const preferred = preferredMap.get(parsed.command);
	if (!preferred) return null;
	return `${preferred}${parsed.rest}`;
}
