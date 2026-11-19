# Scout builds for the renewables tracker

This page says how open-source tools and open data reach this repository.
The scouts are shared with Hawthorn's data center platform. The building is
separate. Price set this on 2026-11-19.

- **Finding (shared).** Three scouts in the private `pricephillips/data-centers`
  repository look for tools and data for both products. Repo Scout
  (`docs/repo_scout_routine.md` there) searches open-source code and open data
  three times a week, and gives three runs in every twelve to this tracker and
  one to security tools for both repositories. It starts each run from GitHub's
  trending and topic pages for its category. Gov Data Scout searches
  government data, including wind, solar and storage data. Once a month,
  Competitor Scout reads rival and complementary products (SitePath
  Intelligence among them). Every verdict goes into one registry there
  (`configs/integrations.json`), so no run judges the same thing twice.
- **Deciding (shared).** Each Friday one "Tool picks" issue in data-centers
  lists every shortlisted item. An item for this repository says
  "renewables" in its type. Price ticks Yes or No. Nothing is built without
  a Yes.
- **Building (this repository).** Each Tuesday the "Renewables scout: build
  approved picks" routine follows this page. The `renewables-integrator`
  agent (`.claude/agents/renewables-integrator.md`) builds each approved
  item marked `build_in: "renewable-opposition"`, through this repository's
  own paths, and records it in `config/adopted_tools.json`. The data center
  build run never builds these items, and this run never builds theirs.

Nothing here names a client: this repository is public, and the registry
and the picks issue that might hold client context stay in the private
repository.

## 1. Setup

1. Work in this repository's checkout under its `CLAUDE.md`. Attach
   `pricephillips/data-centers` with the `add_repo` tool (access `read`) and
   clone it shallow, as the tool says. GitHub GraphQL is blocked: use
   `gh api` (REST).
2. Check GitHub access and what is open:

   ```bash
   W=$(mktemp -d)
   git fetch origin main
   gh api 'repos/pricephillips/renewable-opposition/pulls?state=open&per_page=100' \
     --jq '.[] | select(.title | startswith("Renewables scout: builds")) | "\(.number) \(.html_url)"'
   gh api 'repos/pricephillips/data-centers/issues?state=all&labels=tool-picks&per_page=1' \
     --jq '.[] | "\(.number) \(.state) \(.title)"'
   ```

   If a call fails, stop and reply "Renewables scout build did not run:
   <the error>". A run without access must never read like a run that found
   nothing to do.

## 2. Pace

Stop with one line, and open nothing, when:

- a `Renewables scout: builds` pull request is still open (one waits for
  Price at a time); or
- no item is approved. Save the newest picks issue's body to `$W/picks.md`
  and run `python scripts/tool_picks.py --parse $W/picks.md` in the
  data-centers checkout. The items to build are the ids in its `yes` list
  whose registry entries (on data-centers main, or on an open `Repo scout:
  shortlist`, `Gov data scout: shortlist` or `Competitor scout:` branch
  there) carry `build_in: "renewable-opposition"`, are `deferred` with a
  trigger starting `Shortlisted for adoption`, and are not in this
  repository's `config/adopted_tools.json`. Take them in the issue's order,
  at most 3. The rest wait for next Tuesday.

## 3. Build

1. `git checkout -B <session branch> origin/main`.
2. For each item: save its registry entry to
   `.packets/scout-builds/<id>.json` (`.packets/` is never committed), then
   dispatch `renewables-integrator` with that path, the picks issue number
   and today's date. Take its report back and do not redo its work. One
   item that fails does not stop the others.
3. Review: `git status --short` and `git diff --stat` show only the files the
   report names, and nothing under `data/`, `docs/`, `.github/` or
   `.claude/`. If the report says a workflow file must change, make that
   change yourself and say why in the pull request. Commit each item on its
   own, so Price can revert one and keep the rest. Each commit message gets
   the humanizer pass (`CLAUDE.md`, "Written text").
4. Push once, when every item is committed.
5. Prove it live. Start each proof workflow the reports name, once, on the
   branch (`gh workflow run <file> --ref <branch>`), and wait for it in the
   same turn (`gh run watch <id> --exit-status`). A run of `intake.yml` or
   `build-data.yml` on the branch commits its outputs to the branch. That is
   expected, and main rebuilds them after the merge. If the new item makes a
   run fail, revert that item's commit, say so, and keep the others.

## 4. Pull request

Open one pull request, titled `Renewables scout: builds for the week of
<YYYY-MM-DD>`, with the attribution lines the session context gives. Its
body (after the humanizer pass, then the copy-editor agent as usual) starts
with a short table (item, registry id, what it adds, proof run), and then,
for each item, says in plain words:

- that Price approved it, by picks issue number in the data-centers
  repository;
- what was built, by which path, its license and any notice the license
  requires;
- the URL of the green proof run, or why there is none;
- what Price checks before merging: the license page and the source.

The registry ids must appear in the body: the next Repo Scout run in
data-centers reads them from the merged pull request and records that the
item was built here. Wait for `validate.yml` and make it green, give Price
the link, and stop. Price merges. No reminders or wakeups.

## 5. Reply

One short reply: what was built, the proof run URLs, what Price checks
before merging, and the pull request link, or the one line saying why the
run stopped.
