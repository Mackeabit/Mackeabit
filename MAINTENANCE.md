# Profile maintenance

The profile uses the approved monochrome and teal design, Mackeabit's original logo, and Java, Python, Git, Codex and Obsidian icons.

- GitHub displays the root README because this public repository matches the account name.
- The workflow reads the repository owner's actual GitHub contribution calendar using the built-in GitHub token. It does not require a personal access token.
- Platane/snk generates the snake from that calendar. The Python renderer combines it with the profile design as self-contained SVGs; no JavaScript, foreignObject or external image services are needed by the README.
- Updates run daily at 00:17 UTC (09:17 Korea time), on relevant source changes, or via Actions → Update profile and contribution snake → Run workflow. Scheduled jobs can start later when GitHub is busy.
- To edit wording or layout, change `scripts/render_profile.py`. Generated SVGs and README are replaced by the workflow.
- Desktop and mobile images have light/dark variants. Reduced-motion preferences pause SVG animations.
- `generated/activity.json` records the account, calendar date range and total used to verify each refresh. It contains no repository names or project descriptions.

GitHub can disable scheduled workflows in public repositories after 60 days without repository activity. If updates stop, check and re-enable the workflow in Actions. The script also supports a local rendering check with Python 3.11+ after the workflow has generated the snake files and calendar metadata.

Icons retain their upstream license notices in `licenses/`; exact asset sources are recorded in `assets/sources.json`. Brand names and logos remain the property of their respective owners. The provided Mackeabit logo is reused without alteration.
