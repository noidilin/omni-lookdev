from __future__ import annotations

from pathlib import Path

from .config import OV_CAMERA_PRIM, OV_RENDER_PRODUCT


STUDIO_CAMERA_XFORM = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 0.049989992045490705, 0.9987497187460389, 0.0),
    (0.0, -0.9987497187460389, 0.049989992045490705, 0.0),
    (0.0, -12.266838073730469, 1.600000023841858, 1.0),
)


def _asset_ref(path: Path, base_dir: Path) -> str:
    try:
        rel = path.resolve().relative_to(base_dir.resolve())
        return rel.as_posix()
    except ValueError:
        return path.resolve().as_posix()


def make_lookdev_composite(
    studio_stage: Path,
    asset_stage: Path | None,
    output_dir: Path,
    width: int,
    height: int,
    settings: dict,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    composite = output_dir / "_lookdev_viewer_composite.usda"
    composite.write_text(
        make_lookdev_composite_text(studio_stage, asset_stage, output_dir, width, height, settings),
        encoding="utf-8",
    )
    return composite


def make_lookdev_composite_text(
    studio_stage: Path,
    asset_stage: Path | None,
    base_dir: Path,
    width: int,
    height: int,
    settings: dict,
) -> str:
    safe_width = max(1, int(width))
    safe_height = max(1, int(height))
    studio_ref = _asset_ref(studio_stage, base_dir)
    asset_block = ""
    if asset_stage is not None:
        asset_ref = _asset_ref(asset_stage, base_dir)
        asset_block = f'''
def Xform "LookdevAsset" (
    prepend references = @{asset_ref}@</root>
)
{{
}}
'''

    samples = int(settings.get("samples_per_pixel", 64))
    denoiser = 1 if settings.get("denoiser", True) else 0
    vertical_aperture = 0.36000001430511475 * float(safe_height) / float(safe_width)
    camera_rows = ",".join(
        "(" + ",".join(f"{value:.15g}" for value in row) + ")" for row in STUDIO_CAMERA_XFORM
    )
    lighting = settings.get("viewer_lighting", {})
    studio_environment_intensity = max(1.0, float(lighting.get("environment_intensity", 1.0))) * 500.0
    light_enabled = bool(lighting.get("enabled", False)) and bool(lighting.get("fallback", False))
    key_intensity = float(lighting.get("key_intensity", 500.0)) if light_enabled else 0.0
    fill_intensity = float(lighting.get("fill_intensity", 80.0)) if light_enabled else 0.0
    environment_intensity = float(lighting.get("environment_intensity", 1.0)) if light_enabled else 0.0
    viewer_lighting_block = ""
    if light_enabled:
        viewer_lighting_block = f'''
def Scope "ViewerLighting"
{{
    def DomeLight "Environment"
    {{
        float intensity = {environment_intensity:.4f}
    }}
    def SphereLight "Key"
    {{
        float intensity = {key_intensity:.4f}
        float radius = 2
        double3 xformOp:translate = (4, 5, 4)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }}
    def SphereLight "Fill"
    {{
        float intensity = {fill_intensity:.4f}
        float radius = 3
        double3 xformOp:translate = (-4, 3, 2)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }}
}}
'''

    return f'''#usda 1.0
(
    subLayers = [
        @{studio_ref}@
    ]
    defaultPrim = "root"
)

{asset_block}
{viewer_lighting_block}

over "root"
{{
    over "env_light"
    {{
        float inputs:intensity = {studio_environment_intensity:.4f}
        float inputs:exposure = 2
    }}
}}

def Camera "OVCamera"
{{
    float focalLength = 1
    float horizontalAperture = 0.36000001430511475
    float verticalAperture = {vertical_aperture:.15g}
    float2 clippingRange = (0.1, 1000)
    token projection = "perspective"
    matrix4d xformOp:transform = ({camera_rows})
    uniform token[] xformOpOrder = ["xformOp:transform"]
}}

def Scope "Render"
{{
    def Scope "OVServer"
    {{
        def RenderProduct "ViewportTexture0" (
            prepend apiSchemas = ["OmniRtxSettingsCommonAdvancedAPI_1", "OmniRtxSettingsPtAdvancedAPI_1", "OmniRtxSettingsRtAdvancedAPI_1"]
        )
        {{
            token omni:rtx:rendermode = "RealTimePathTracing"
            int omni:rtx:pt:maxSamplesPerLaunch = {samples}
            bool omni:rtx:pt:denoising:optix:enabled = {denoiser}
            rel camera = <{OV_CAMERA_PRIM}>
            rel orderedVars = [
                </Render/Vars/LdrColor>,
                </Render/Vars/Depth>,
                </Render/Vars/Normal>
            ]
            uniform int2 resolution = ({safe_width}, {safe_height})
            uint[] deviceIds = [0]
        }}
    }}

    def Scope "Vars"
    {{
        def RenderVar "LdrColor"
        {{
            uniform string sourceName = "LdrColor"
        }}
        def RenderVar "Depth"
        {{
            uniform string sourceName = "DepthSD"
        }}
        def RenderVar "Normal"
        {{
            uniform string sourceName = "NormalSD"
        }}
    }}

    def RenderSettings "OVRenderSettings"
    {{
        rel products = [<{OV_RENDER_PRODUCT}>]
    }}
}}
'''
