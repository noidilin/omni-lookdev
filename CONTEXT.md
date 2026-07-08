# Lookdev Studio

Lookdev Studio is a streamed USD asset review app where a server-owned RTX runtime loads assets into a stable studio environment and the browser presents controls plus the WebRTC video stream.

## Language

**Asset Refresh**:
Rescanning the asset catalog so the asset list reflects files currently available to the server. It does not mutate the renderer stage or change the current asset.
_Avoid_: Reload, cache flush

**Asset Reload**:
Reopening the current asset path from disk while preserving lookdev context and rebuilding stage-derived context. It is for same-name file updates where the asset identity stays the same.
_Avoid_: Refresh

**Current Asset Path**:
The server-resolved USD file path for the asset currently committed in the viewer. Asset reload targets this path directly and does not rescan the asset catalog first.
_Avoid_: Asset catalog entry

**Reload Asset**:
The user-facing command for reopening the current asset from disk. It always uses cache-flushing reload semantics so users do not need to choose between ordinary reload and cache invalidation.
_Avoid_: Flush button, refresh button

**Transactional Reload**:
An asset reload that commits new stage-derived context only after the reloaded asset is usable. If reload fails, the viewer keeps the last good render active and reports the failed reload without replacing the current asset.
_Avoid_: Destructive reload

**Cache Flush**:
A forced asset reload that deliberately invalidates viewer-owned cached load identity so same-path USD content is read again. It preserves lookdev context and rebuilds stage-derived context.
_Avoid_: Refresh, ordinary load

**Lookdev Context**:
User-facing review state that should survive an asset reload when still valid, such as render settings, active AOV, camera pose, and current asset identity.
_Avoid_: Stage cache

**Reload Camera Policy**:
The rule that an asset reload preserves the current camera pose for visual comparison, then falls back to fitting the reloaded asset only when the preserved pose is invalid or clearly unusable.
_Avoid_: Always fit, always reset

**Stage-Derived Context**:
Runtime state derived from the loaded USD stage that must be cleared and rebuilt after an asset reload, such as hierarchy, selected prim, property data, pickable maps, renderer query data, and generated composite identity.
_Avoid_: Lookdev context

**Stage Operation**:
A renderer-owned mutation of the loaded stage, including asset switch and asset reload. Only one stage operation may run at a time, and asset controls are locked while one is active.
_Avoid_: Background UI refresh

**Reload Feedback**:
UI feedback for reloading the current asset while the last good render remains active. The current row stays current, the asset pane says `Reloading asset...`, and failures are shown near the asset controls without clearing the current asset.
_Avoid_: Switching feedback, failed current asset

**Reload Request**:
A client message asking the server to reopen the committed current asset path from disk. It does not carry a browser-chosen path because reload authority belongs to the server.
_Avoid_: Forced load request
