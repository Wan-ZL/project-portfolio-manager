---
name: babysit-pr
description: Monitor a PR for review bot comments, identify real bugs vs false positives, fix critical issues, and repeat until clean
---
Use ultrathink for triage decisions.
Detect the current repo: `gh repo view --json nameWithOwner -q .nameWithOwner`.
Detect the default branch: `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`.
Get the PR for the current branch: `gh pr view --json number -q .number`.
If no PR exists, create one to the default branch: `gh pr create --fill`.
Repeat this loop (max 10 rounds):
1. `sleep 480` (wait 8 min for review bots)
2. Fetch comments: `gh pr view <number> --comments` and `gh api repos/<owner/repo>/pulls/<number>/comments`
3. Triage each comment: fix all real issues including bugs, security vulnerabilities, UI/UX problems, accessibility gaps, and i18n incompleteness. Only ignore false positives. Show reasoning for each.
4. If real bugs found: read source files for context, fix minimally, commit and push. Go to step 1.
5. If no real bugs: report "PR is clean" and stop.
Rules: never force push, always new commits, skip previously fixed comments.
