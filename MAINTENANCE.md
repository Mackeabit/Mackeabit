# Profile maintenance

The introduction, interests, headings and tool names are real Markdown in `README.md`. The supplied Mackeabit logo, five monochrome tool icons and teal contribution snake are separate images.

- Edit wording and links directly in `README.md`. The workflow never overwrites this file.
- Java, Python, Git, Codex and Obsidian each have their own SVG icon and official link. Icon originals and licenses are kept in `assets/icons/` and `licenses/`.
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
