# Lookdev Studio USD Viewer

Browser-controlled USD lookdev viewer for the prepared studio scene in `studio/`.

The app is split into two processes:

- `server/`: Python runtime that owns OpenUSD composition, `ovrtx` RTX rendering, `ovstream` WebRTC streaming, camera control, picking, selection, and render settings.
- `frontend/`: React UI that displays the streamed video and sends app commands over the WebRTC data channel.

The browser never renders USD geometry. It displays the `ovstream` video output from the server.

## Runtime Target

Authoring can happen on any machine. On this Windows workstation, run the
`ovrtx`/`ovstream` server natively on Windows, not under WSL2. WSL2 can expose
CUDA/NVENC on this device, but the current `ovrtx` renderer path needs direct
Vulkan/NVML access and failed there with `ERROR_INCOMPATIBLE_DRIVER`.

The server is supported on:

- native Windows 11 with an NVIDIA RTX GPU and current NVIDIA drivers
- Linux x86_64 RTX hosts with Vulkan/NVENC available outside WSL2

Runtime requirements:

- NVIDIA RTX GPU
- NVIDIA driver with NVENC support
- Node.js 20+ and npm 10+ for the frontend
- Python 3.10 or 3.11 for the server

See `docs/runtime-setup.md` for device-specific WSL2 and native Windows runtime findings.
See `docs/development-runbook.md` for toolchain and debugging issues encountered during viewer development.

## Workspace Layout

```text
.
  studio/                 Prepared lookdev environment, kept unmodified
  assets/                 Server-side user USD assets to load into the studio
  data/                   Viewer settings and runtime-generated files
  scripts/                Linux setup/run helpers
  server/                 ovrtx + ovstream backend
  frontend/               React browser UI
  validation/             Validation report template
```

## Asset Loading Model

The studio scene is always the base environment. User assets are resolved by the server from `assets/` or an allow-listed absolute path, then referenced into a viewer-owned composite stage under `/LookdevAsset`.

User USD files and `studio/lookdev-studio.usdc` are not modified.

## Dev Environment With mise

This project uses `mise` to provision the development toolchain:

```bash
mise install
mise run setup
```

Pinned tools live in `mise.toml`:

- Python 3.11
- Node.js 20

## Native Windows Runtime Setup

From the workspace root on this RTX Windows host:

```powershell
mise install
mise run setup:server:win
mise run setup:frontend
```

`setup:server:win` creates `.venv-win-runtime/` and installs the native Windows
`ovrtx`/`ovstream` runtime packages.

Copy user USD assets under `assets/`.

## Linux RTX Host Setup

From the workspace root on the RTX Linux host:

```bash
mise install
mise run setup:server
mise run setup:frontend
```

`setup:server` creates `.venv-linux/`; the Windows authoring setup uses `.venv/`;
the native Windows runtime setup uses `.venv-win-runtime/`.

Copy or mount user USD assets under `assets/`.

## Run

Terminal 1 on native Windows:

```powershell
mise run run:server:win
```

Terminal 1 on a Linux RTX host:

```bash
mise run run:server
```

Terminal 2:

```bash
cd frontend
mise run dev:frontend
```

Open the Vite URL in a browser. For a remote server, pass connection details:

```text
http://frontend-host:5173/?server=RTX_SERVER_HOST&signalingport=49100
```

## Controls

- Left drag: orbit
- Middle drag: pan
- Right drag: dolly
- Wheel: zoom
- Left click release without drag: select prim
- Fit: frame the loaded asset or full studio

## Render Settings

The render settings panel is capability-backed. Controls for samples, denoiser, resolution, and viewer lighting are present, but the server reports whether each setting is live, reload-required, reconnect-required, or unsupported for the active runtime.

## Validation

Use `validation/viewer-validation.md` after running on the RTX host. This Windows authoring workspace cannot validate `ovrtx` or `ovstream` runtime behavior unless those Linux GPU dependencies are available.
