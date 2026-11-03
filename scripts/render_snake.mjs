// Adapt a local activity grid to the same pinned Platane/snk renderer.
// No npm packages or personal access token are required.
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { stripTypeScriptTypes } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const upstream = path.join(root, ".tmp/snk/packages");
const runtime = path.join(root, ".tmp/snk-runtime");
const compiled = new Set();

// Upstream is checked out at the same immutable commit as the previous action.
// Erase types and resolve workspace aliases in an ignored, temporary directory.
async function compileModule(relative) {
  const normalized = path.posix.normalize(relative);
  if (normalized.startsWith("../") || path.isAbsolute(normalized)) {
    throw new Error("Module must stay inside the pinned upstream source tree");
  }
  if (compiled.has(normalized)) return;
  compiled.add(normalized);
  let input = await readFile(path.join(upstream, normalized + ".ts"), "utf8");
  // Upstream has some type imports without modifiers. These are the exported
  // type names in this pinned source tree; annotate them for Node's type eraser.
  const types = new Set(["Outside", "Options", "DrawOptions", "Color", "Empty", "Grid", "Point", "Snake"]);
  input = input.replace(/import\s*\{([^}]+)\}/g, (_, names) => "import {" + names.split(",").map(name => {
    const item = name.trim();
    return types.has(item.split(/\s+/)[0]) ? "type " + item : item;
  }).filter(Boolean).join(", ") + "}");
  const dependencies = [];
  let js = stripTypeScriptTypes(input, { mode: "strip" });
  js = js.replace(/\bfrom\s+["']([^"']+)["']/g, (_, specifier) => {
    let dependency;
    if (specifier.startsWith("@snk/")) dependency = specifier.slice(5);
    else if (specifier.startsWith(".")) dependency = path.posix.join(path.posix.dirname(normalized), specifier);
    else throw new Error("Unexpected upstream runtime dependency: " + specifier);
    dependencies.push(dependency);
    let local = path.posix.relative(path.posix.dirname(normalized), dependency);
    if (!local.startsWith(".")) local = "./" + local;
    return 'from "' + local + '.mjs"';
  });
  for (const dependency of dependencies) await compileModule(dependency);
  const output = path.join(runtime, normalized + ".mjs");
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, js);
}

const entries = ["solver/getBestRoute", "solver/getPathToPose", "svg-creator/index", "types/__fixtures__/snake", "generate-snake-animation/cellsToGrid"];
for (const entry of entries) await compileModule(entry);
const load = (entry) => import(pathToFileURL(path.join(runtime, entry + ".mjs")).href);
const [{ getBestRoute }, { getPathToPose }, { createSvg }, { snake4 }, { cellsToGrid }] = await Promise.all(entries.map(load));
const ai = process.argv.includes("--ai");
let calendar;
if (ai) {
  const data = JSON.parse(await readFile(path.join(root, "generated/codex-activity.json"), "utf8"));
  const end = new Date(data.dataThrough + "T00:00:00Z");
  if (!Number.isFinite(end.getTime()) || !Array.isArray(data.days)) throw new Error("Invalid AI activity data");
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - end.getUTCDay() - 52 * 7);
  const counts = new Map(data.days.map(d => [d.date, d.tokens]));
  if (counts.size !== data.days.length || data.days.some(d => !Number.isSafeInteger(d.tokens) || d.tokens < 0)) throw new Error("Invalid daily token counts");
  const active = data.days.filter(d => d.date >= start.toISOString().slice(0,10) && d.date <= data.dataThrough && d.tokens > 0).map(d => d.tokens).sort((a,b) => a-b);
  if (!active.length) throw new Error("No activity to animate");
  const cuts = [.25,.5,.75].map(q => active[Math.floor((active.length-1)*q)]);
  const days = [];
  for (let i=0; i<371; i++) {
    const d = new Date(start); d.setUTCDate(d.getUTCDate()+i);
    if (d > end) break;
    const date = d.toISOString().slice(0,10), count = counts.get(date) ?? 0;
    days.push({date, count, level: count === 0 ? 0 : 1 + cuts.filter(c => count > c).length, x:Math.floor(i/7), y:i%7});
  }
  calendar = {account:"Mackeabit", days, total_contributions:days.reduce((n,d)=>n+d.count,0)};
} else {
  calendar = JSON.parse(await readFile(path.join(root, ".tmp/repository-activity.json"), "utf8"));
}
if (calendar.account.toLowerCase() !== "mackeabit" || calendar.days.length < 365 || calendar.days.length > 371) {
  throw new Error("Invalid repository activity calendar");
}
const cells = calendar.days;
if (cells.some(c => !Number.isInteger(c.count) || c.count < 0 || !Number.isInteger(c.level) || c.level < 0 || c.level > 4)) {
  throw new Error("Invalid activity cell");
}
const grid = cellsToGrid(cells);
const chain = getBestRoute(grid, snake4);
if (!chain?.length) throw new Error("No snake route generated");
const returnRoute = getPathToPose(chain.at(-1), snake4);
if (!returnRoute) throw new Error("Snake cannot return to its starting pose");
chain.push(...returnRoute);
// All nonempty cells must actually be visited by the snake's head.
const visited = new Set(chain.map(snake => (snake[0] - 2) + "," + (snake[1] - 2)));
if (cells.some(c => c.count > 0 && !visited.has(c.x + "," + c.y))) {
  throw new Error("Snake route missed an activity cell");
}
const palettes = ai ? {
  light: ["#ebedf0", "#cce7ff", "#8dcbff", "#399cf4", "#0969da"],
  dark: ["#262c36", "#053963", "#075b9c", "#1683d8", "#69b7ff"],
} : {
  light: ["#e9efec", "#d3e6df", "#9acdbd", "#53ac96", "#13856c"],
  dark: ["#212c26", "#25453b", "#27735f", "#27a78b", "#53d9b9"],
};
await mkdir(path.join(root, "generated"), { recursive: true });
for (const [theme, colors] of Object.entries(palettes)) {
  const svg = createSvg(grid, cells, chain, {
    sizeDotBorderRadius: 2, sizeCell: 16, sizeDot: 12,
    colorDotBorder: "#1b1f230a", colorDots: colors,
    colorEmpty: colors[0], colorSnake: ai ? (theme === "dark" ? "#c4b5fd" : "#8b5cf6") : "#25c6b0",
  }, { stepDurationMs: 100 });
  await writeFile(path.join(root, ai ? ".tmp" : "generated", `${ai ? "ai-" : ""}snake-${theme}.svg`), svg + "\n");
}
console.log(`Rendered ${cells.length} days, ${calendar.total_contributions} activities, ${chain.length} route steps with the snake renderer.`);
