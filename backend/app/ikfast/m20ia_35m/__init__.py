"""FANUC M-20iA/35M 的 ikfast 源码与编译产物。"""

from pathlib import Path

MODEL_ID = "m20ia_35m"
ROBOT_NAME = "FANUC M-20iA/35M"
NUM_JOINTS = 6

PACKAGE_DIR = Path(__file__).resolve().parent
LIB_DIR = PACKAGE_DIR / "lib"
