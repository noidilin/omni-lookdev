from __future__ import annotations

from pathlib import Path

from .config import LOOKDEV_ASSET_PRIM, OV_CAMERA_PRIM, OV_RENDER_PRODUCT


CAMERA_HORIZONTAL_APERTURE = 20.955


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
    vertical_aperture = CAMERA_HORIZONTAL_APERTURE * float(safe_height) / float(safe_width)
    studio_ref = _asset_ref(studio_stage, base_dir)
    asset_block = ""
    if asset_stage is not None:
        asset_ref = _asset_ref(asset_stage, base_dir)
        asset_block = f'''
def Xform "LookdevAsset" (
    prepend references = @{asset_ref}@
)
{{
}}
'''

    samples = int(settings.get("samples_per_pixel", 64))
    denoiser = 1 if settings.get("denoiser", True) else 0
    lighting = settings.get("viewer_lighting", {})
    light_enabled = bool(lighting.get("enabled", True))
    key_intensity = float(lighting.get("key_intensity", 500.0)) if light_enabled else 0.0
    fill_intensity = float(lighting.get("fill_intensity", 80.0)) if light_enabled else 0.0
    environment_intensity = float(lighting.get("environment_intensity", 1.0)) if light_enabled else 0.0

    return f'''#usda 1.0
(
    subLayers = [
        @{studio_ref}@
    ]
    defaultPrim = "World"
)

{asset_block}
def Camera "OVCamera"
{{
    float2 clippingRange = (0.01, 10000000)
    float focalLength = 18.15
    float horizontalAperture = {CAMERA_HORIZONTAL_APERTURE:.3f}
    float verticalAperture = {vertical_aperture:.4f}
    token projection = "perspective"
    matrix4d xformOp:transform = ((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1))
    uniform token[] xformOpOrder = ["xformOp:transform"]
}}

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
                </Render/Vars/HdrColor>,
                </Render/Vars/Depth>,
                </Render/Vars/Normal>,
                </Render/Vars/InstanceSeg>,
                </Render/Vars/SemanticSeg>,
                </Render/Vars/Diffuse>
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
        def RenderVar "HdrColor"
        {{
            uniform string sourceName = "HdrColor"
        }}
        def RenderVar "Depth"
        {{
            uniform string sourceName = "DepthSD"
        }}
        def RenderVar "Normal"
        {{
            uniform string sourceName = "NormalSD"
        }}
        def RenderVar "InstanceSeg"
        {{
            uniform string sourceName = "InstanceSegmentationSD"
        }}
        def RenderVar "SemanticSeg"
        {{
            uniform string sourceName = "SemanticSegmentationSD"
        }}
        def RenderVar "Diffuse"
        {{
            uniform string sourceName = "DiffuseAlbedoSD"
        }}
    }}

    def RenderSettings "OVRenderSettings"
    {{
        rel products = [<{OV_RENDER_PRODUCT}>]
    }}
}}
'''

