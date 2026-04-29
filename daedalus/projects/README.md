# Daedalus projects

Each subdirectory under `projects/` is one **project pack** — optional
playground material for a specific repository or operator setup.

Project packs are not the public workflow contract. The engine is
configured from `<workflow-root>/WORKFLOW.md`; `projects/` is
where you keep project-specific docs, helper skills, and local metadata
that you do not want in the generic plugin surface.

The published repo keeps `yoyopod_core/` here as an example pack and
local playground, not as an engine default.

## Layout

```
projects/
├── README.md                # this file
└── <project-slug>/          # one directory per project pack
    ├── config/              # project metadata
    │   └── project.json     # {projectSlug, displayName, workspaceRepoName}
    ├── docs/                # project-scoped runbooks and specs
    ├── runtime/             # mutable runtime state (gitignored)
    │   ├── memory/          # event log, alert state, status projections
    │   ├── state/           # sqlite + durable runtime state
    │   └── logs/            # local runtime/service logs
    ├── skills/              # project-only skills kept out of the public root
    └── workspace/           # cloned source repo (gitignored)
        └── <repo-name>/     # the actual git checkout the agents work in
```

`runtime/` and `workspace/` are excluded from git — only the README
stubs inside them are tracked, so the directory shape is preserved on a
fresh clone.

## Adding a new project pack

1. Create `projects/<your-slug>/config/project.json` with the three
   keys: `projectSlug`, `displayName`, `workspaceRepoName`.
2. Add `projects/<your-slug>/runtime/README.md` and
   `projects/<your-slug>/workspace/README.md` placeholders.
3. Add `projects/<your-slug>/docs/` and `projects/<your-slug>/skills/`
   if you need project-only runbooks or automations.
4. Point your real workflow root's `WORKFLOW.md` at the repo
   and policy for that project. Daedalus selects work by
   `--workflow-root`, not by project-pack slug.
