# Profile maintenance — Activity

The README displays a blue activity grid and a lavender snake under **Activity**. The snake is lavender (`#c4b5fd`) in dark mode and deeper violet (`#8b5cf6`) in light mode, with a subtle head glow and a progressively translucent tail. It consumes activity cells and loops. No summary statistics, dates, month names, legend, per-tool colors or extra visible title are drawn into the image. Each cell is the day's actual Codex tokens plus Claude Code tokens from every machine that publishes them.

## Current pipeline (2026-11-28)

1. A private always-on host runs `scripts/codex_activity.py --publish` at 00:37 UTC (09:37 Asia/Seoul), using its existing Codex login and GitHub connector. It publishes only `generated/codex-activity.json`; it cannot overwrite the animated SVGs.
2. Every machine that runs Claude Code (desktop, laptop, servers) runs `scripts/claude_activity.py --publish` once a day. See **Claude Code hosts** below.
3. A push changing that data, the renderer/tests, or the workflow triggers **Update activity snake** in GitHub Actions. The job always checks out the newest `main`, so a run started by one host also includes data that other hosts published meanwhile. Manual workflow dispatch is also available.
4. `scripts/ai_activity.py` sums Codex and all Claude host files per UTC day into `.tmp/ai-activity.json`; the renderer and the verifier both read that one file. `scripts/render_snake.mjs --ai` maps the daily buckets into a 53-week Sunday-first calendar. Blue levels are quartiles of nonzero counts. It reuses the original pinned Platane/snk route solver and SVG renderer at `d8f6715049803e982ee5ff501b6b9b7d5deeb09b`, including the original four-part snake and cell consumption animation. Every active cell must be visited by the head before output is accepted.
5. `scripts/render_profile.py --ai-snake-only` prepares the snake and grid at the existing 160px height, adds a Gaussian head glow and fading tail, and retains the reduced-motion fallback. Reduced-motion mode stops animations and preserves the initial calendar. Light/dark files keep their existing paths.
6. `scripts/verify_ai_snake.py` verifies every cell position and initial color against the daily source, day/active-cell totals, four snake segments, lavender color, head glow, fading tail and looping CSS, reduced-motion handling, no visible text, no consumption bar, and no scripts/foreign objects. Only the two SVGs are committed when changed. Push conflicts fail instead of forcing or overwriting another commit.

The app-server integration never starts model turns or copies credentials. It opens a nonpersistent MCP context and uses the already-connected GitHub account. No account identifiers, email, conversations or credentials enter the allowlisted aggregate JSON. GitHub Actions needs no Codex credentials; it uses its built-in token to publish images. No npm installation is required; the renderer uses Node 22.13+ built-in type erasure, available on the Actions runner.

Missing/invalid/empty data, a date or lifetime-total regression, or data over seven days old stops collection. Render failure leaves the last good animation in place. The service can lag behind today. Dates are preserved as returned, missing buckets inside the calendar are zero, and future cells are omitted. Summary metrics remain in the aggregate source for validation but are not displayed.

The private host runs a reviewed installed copy, not an automatically downloaded script. Deploy collector edits deliberately. Its lock, five-minute timeout and existing daily schedule are retained. Sources and rendered files update in two commits; the image refresh follows the successful Actions run.

Validation:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/ai_activity.py
node scripts/render_snake.mjs --ai
python3 -B scripts/render_profile.py --ai-snake-only
python3 -B scripts/verify_ai_snake.py
```

The renderer expects the pinned upstream checkout at `.tmp/snk`. The retired GitHub contribution mode remains available without `--ai`; it is no longer scheduled. The image is derived from authentic usage, with a custom quartile color scale rather than an undocumented exact Codex color threshold.

Reference: https://learn.chatgpt.com/docs/app-server#7-token-usage-chatgpt

## Claude Code hosts

Claude Pro/Max has no account-wide token API (`/usage` and the Claude Code Analytics API do not cover it), so usage is read from each machine's own Claude Code transcripts.

- **One hub, no credentials on other machines:** a single hub machine runs `scripts/claude_activity.py --publish --remote <alias> ...` once a day. For each `--remote` SSH alias (key authentication, `BatchMode`), the script sends itself over SSH stdin and runs there with `--emit`; the remote needs only Python 3.10+ (`alias=C:/path/python.exe` for a Windows remote). The remote returns hashed response ids with dates and totals; it needs no GitHub login and nothing is installed there except its `~/.mackeabit-profile/claude-host-id`.
- **Counted once across machines:** a response recorded on more than one machine (for example an SSH session also logged by the client) is counted for the first machine in run order: the hub, then `--remote` in the order given. Put always-on servers before laptops. An unreachable machine is reported and skipped; the others still publish.

- **What is counted:** `~/.claude/projects/**/*.jsonl` (or `CLAUDE_CONFIG_DIR`), assistant responses only. Input, output, cache-write and cache-read tokens are summed, which matches how the Codex total counts cached input. A response repeated by streaming or a resumed session (same message id and request id) is counted once. Days are UTC. The current, incomplete day is never published.
- **What is published:** `generated/claude-activity/<host-id>.json` with only dates and daily totals. The host id is 8 random hex characters stored in `~/.mackeabit-profile/claude-host-id`; no hostname, user, path, project, model or text is published. Each host writes only its own file, so hosts never conflict with each other.
- **History is kept:** Claude Code deletes transcripts after `cleanupPeriodDays` (30 by default). The collector merges with the copy already on `main` and keeps the larger total for each day, so cleanup never removes published days. Published days older than 7 days are final, so a response whose copy disappears from one machine later cannot be counted again elsewhere. Every machine must be reachable by the hub at least once every 30 days.
- **Token (hub only):** `GH_TOKEN`/`GITHUB_TOKEN`, otherwise `gh auth token`, otherwise git's own GitHub login (`git credential fill`, non-interactive, e.g. Git Credential Manager). The token is never stored by the script.
- **Failure:** No usage at all, invalid published or remote data, or a second write conflict stops that machine without writing. The exit status is nonzero when any machine failed. Never force-push.

Dry run (prints per-machine totals, publishes nothing), then publish:

```sh
python3 -B scripts/claude_activity.py --remote server-a --remote laptop=C:/Python313/python.exe
python3 -B scripts/claude_activity.py --publish --remote server-a --remote laptop=C:/Python313/python.exe
```

The hub runs an installed copy of the reviewed script daily after 00:37 UTC (Windows Task Scheduler with `pythonw -I -B`, "run as soon as possible after a missed start"). Adding a machine = add an SSH alias on the hub and one more `--remote` to that task.

## Historical GitHub snake pipeline (retired 2026-11-03)

The following records describe the former pipeline, not the current schedule or README activity source.

# Profile maintenance

The introduction, interests, headings and tool names are real Markdown in `README.md`. The supplied Mackeabit logo, six monochrome tool icons and teal contribution snake are separate images.

- Edit wording and links directly in `README.md`. The workflow never overwrites this file.
- Java, Python, Git, Codex, Claude Code and Obsidian each have their own SVG icon and official link. Icon originals and licenses are kept in `assets/icons/` and `licenses/`.
- `scripts/render_profile.py` prepares the monochrome icon tiles, teal accent line and standalone light/dark contribution animations using Python's standard library.
- `scripts/collect_activity.py` reads public, owned, non-fork repositories directly through the GitHub REST API. It counts commits attributed to Mackeabit on each default branch, plus issues and pull requests created by Mackeabit. Dates use UTC; duplicate commit SHAs and issue IDs are counted once. Automation authored by other accounts is excluded.
- Private repositories, contributions to other owners' repositories, reviews, discussions and repository creation are outside this scope. These activity totals are real, but are not GitHub's official contribution-calendar totals. Making the profile private does not make its public repositories private.
- The collector uses only the built-in GitHub Actions token; no personal access token or browser session is stored. It never calls the profile contribution API.
- `scripts/render_snake.mjs` feeds the collected grid into the same Platane/snk solver and SVG renderer at commit `d8f6715049803e982ee5ff501b6b9b7d5deeb09b`. Actions checks out that source into ignored `.tmp/snk`. Node's built-in type eraser prepares the required modules in `.tmp/snk-runtime`; no npm installation or third-party source redistribution is needed. Node 22.13+ is required. The palette, dimensions and animation timing remain unchanged.
- Updates run daily at 00:17 UTC (09:17 Korea time), on graphics/workflow source changes, or via Actions → Update profile and contribution snake → Run workflow. GitHub may delay scheduled jobs.
- The README uses normal GitHub text colors. The snake switches between light and dark palettes and respects reduced-motion preferences when loaded.
- `generated/activity.json` records the account, range, collection scope, totals and source digest. `generated/activity-calendar.json` contains daily aggregated counts, with no repository names, commit messages, issue titles or personal credentials.
- For a local graphics-only refresh using the existing real contribution SVGs, run `python -B scripts/render_profile.py --assets-only`.

Profile README content does not control GitHub's separate Popular repositories / Pinned or contribution sections. A private profile hides these sections from visitors; the owner may still see them when signed in. Profile privacy also hides social activity and follower/organization information. The direct public-repository collector works independently of that profile setting.

API or pagination failures stop the update before publication. Empty results cannot replace an existing nonempty calendar. Generation validates the daily totals, grid size, active cells and snake coverage. The Actions workflow commits generated files only after all steps succeed.

For a local refresh, check out the pinned Platane/snk source into `.tmp/snk`, then run `python -B scripts/collect_activity.py --use-gh`, `node scripts/render_snake.mjs`, and `python -B scripts/render_profile.py`. The optional `--use-gh` uses the existing authenticated CLI without copying its token. Run the focused collection checks with `python -B -m unittest discover -s tests -v`.

The original SVG layout's custom fonts, exact spacing, background and rounded cards cannot be reproduced exactly with native GitHub Markdown: GitHub strips custom CSS. Real text can retain the same content and approximate alignment while the supplied logo, tool tiles and snake remain separate graphics. Do not replace the current README with a composite image merely to change activity collection.

GitHub can disable scheduled workflows in public repositories after 60 days without repository activity. If updates stop, check and re-enable the workflow in Actions.

The original full-profile SVGs are retained only as historical files; the README does not use them and the workflow no longer generates them. Exact upstream icon sources are recorded in `assets/sources.json`. Brand names and logos remain the property of their respective owners. The provided Mackeabit logo is unchanged.
