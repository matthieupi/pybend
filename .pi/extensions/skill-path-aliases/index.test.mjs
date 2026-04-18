import test from "node:test";
import assert from "node:assert/strict";

const { default: extensionFactory } = await import("./index.ts");

function makeFakePi(commands = []) {
	const handlers = new Map();
	const registeredCommands = [];
	let runtimeReady = false;

	return {
		api: {
			on(name, handler) {
				handlers.set(name, handler);
			},
			registerCommand(name, options) {
				registeredCommands.push({ name, options });
			},
			getCommands() {
				if (!runtimeReady) throw new Error("Extension runtime not initialized");
				return commands;
			},
			sendUserMessage() {},
		},
		handlers,
		registeredCommands,
		setRuntimeReady(value) {
			runtimeReady = value;
		},
	};
}

test("extension factory does not call runtime actions during load", () => {
	const fake = makeFakePi();
	assert.doesNotThrow(() => extensionFactory(fake.api));
});

test("session_start registers nested skill alias commands after runtime is ready", async () => {
	const fake = makeFakePi([
		{
			name: "skill:git-status",
			source: "skill",
			sourceInfo: { path: "/workspace/.agents/skills/git/git-status/SKILL.md" },
		},
		{
			name: "skill:review",
			source: "skill",
			sourceInfo: { path: "/workspace/.agents/skills/review.md" },
		},
	]);

	extensionFactory(fake.api);
	fake.setRuntimeReady(true);

	const sessionStart = fake.handlers.get("session_start");
	assert.equal(typeof sessionStart, "function");
	await sessionStart({}, {});

	assert.deepEqual(
		fake.registeredCommands.map((entry) => entry.name),
		["skill:git:git-status"],
	);
});
