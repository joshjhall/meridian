---
type: reference
title: Devcontainer workspace mount quirks
description: The bindfs/FUSE overlay on /workspace breaks the Write tool on new files and briefly breaks fresh symlinks.
---

The workspace is a bindfs FUSE overlay on a VirtioFS mount (`mount | grep workspace`). Known quirks:

- **Write tool on a new file** can fail with `EEXIST: file already exists, fsync` even though nothing was written. Workaround: `touch` the file first, `Read` it, then write, or write it with a shell heredoc.
- **A newly created symlink** can report `Too many levels of symbolic links` on first access. It resolves on retry; `readlink -f` confirms the target.
- **`rg` with no path argument** in a backgrounded or non-TTY shell reads stdin and hangs. Always pass a path (`rg pattern .`) and `</dev/null`.
- `.codegraph` is a committed symlink to the `/cache/codegraph` named volume. `codegraph.json` excludes the `containers/` submodule. Only a few files are indexed, since the repo is mostly markdown and data.
- **`rumdl check` without `--no-cache`** reported a file clean that the commit hook then rejected (117 list-indent errors). Use `rumdl check --no-cache`, or trust the lefthook run. `rumdl fmt` fixes these safely: only leading whitespace changes, and it converts `*emphasis*` to `_emphasis_`.
- **Case-insensitive lookups**: the macOS host makes the mount case-insensitive, so once anything stats `Justfile`, listings show it beside the tracked `justfile` (same inode). `just` then errors with "multiple candidate justfiles". Lefthook passes `--justfile justfile`, and the container sets `JUST_JUSTFILE`. In a shell started before a rebuild, export `JUST_JUSTFILE=/workspace/meridian/justfile`.
