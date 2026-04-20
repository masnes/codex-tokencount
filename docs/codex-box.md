# codex-box shim

`tools/codex-box` is a compatibility wrapper around Podman. It is useful infrastructure, but it is not the core of the usage tracker itself.

## Why This Exists

Running Codex directly on the host is convenient, but sometimes you want a cleaner boundary:

- separate `CODEX_HOME` state per box
- shared access to one project workspace
- a repeatable way to reopen the same container later

This wrapper is the repo's pragmatic answer to that problem.

## When To Use It

Use `codex-box` when you want:

- a separate containerized Codex environment per task or role
- less risk of one box trampling another box's local Codex state
- a stronger boundary around host access than "just run it on the host"

Do not use it when:

- you only need the usage tracker and not the container boundary
- you want a read-only workspace, because this wrapper mounts the repo read-write
- you need a fully isolated VM-style security boundary

## Quick Start

Run it from the repo root as:

```bash
./tools/codex-box [--box NAME] [--workspace-label shared|private|disable] [PROJECT_DIR]
```

Examples:

```bash
./tools/codex-box --box planner
./tools/codex-box --box reviewer .
./tools/codex-box --box fixup ~/src/myrepo
```

If you want it on `PATH`, add `tools/` explicitly. The wrapper is intentionally not kept in the repo root.

## What It Actually Does

- Reuses the same container name for the same project path plus `--box` name.
- Gives each box its own `CODEX_HOME` volume so concurrent boxes do not trample logs, cache, or auth state.
- Shares `/codex-auth/auth.json` across boxes so login is not repeated unnecessarily.
- Sets `CODEX_OUT=/workspace/_codex_out/<box>` for clean per-box handoff files.
- Keeps the workspace bind mount nonrecursive and isolated from nested mounts.
- Seeds new boxes with `model = "gpt-5.4-mini"` and `model_reasoning_effort = "xhigh"` in `~/.codex/config.toml`.
- Prints the resume path for a second shell inside a live container:

```bash
podman exec -it <container_name> bash
```

## Security Posture

This wrapper is trying to be practically safer, not theatrically "secure."

### What it is trying to protect against

- accidental interference between multiple Codex boxes
- needless exposure of host paths outside the chosen project directory
- privilege escalation inside the container
- accidental dependence on host loopback services

### What it does for that goal

- `no-new-privileges`
- `rprivate` bind propagation
- `bind-nonrecursive=true`
- `--http-proxy=false`
- `--no-hosts`
- `--pids-limit=512`
- `--network=slirp4netns:allow_host_loopback=false`
- separate `CODEX_HOME` volume per box
- explicit shared auth volume instead of reusing the host's entire Codex home

### What it does not protect you from

- changes to files in `/workspace`, because the project is mounted writable on purpose
- ordinary network access from inside the container
- every possible container escape; this is still a container, not a VM
- mistakes caused by using `--workspace-label disable` unless you truly need it

## Workspace Label Modes

Default mode is `shared`, which uses SELinux relabeling that is friendly to multiple containers sharing one project directory.

- `shared`: default and usually correct
- `private`: stricter single-container labeling when you want one box at a time
- `disable`: escape hatch for hosts where SELinux labeling blocks startup

You can also set:

```bash
export CODEX_BOX_WORKSPACE_LABEL=shared
```

Use `private` or `disable` only because the host actually needs it, not because they sound more serious.

## Operational Notes

- Re-running the same `--box` value in the same project resumes the same container instead of creating a new one.
- The wrapper refuses to mount your entire home directory.
- The wrapper warns if Podman auto-mount configuration may expose extra host paths.
- `CODEX_ASSUME_EXTERNAL_SANDBOX=1` is set so Codex can treat the Podman box as the outer sandbox boundary.
- Package installs inside the container persist only as long as that container exists.

## Why This Stays Separate From The Tracker

The Python tracker and checkpoint wrappers are about local observability and workflow control.

`codex-box` is host/container integration glue.

Keeping that split explicit makes the repo easier to reason about:

- telemetry logic lives with the tracker
- host sandboxing logic lives in the shim
- security tradeoffs are easier to audit when they are not buried inside the tracker code
