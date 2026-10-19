import test from "node:test";
import assert from "node:assert/strict";

import {
	buildSkillAliasEntries,
	findPreferredSkillAlias,
	inferSkillAliasSegments,
	rewriteSkillAlias,
} from "./skill-aliases.mjs";

const commands = [
	{
		name: "skill:git-status",
		source: "skill",
		sourceInfo: {
			path: "/workspace/.agents/skills/git/git-status/SKILL.md",
		},
	},
	{
		name: "skill:deep-audit",
		source: "skill",
		sourceInfo: {
			path: "/workspace/.agents/skills/architecture/deep-audit/SKILL.md",
		},
	},
	{
		name: "skill:review",
		source: "skill",
		sourceInfo: {
			path: "/workspace/.pi/skills/review.md",
		},
	},
];

test("inferSkillAliasSegments derives nested folder aliases from SKILL.md paths", () => {
	assert.deepEqual(
		inferSkillAliasSegments("/workspace/.agents/skills/git/git-status/SKILL.md"),
		["git", "git-status"],
	);
	assert.deepEqual(
		inferSkillAliasSegments("C:\\Users\\pi\\.pi\\agent\\skills\\planning\\write-a-prd\\SKILL.md"),
		["planning", "write-a-prd"],
	);
});

test("inferSkillAliasSegments supports top-level markdown skills", () => {
	assert.deepEqual(inferSkillAliasSegments("/workspace/.pi/skills/review.md"), ["review"]);
});

test("buildSkillAliasEntries maps nested loaded skills to /skill:<path> aliases", () => {
	assert.deepEqual(
		buildSkillAliasEntries(commands).map(({ alias, target }) => ({ alias, target })),
		[
			{ alias: "skill:architecture:deep-audit", target: "skill:deep-audit" },
			{ alias: "skill:git:git-status", target: "skill:git-status" },
		],
	);
});

test("rewriteSkillAlias preserves arguments and rewrites path aliases to canonical skill commands", () => {
	assert.equal(rewriteSkillAlias("/skill:git:git-status", commands), "/skill:git-status");
	assert.equal(
		rewriteSkillAlias("/skill:architecture:deep-audit investigate actor routing", commands),
		"/skill:deep-audit investigate actor routing",
	);
});

test("findPreferredSkillAlias points canonical nested skill commands to the preferred path form", () => {
	assert.equal(findPreferredSkillAlias("/skill:git-status", commands), "/skill:git:git-status");
	assert.equal(
		findPreferredSkillAlias("/skill:deep-audit investigate actor routing", commands),
		"/skill:architecture:deep-audit investigate actor routing",
	);
	assert.equal(findPreferredSkillAlias("/skill:review", commands), null);
});

test("non-alias and unknown-alias cases return null", () => {
	assert.equal(rewriteSkillAlias("/skills:git:status", commands), null);
	assert.equal(rewriteSkillAlias("/skill:git:missing", commands), null);
	assert.equal(rewriteSkillAlias("/skill:git-status", commands), null);
});
