# Viewer Validation Report

## Metadata

| Field | Value |
|---|---|
| App or repo | Lookdev Studio USD Viewer |
| Branch or commit | no git repository in workspace |
| Date | 2026-07-08 |
| Reviewer | Codex |
| Delivery path | Browser WebRTC |
| Runtime environment | Native Windows, NVIDIA GeForce RTX 3090 Ti, driver 610.62 |
| Scene inputs | `studio/lookdev-studio.usdc`, sanitized asset names only |

## Commands Run

| Step | Command | Result | Artifact |
|---|---|---|---|
| Setup | `mise run setup:server:win` | Pass | installed `.venv-win-runtime` with `ovrtx`, `ovstream`, `warp-lang`, `numpy`, `usd-core==24.11` |
| Runtime smoke | `.venv-win-runtime\Scripts\python.exe -u -c "...LookdevRuntime...renderer.step..."` | Pass | renderer constructed, stage loaded, first frame handled |
| Runtime launch | `mise run run:server:win -- --width 640 --height 360 --fps 10 --signaling-port 49101 --health-port 18081` | Pass | health endpoint reached readiness |
| Frontend build / Python compile | `mise run validate` | Pass | Vite build warning only: large `@nvidia/ov-web-rtc` chunk |
| Health | `Invoke-WebRequest -UseBasicParsing http://127.0.0.1:18081/healthz` | Pass | `200 ok` |
| Runtime launch | `mise run run:server:win` | Pass | native server produced `First ovrtx frame ready: 1920x1080`; final process left running on `49100` / `8081` |
| Frontend launch | `mise run dev:frontend` | Pass | Vite served `http://localhost:5173/` |
| Browser WebRTC | `http://localhost:5173/?server=127.0.0.1&signalingport=49100` | Pass | `validation/artifacts/browser-live-stream.png`; video `readyState=4`, `1920x1080`, current time advancing |
| Frontend build / Python compile | `mise run validate` | Pass | Vite build warning only: large `@nvidia/ov-web-rtc` chunk; `server/runtime.py` compiled |

## Evidence Checklist

| Evidence | Status | Artifact | Notes |
|---|---|---|---|
| Startup and dependency output captured | Pass | command output in current run | Native Windows runtime setup completed |
| First nonblank rendered frame captured | Pass | `validation/artifacts/windows-ldrcolor-smoke.npy` | `LdrColor` mapped as `180x320x4 uint8`, range `0..255`, mean `63.95` |
| Browser WebRTC video decoded | Pass | `validation/artifacts/browser-live-stream.png` | Browser video element reported `readyState=4`, `paused=false`, `videoWidth=1920`, `videoHeight=1080` |
| Stage hierarchy receives root children | Pass | browser logs and screenshot | Server pushed `root_prim_path=/root`; tree populated 109 prims with `/root/...` children |
| Camera orbit, pan, zoom, and fit-to-asset verified | Partial | browser interaction pass | Fit/reset controls visible and data channel active; full mouse gesture suite not run |
| Object selection updates viewport, tree, and property panel | Pass | browser interaction pass | Clicking `/root/env_light` selected the tree row and property panel showed path/name/type |
| Asset replacement clears stale selection and refreshes hierarchy | Not run |  | No USD assets found under `assets/`; asset switch flow could not be exercised |
| Render setting capability and AOV changes verified | Partial | browser interaction pass | AOV and resolution controls populate from server state; non-`LdrColor` AOVs now fall back safely to `LdrColor` if tensor streaming fails |
| Shutdown and reconnect behavior verified | Partial | browser interaction pass | Fresh-tab reconnect works after server restarts; hard browser reload can leave transient stale peer warnings in ovstream logs |

## Issues And Waivers

| ID | Severity | Summary | Owner | Resolution |
|---|---|---|---|---|
| WSL2-Vulkan | Medium | WSL2 imports runtime packages but `ovrtx.Renderer` fails with Vulkan `ERROR_INCOMPATIBLE_DRIVER` |  | Use native Windows runtime on this device |
| UI-E2E | Resolved | Browser interaction evidence was missing |  | Native server plus Vite client connected; browser decoded WebRTC video, received data-channel state, populated tree/settings, and selected `/root/env_light` |
| ASSET-E2E | Low | Asset replacement flow not exercised |  | Add at least one sanitized USD asset under `assets/` and rerun load/clear-selection validation |
| RELOAD-PEER | Low | Hard browser reload during direct WebRTC development can leave transient stale peer warnings |  | Open a fresh tab or restart server for a clean local session; fresh-tab reconnect validated |

## Result

Overall status: pass with remaining asset/camera-depth gaps

Reviewer notes: Native Windows runtime path is validated through first frame, health readiness, browser WebRTC decode, data-channel initial state, stage hierarchy, render settings, and tree/property selection sync. Asset switching remains untested because `assets/` contains no USD files.
