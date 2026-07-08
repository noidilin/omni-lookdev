# Development Runbook

This runbook records toolchain and development setup issues seen while debugging
the browser-streamed lookdev viewer. Entries are grouped by the file or tool area
most likely to send a future developer looking for the answer.

## `README.md`

### Fresh Client After Server Restart

Symptom: the browser appears connected, but behavior does not match the server
that was just restarted.

Cause: an existing WebRTC client tab can remain attached to an older or orphaned
server process.

Resolution:

1. Stop the old server.
2. Confirm ports are clear before restarting:

   ```powershell
   Get-NetTCPConnection -LocalPort 49100,8081,5173 -ErrorAction SilentlyContinue |
     Select-Object LocalAddress,LocalPort,State,OwningProcess
   ```

3. Start the server and wait for `First ovrtx frame ready: 1920x1080`.
4. Open a new browser tab with an explicit server URL:

   ```text
   http://localhost:5173/?server=127.0.0.1&signalingport=49100
   ```

5. Verify the video element reports `readyState=4`, `videoWidth=1920`,
   `videoHeight=1080`, and advancing `currentTime`.

### Desktop-Size Browser Verification

Symptom: side panels or toolbar controls hide the stream state, making it hard to
tell whether the app or the viewport is failing.

Resolution: use a desktop-size browser viewport for manual validation, such as
`1600x1000`, then reset the override after the run. Capture evidence from both
the page state and screenshot, not screenshot alone.

## `mise.toml`

### `npm` Not On PATH In Tool Sessions

Symptom:

```text
npm: The term 'npm' is not recognized as a name of a cmdlet...
```

Cause: the interactive tool session may not inherit the same PATH that `mise`
or a user terminal has.

Resolution: prefer the repository tasks in a normal dev shell:

```powershell
mise run dev:frontend
mise run run:server:win
```

If automation must launch Vite from this environment, call the known Node
executable directly:

```powershell
& 'C:\Users\noid\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' `
  '.\node_modules\vite\bin\vite.js' --host 0.0.0.0
```

### Avoid Mixing Package Managers

Symptom: using bundled `pnpm` in `frontend/` created `pnpm-lock.yaml` and
`pnpm-workspace.yaml`, moved npm-installed packages under `.ignored`, and failed
on build-script approval:

```text
ERR_PNPM_IGNORED_BUILDS Ignored build scripts: esbuild
```

Resolution: this frontend currently uses `package-lock.json`; use npm/mise for
setup. If this happens accidentally, remove the generated pnpm files and restore
`node_modules` with the normal frontend setup.

## `scripts/run_server_windows.ps1`

### Native Windows Runtime Is The Expected Local Server Path

Symptom: WSL2 can import CUDA/NVENC-related packages, but `ovrtx.Renderer`
construction fails with Vulkan driver errors.

Resolution: on this workstation, run the server through the native Windows venv:

```powershell
mise run setup:server:win
mise run run:server:win
```

Use `docs/runtime-setup.md` for the detailed WSL2 failure evidence and native
Windows smoke test.

## `server/runtime.py`

### Stage Loads Can Starve WebRTC

Symptom: clicking an asset row or issuing `loadAssetRequest` makes the browser
freeze or automation time out, and server logs show encoder stalls or high frame
intervals.

Cause: loading a stage synchronously on the render loop or stream callback can
block frame production long enough for WebRTC to degrade.

Resolution: keep `renderer.step()` ownership clear, but do not let slow stage
loads run on the stream callback. Guard renderer mutation with a stage lock and
keep streaming the last good frame while a load is in progress.

### Same-Asset Reloads Should Fast-Return

Symptom: reconnecting or clicking the already loaded asset triggers a full reload
and may temporarily blank the client.

Resolution: normalize paths with `os.path.normcase(os.path.abspath(...))`. If
the requested asset is already active, send the current `openStageResult` and
root children without calling `open_usd()`.

## `server/scene_loader.py`

### Validate Generated USDA Before Runtime Debugging

Symptom: ovrtx reports a black frame or a vague render/load failure.

Cause: generated composite USDA can fail because of malformed asset references,
wrong camera relationships, bad default prims, or compact syntax that a bundled
USD parser dislikes.

Resolution: write the exact generated composite to `data/generated/_validate.usda`
and open it with the OpenUSD runtime before chasing renderer behavior:

```powershell
.\.venv-win-runtime\Scripts\python.exe -c "from pxr import Usd; s=Usd.Stage.Open('data/generated/_validate.usda'); print(bool(s))"
```

Check that these prims resolve for the default lookdev scene:

- `/OVCamera`
- `/root/env_light`
- `/LookdevAsset` when an asset is loaded

### Studio Lighting May Need Wrapper Overrides

Symptom: the browser decodes live `LdrColor` frames, the hierarchy is populated,
but the viewport is almost black.

Resolution: preserve `studio/lookdev-studio.usdc`, but author viewer-owned
overrides in the composite wrapper for the studio light. Validate with OpenUSD
that `/root/env_light.inputs:intensity` and `inputs:exposure` resolve to the
intended values.

## `frontend/src/streaming/StreamingProvider.tsx`

### Keep AppStreamer Connect Effect Stable

Symptom: the client shows one frame or briefly connects, then goes black or
disconnects.

Cause: React effect cleanup can terminate `AppStreamer` if the connect effect
depends on changing state or message handlers.

Resolution: keep `AppStreamer.connect()` dependent only on immutable connection
config, route messages through a ref-backed handler set, and catch rejected
`AppStreamer.sendMessage()` promises during reconnect windows.

## `frontend/src/App.tsx`

### Server Initial State Is Authoritative

Symptom: reconnecting reloads the wrong scene or leaves the UI in a permanent
loading state.

Resolution: trust server-pushed `openStageResult` on connect. Do not send a
frontend default `openStageRequest` just because the stream connected. Query
children from the server-provided `root_prim_path`.

## `data/viewer-settings.json`

### Debug AOV Changes Persist

Symptom: after testing `NormalSD`, server logs repeat:

```text
TENSOR input requires dtype=uint8 ... stream_video fell back from NormalSD to LdrColor
```

Cause: AOV selection is persisted in viewer settings. Some debug AOVs are not
converted to BGRA8 before streaming.

Resolution: switch the UI back to `LdrColor` before finishing a validation run,
or edit the settings file back to:

```json
{
  "render": {
    "aov": "LdrColor"
  }
}
```

Longer-term, only expose AOVs that have a verified BGRA8 conversion path, or
convert float/uint32 AOVs before passing them to `ovstream`.

## `validation/viewer-validation.md`

### Minimum Evidence For Browser Stream Fixes

Collect both server and browser proof:

- Server: first-frame log and `/healthz` returning `ok`.
- Browser: fresh tab after server restart, explicit `server=127.0.0.1`, video
  dimensions `1920x1080`, `readyState=4`, advancing `currentTime`.
- Visual: desktop-size screenshot showing the studio and asset in the stream.

Do not treat a loaded DOM or a green connection badge as proof that rendered
frames are visible.

