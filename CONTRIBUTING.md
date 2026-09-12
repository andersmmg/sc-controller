# Contributing to SC Controller

Thanks for wanting to help! This doc covers how to get a development setup
running, what the project expects from patches, and the little things (tabs!)
that will save us both a round of review comments.

Bugs and feature ideas go to the GitHub issue tracker. For code, read on.


## Getting set up

You'll want Python 3.10 or newer and the usual GTK/USB libraries. On a
Debian/Ubuntu-ish system:

```bash
sudo apt-get install python3-pip python3-setuptools python3-gi \
    gir1.2-gtk-3.0 gir1.2-rsvg-2.0 python3-evdev python3-dev \
    zlib1g-dev libusb-1.0-0-dev
```

On Arch (or anything pacman-based), the same stack is:

```bash
sudo pacman -S --needed base-devel python-setuptools python-gobject \
    python-cairo gtk3 librsvg python-evdev libusb zlib
```

One Arch specific warning: its system Python is marked externally managed, 
so use `--break-system-packages` or a venv.

(Other distros: same packages, different names. Reference the CI workflow in
`.github/workflows/tests.yml`)

To start the GUI:

```bash
./run.sh
```

To run just the daemon (useful when working on drivers):

```bash
./daemon.sh            # foreground
./daemon.sh debug      # with debug logging
```

Both scripts set up `PYTHONPATH` and `SCC_SHARED` for you, so it should
just work.


## Running the tests

From the repo root:

```bash
python3 -m pytest tests/ -q
```


## Lint and format

The project uses [ruff](https://docs.astral.sh/ruff/) for both, managed with
[uv](https://docs.astral.sh/uv/).
To get an identical environment:

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
```

If you'd rather not use uv, any ruff matching the pinned version works.

`ruff format` is the arbiter of style. The config lives in `pyproject.toml`,
and the short version is:

- **Tabs for indentation.** Yes, really. This is a large older codebase and
  the whole tree is tab-indented, the formatter is configured for it.

Run `ruff format` on your files before submitting. Please don't reformat
files you aren't otherwise touching.


## Type checking

[ty](https://docs.astral.sh/ty/) is the type checker, installed by the
same `uv sync` as ruff:

```bash
uv run ty check
```

Checking is currently only done on files in the override list in 
`pyproject.toml`. Until all the core modules are fully annotated, 
add new modules to that list.

Give new functions annotated signatures and keep `# type: ignore` comments 
rare and justified.


## Git and pull requests

Commit messages should mostly follow the [conventional commits](https://www.conventionalcommits.org/) 
specification. Keep the first line short and descriptive.

If your change touches several unrelated things, split it into several commits; it
makes bisecting regression reports possible.

For pull requests:

- Keep one topic per PR. A bug fix plus an unrelated refactor in the same
  branch makes both harder to review.
- Include tests when the change is testable without hardware.
- Make sure `ruff check`, `ruff format --check`, `ty check` and `pytest` all
  pass locally before pushing. PRs must pass CI before they'll be merged.
- If you want to rehearse the full CI job in Docker before pushing,
  [act](https://github.com/nektos/act) works:
  `act push -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 -j test`


## Finding work

Reasonably safe first contributions: extending the strict typing,
adding tests for untested modules, and clearing items from the maintenance
list in `TODO.md`.

Issues may be labeled `good first issue` or `help wanted`; these are issues
that are easy to pick up and shouldn't require deep knowledge of the codebase.

The project is licensed under GPLv2; by contributing you agree that your
code is distributed under the same terms.
