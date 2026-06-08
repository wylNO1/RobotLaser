/// C 导出层：将 ikfast C++ API 封装为 ctypes 可调用的纯 C 接口。
/// 与 M-20iA_35M.cpp 一同编译（见 build.cmd）。

#define IKFAST_HAS_LIBRARY
#include "ikfast.h"

#include <vector>

using namespace ikfast;

#ifdef _WIN32
#define IK_EXPORT extern "C" __declspec(dllexport)
#else
#define IK_EXPORT extern "C"
#endif

IK_EXPORT int m20ia35m_get_num_joints(void) { return GetNumJoints(); }

IK_EXPORT int m20ia35m_get_num_free_parameters(void) { return GetNumFreeParameters(); }

IK_EXPORT const char* m20ia35m_get_kinematics_hash(void) { return GetKinematicsHash(); }

IK_EXPORT const char* m20ia35m_get_ikfast_version(void) { return GetIkFastVersion(); }

/// 逆解：平移(米) + 旋转矩阵(行优先 3x3) -> 关节角(弧度)。
IK_EXPORT int m20ia35m_compute_ik(
    const double* eetrans,
    const double* eerot,
    double* joints_out,
    int max_solutions)
{
    if (!eetrans || !eerot || !joints_out || max_solutions <= 0) {
        return -1;
    }

    IkSolutionList<IkReal> solutions;
    if (!ComputeIk(eetrans, eerot, nullptr, solutions)) {
        return -1;
    }

    const int dof = GetNumJoints();
    const int n = static_cast<int>(solutions.GetNumSolutions());
    const int to_write = n < max_solutions ? n : max_solutions;

    std::vector<IkReal> solvalues(static_cast<size_t>(dof));
    for (int i = 0; i < to_write; ++i) {
        const IkSolutionBase<IkReal>& sol = solutions.GetSolution(static_cast<size_t>(i));
        sol.GetSolution(solvalues.data(), nullptr);
        for (int j = 0; j < dof; ++j) {
            joints_out[i * dof + j] = static_cast<double>(solvalues[static_cast<size_t>(j)]);
        }
    }
    return to_write;
}

/// 正解：6 关节角(弧度) -> 平移 + 行优先旋转矩阵。
IK_EXPORT void m20ia35m_compute_fk(
    const double* joints,
    double* eetrans_out,
    double* eerot_out)
{
    if (!joints || !eetrans_out || !eerot_out) {
        return;
    }
    ComputeFk(joints, eetrans_out, eerot_out);
}
