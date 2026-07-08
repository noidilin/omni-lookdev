import unittest

import numpy as np

from server.camera_controller import OrbitCamera
from server.scene_loader import STUDIO_CAMERA_XFORM


class CameraControllerTests(unittest.TestCase):
    def test_set_from_xform_reconstructs_studio_camera_view(self) -> None:
        camera = OrbitCamera(1920, 1080)

        self.assertTrue(camera.set_from_xform(STUDIO_CAMERA_XFORM))

        np.testing.assert_allclose(camera.get_camera_xform(), np.asarray(STUDIO_CAMERA_XFORM), atol=1e-10)


if __name__ == "__main__":
    unittest.main()
