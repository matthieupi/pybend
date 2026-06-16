#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const skillsDir = path.join(root, '.opencode', 'skills');

const requiredPackages = [
  'n3tx-core',
  'n3tx-actors',
  'n3tx-ui',
  'n3tx-agents',
  'n3tx-files',
];

const highRiskUseOnly = new Set([
  'n3tx-files',
  'n3tx-framework-maintenance',
  'n3tx-framework-boundaries',
  'n3tx-extension-patterns',
  'n3tx-json-fields',
]);

const implementationSkills = new Set([
  'n3tx-app-bootstrap',
  'n3tx-backend',
  'n3tx-build-app',
  'n3tx-files',
  'n3tx-frontend',
  'n3tx-framework-maintenance',
]);

function fail(message) {
  failures.push(message);
}

function parseFrontmatter(content, file) {
  if (!content.startsWith('---\n')) {
    fail(`${file}: missing YAML frontmatter`);
    return {};
  }
  const end = content.indexOf('\n---', 4);
  if (end === -1) {
    fail(`${file}: unterminated YAML frontmatter`);
    return {};
  }

  const frontmatter = content.slice(4, end).split('\n');
  const parsed = {};
  for (const line of frontmatter) {
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!match) continue;
    parsed[match[1]] = match[2].replace(/^['"]|['"]$/g, '');
  }
  return parsed;
}

function listSkillDirs() {
  return fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
}

const failures = [];
const warnings = [];

if (!fs.existsSync(skillsDir)) {
  throw new Error(`Missing skills directory: ${skillsDir}`);
}

const skillDirs = listSkillDirs();
const skillBodies = new Map();

for (const skillName of skillDirs) {
  const file = path.join(skillsDir, skillName, 'SKILL.md');
  if (!fs.existsSync(file)) {
    fail(`${skillName}: missing SKILL.md`);
    continue;
  }

  const rel = path.relative(root, file);
  const content = fs.readFileSync(file, 'utf8');
  const frontmatter = parseFrontmatter(content, rel);
  skillBodies.set(skillName, content);

  if (frontmatter.name !== skillName) {
    fail(`${rel}: frontmatter name '${frontmatter.name}' does not match folder '${skillName}'`);
  }
  if (!frontmatter.description || frontmatter.description.length < 40) {
    fail(`${rel}: description is missing or too short for reliable skill selection`);
  }
  if (frontmatter.description && !/Use\s+(ONLY\s+)?(FIRST\s+)?when/i.test(frontmatter.description)) {
    warnings.push(`${rel}: description should include an explicit 'Use when', 'Use FIRST when', or 'Use ONLY when' trigger`);
  }
  if (highRiskUseOnly.has(skillName) && !/Use ONLY when/i.test(frontmatter.description || '')) {
    fail(`${rel}: high-risk/narrow skill should use 'Use ONLY when...' in description`);
  }
  if (implementationSkills.has(skillName) && !/AGENTS\.md/.test(content)) {
    warnings.push(`${rel}: implementation skill should anchor docs-first behavior to AGENTS.md`);
  }
}

const maintenance = skillBodies.get('n3tx-framework-maintenance') || '';
for (const pkg of requiredPackages) {
  if (!maintenance.includes(pkg)) {
    fail(`n3tx-framework-maintenance: package boundary table should mention ${pkg}`);
  }
}

const router = skillBodies.get('n3tx-skill-routing') || '';
for (const skill of ['n3tx-files', 'n3tx-testing', 'n3tx-backend', 'n3tx-frontend']) {
  if (!router.includes(skill)) {
    fail(`n3tx-skill-routing: routing matrix should mention ${skill}`);
  }
}

const buildApp = skillBodies.get('n3tx-build-app') || '';
if (/Default recommendation.*ActorModel.*Level 3/is.test(buildApp)) {
  fail('n3tx-build-app: stale Level 3 default detected; prefer lowest sufficient routing level');
}

const backend = skillBodies.get('n3tx-backend') || '';
if (backend.includes('without framework source lookup')) {
  fail('n3tx-backend: stale description still says without framework source lookup');
}

if (failures.length || warnings.length) {
  for (const warning of warnings) console.warn(`warn: ${warning}`);
  for (const failure of failures) console.error(`error: ${failure}`);
}

if (failures.length) {
  console.error(`\nSkill lint failed: ${failures.length} error(s), ${warnings.length} warning(s)`);
  process.exit(1);
}

console.log(`Skill lint passed: ${skillDirs.length} skills checked, ${warnings.length} warning(s)`);
