# Runtime Setup Notes

## Current Device

This machine has an NVIDIA GeForce RTX 3090 Ti with driver `610.62`.

WSL2 is available with an Arch Linux distro. Inside WSL, CUDA/NVENC visibility is present:

- `nvidia-smi` is available at `/usr/lib/wsl/lib/nvidia-smi`
- `/usr/lib/wsl/lib/libnvidia-encode.so.1` exists
- `/usr/lib/wsl/lib/libnvcuvid.so.1` exists

## Recommendation

Use native Windows for this device. The native Windows `ovrtx` wheel constructs
an RTX renderer successfully, while WSL2 currently fails before renderer
construction with a Vulkan driver error.

Keep WSL2 notes below as diagnostic evidence, not the primary setup path.

## Native Windows Runtime Setup

Create a separate runtime venv and install the server packages:

```powershell
mise install
mise run setup:server:win
```

Smoke test the renderer:

```powershell
$env:OVRTX_SKIP_USD_CHECK = "1"
.\.venv-win-runtime\Scripts\python.exe -c "import ovrtx, ovstream; renderer = ovrtx.Renderer(config=ovrtx.RendererConfig(sync_mode=True)); print('renderer constructed')"
```

Validated on this machine:

```text
ovrtx 0.3.0
ovstream imported
renderer constructed
```

Run the server:

```powershell
mise run run:server:win
```

## WSL2 Setup

Install and trust `mise` inside WSL:

```bash
curl https://mise.run | sh
echo 'eval "$(/home/noid/.local/bin/mise activate bash)"' >> ~/.bashrc
source ~/.bashrc

cd /mnt/c/Users/noid/hub/omni
mise trust mise.toml
mise install
mise run setup:server
```

This creates `.venv-linux/` and installs:

- `ovrtx==0.3.0.312915`
- `ovstream==0.3.0`
- `warp-lang==1.15.0`
- `usd-core==24.11`

Import validation passed in WSL:

```bash
cd /mnt/c/Users/noid/hub/omni
OVRTX_SKIP_USD_CHECK=1 .venv-linux/bin/python - <<'PY'
import ovrtx, ovstream, warp, numpy
print('ovrtx', getattr(ovrtx, '__version__', 'imported'))
print('ovstream', getattr(ovstream, '__version__', 'imported'))
print('warp', warp.__version__)
print('numpy', numpy.__version__)
PY
```

## WSL2 Renderer Blocker

`ovrtx.Renderer` construction currently fails in WSL:

```text
VkResult: ERROR_INCOMPATIBLE_DRIVER
vkCreateInstance failed. Vulkan 1.1 is not supported, or your driver requires an update.
createDevices failed.
Failed to setup graphics.
```

This means WSL can see CUDA/NVENC and import the packages, but it does not currently expose the Vulkan graphics device path that `ovrtx` needs on this machine.

## Native Windows Probe

Windows package discovery shows native Windows wheels exist:

- `ovstream-0.3.0-py3-none-win_amd64`
- `ovrtx-0.3.0.312915-py3-none-win_amd64`

The next runtime probe should use a separate Windows runtime venv, not the authoring `.venv`:

```powershell
mise exec -- python -m venv .venv-win-runtime
.\.venv-win-runtime\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv-win-runtime\Scripts\python.exe -m pip install ovstream ovrtx --index-url https://pypi.nvidia.com --extra-index-url https://pypi.org/simple
```

Then test:

```powershell
$env:OVRTX_SKIP_USD_CHECK = "1"
.\.venv-win-runtime\Scripts\python.exe - <<'PY'
import ovrtx, ovstream
renderer = ovrtx.Renderer(config=ovrtx.RendererConfig(sync_mode=True))
print("renderer constructed")
PY
```

Native Windows renderer construction succeeded. The project now provides
`mise run setup:server:win` and `mise run run:server:win`.
