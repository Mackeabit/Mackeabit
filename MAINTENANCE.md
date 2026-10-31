# Profile maintenance

The introduction, interests, headings and tool names are real Markdown in `README.md`. The supplied Mackeabit logo, five monochrome tool icons and teal contribution snake are separate images.

- Edit wording and links directly in `README.md`. The workflow never overwrites this file.
- Java, Python, Git, Codex and Obsidian each have their own SVG icon and official link. Icon originals and licenses are kept in `assets/icons/` and `licenses/`.
- `scripts/render_profile.py` prepares the monochrome icon tiles, teal accent line and standalone light/dark contribution animations using Python's standard library.
- Platane/snk reads the repository owner's real contribution calendar using the built-in GitHub token. No personal access token is configured.
- Updates run daily at 00:17 UTC (09:17 Korea time), on graphics/workflow source changes, or via Actions → Update profile and contribution snake → Run workflow. GitHub may delay scheduled jobs.
- The README uses normal GitHub text colors. The snake switches between light and dark palettes and respects reduced-motion preferences when loaded.
- `generated/activity.json` records the account, calendar range and contribution totals without repository names or project descriptions.
- For a local graphics-only refresh using the existing real contribution SVGs, run `python -B scripts/render_profile.py --assets-only`.

Profile README content does not control GitHub's separate Popular repositories / Pinned or contribution sections. Making a profile private affects more than these sections and may change API visibility. The refresh refuses to replace an existing nonempty calendar with an empty one; check the workflow if visibility changes.

GitHub can disable scheduled workflows in public repositories after 60 days without repository activity. If updates stop, check and re-enable the workflow in Actions.

The original full-profile SVGs are retained only as historical files; the README does not use them and the workflow no longer generates them. Exact upstream icon sources are recorded in `assets/sources.json`. Brand names and logos remain the property of their respective owners. The provided Mackeabit logo is unchanged.
