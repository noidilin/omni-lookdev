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

## Evidence Checklist

| Evidence | Status | Artifact | Notes |
|---|---|---|---|
| Startup and dependency output captured | Pass | command output in current run | Native Windows runtime setup completed |
| First nonblank rendered frame captured | Pass | `validation/artifacts/windows-ldrcolor-smoke.npy` | `LdrColor` mapped as `180x320x4 uint8`, range `0..255`, mean `63.95` |
| Camera orbit, pan, zoom, and fit-to-asset verified | Not run |  | Requires browser/WebRTC interaction pass |
| Object selection updates viewport, tree, and property panel | Not run |  | Requires browser/WebRTC interaction pass |
| Asset replacement clears stale selection and refreshes hierarchy | Not run |  | Requires browser/WebRTC interaction pass |
| Render setting capability and AOV changes verified | Partial | runtime smoke output | AOVs present in first frame; UI setting flow not exercised |
| Shutdown and reconnect behavior verified | Partial | process cleanup check | Test server process stopped; browser reconnect not exercised |

## Issues And Waivers

| ID | Severity | Summary | Owner | Resolution |
|---|---|---|---|---|
| WSL2-Vulkan | Medium | WSL2 imports runtime packages but `ovrtx.Renderer` fails with Vulkan `ERROR_INCOMPATIBLE_DRIVER` |  | Use native Windows runtime on this device |
| UI-E2E | Medium | Browser interaction evidence not captured in this pass |  | Run Playwright/browser validation after connecting frontend to the native Windows server |

## Result

Overall status: partial pass

Reviewer notes: Native Windows runtime path is validated through first frame and health readiness. Browser-side interaction validation remains to be captured.
