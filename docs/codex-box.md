# codex-box shim

`tools/codex-box` is a compatibility wrapper around Podman, not part of the usage-tracker core. It exists to give a strong default sandbox for one or more boxes that share the same workspace directory.

## Location

Run it from the repo root as:

```bash
./tools/codex-box [--box NAME] [--workspace-label shared|private|disable] [PROJECT_DIR]
```

If you want it on `PATH`, add `tools/` explicitly. The wrapper is intentionally not kept in the repo root.

## Behavior

- Reuses the same container name for the same project path plus `--box` name.
- Gives each box its own `CODEX_HOME` volume so concurrent boxes do not trample logs, cache, or auth state.
- Shares `/codex-auth/auth.json` across boxes so login is not repeated unnecessarily.
- Sets `CODEX_OUT=/workspace/_codex_out/<box>` for clean per-box handoff files.
- Keeps the workspace bind mount nonrecursive and isolated from nested mounts.
- Prints the resume path for a second shell inside a live container:

```bash
podman exec -it <container_name> bash
```

## Security posture

Default mode is `shared`, which uses SELinux relabeling that is friendly to multiple containers sharing one project directory.

- `shared` is the default and the right choice unless a host-specific issue says otherwise.
- `private` keeps the mount stricter for one-container-at-a-time use.
- `disable` exists only as an escape hatch when SELinux labeling blocks startup on a specific host.
- You can set `CODEX_BOX_WORKSPACE_LABEL=shared|private|disable` instead of passing the flag every time.

The wrapper still keeps other guardrails in place:

- `no-new-privileges`
- `rprivate` bind propagation
- `bind-nonrecursive=true`
- `--http-proxy=false`
- `--no-hosts`
- `--pids-limit=512`
- Sets `CODEX_ASSUME_EXTERNAL_SANDBOX=1` so wrapper-launched Codex can bypass Codex's nested sandbox and treat the Podman box as the outer boundary.
- Seeds new boxes with `model = "gpt-5.4-mini"` and `model_reasoning_effort = "xhigh"` in `~/.codex/config.toml`.

## Why it is separate

The wrapper is host and container integration glue. It is useful, but it is not the same layer as the Python usage tracker, the budget policy, or the repo-local launch logic. Keeping it in `tools/` makes the split obvious and reduces the chance that the shim gets treated like core workflow code.
