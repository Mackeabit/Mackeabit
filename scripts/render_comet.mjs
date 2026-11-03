// Render a lavender comet over a persistent activity grid using the solved route.
export function createComet(cells, chain, colors, theme) {
  const positions = chain.map(s => ({ x: (s[0] - 2) * 16, y: (s[1] - 2) * 16 }));
  const first = positions[0], last = positions.at(-1);
  if (first.x !== last.x || first.y !== last.y) throw new Error("Comet route must close without a jump");
  const duration = (positions.length - 1) * 100;
  const lavender = theme === "dark" ? "#c4b5fd" : "#8b5cf6";
  const core = theme === "dark" ? "#f5f0ff" : "#ede9fe";
  const frames = positions.map((p, i) => `${(i / (positions.length - 1) * 100).toFixed(5)}%{transform:translate(${p.x}px,${p.y}px)}`).join("");
  const dots = cells.map(c => `<rect class="c${c.level ? ' active' : ''}" x="${c.x * 16 + 2}" y="${c.y * 16 + 2}" width="12" height="12" rx="2" fill="${colors[c.level]}"/>`).join("");
  // Closely spaced, progressively smaller translucent particles form a tapered tail.
  const tail = Array.from({ length: 18 }, (_, n) => {
    const i = 18 - n, strength = 1 - i / 19;
    return `<circle class="comet tail" cx="8" cy="8" r="${(0.6 + 3.4 * strength).toFixed(2)}" fill="${lavender}" opacity="${(0.06 + 0.7 * strength ** 1.5).toFixed(3)}" style="animation-delay:-${duration - i * 24}ms"/>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="880" height="160" viewBox="-16 -32 880 160">
<defs><radialGradient id="comet-glow"><stop stop-color="${lavender}" stop-opacity="0.65"/><stop offset="1" stop-color="${lavender}" stop-opacity="0"/></radialGradient></defs>
<style>.c{stroke:#1b1f230a;stroke-width:1}.comet{animation:comet-flight ${duration}ms linear infinite;transform:translate(${first.x}px,${first.y}px)}@keyframes comet-flight{${frames}}@media(prefers-reduced-motion:reduce){.comet{display:none}}</style>
${dots}${tail}<g class="comet head"><circle cx="8" cy="8" r="11" fill="url(#comet-glow)"/><circle cx="8" cy="8" r="4.5" fill="${lavender}"/><circle cx="7.4" cy="7.4" r="2.2" fill="${core}"/></g></svg>`;
}
