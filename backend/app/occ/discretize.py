"""Discretize TopoDS_Edge / Wire to 3D polylines."""

from __future__ import annotations

from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.GCPnts import GCPnts_QuasiUniformDeflection
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods
from OCC.Core.gp import gp_Pnt


def apply_location(
    pts: list[tuple[float, float, float]],
    loc: TopLoc_Location,
) -> list[tuple[float, float, float]]:
    """Map wire/edge points into world coords (match BRep mesh / GLB)."""
    if loc.IsIdentity() or not pts:
        return pts
    trsf = loc.Transformation()
    out: list[tuple[float, float, float]] = []
    for x, y, z in pts:
        p = gp_Pnt(x, y, z)
        p.Transform(trsf)
        out.append((p.X(), p.Y(), p.Z()))
    return out


def wire_location_on_face(face, wire) -> TopLoc_Location:
    """Cumulative placement of a wire on its face (STEP 装配/实例化常见)."""
    wl = wire.Location()
    fl = face.Location()
    if wl.IsIdentity():
        return fl
    if fl.IsIdentity():
        return wl
    return fl.Multiplied(wl)


def discretize_edge(edge, linear_deflection: float, angular_deflection: float = 0.5) -> list[tuple[float, float, float]]:
    """Sample edge polyline. `angular_deflection` reserved; OCC GCPnts uses linear deflection only."""
    del angular_deflection  # not used by GCPnts_QuasiUniformDeflection
    curve = BRepAdaptor_Curve(edge)
    deflection = GCPnts_QuasiUniformDeflection(curve, linear_deflection)
    if not deflection.IsDone():
        u0, u1 = curve.FirstParameter(), curve.LastParameter()
        p0 = curve.Value(u0)
        p1 = curve.Value(u1)
        return [(p0.X(), p0.Y(), p0.Z()), (p1.X(), p1.Y(), p1.Z())]
    pts: list[tuple[float, float, float]] = []
    for i in range(1, deflection.NbPoints() + 1):
        p = deflection.Value(i)
        pts.append((p.X(), p.Y(), p.Z()))
    return pts


def wire_to_polyline(
    wire,
    linear_deflection: float,
    angular_deflection: float,
    *,
    location: TopLoc_Location | None = None,
) -> list[tuple[float, float, float]]:
    """Discretize a TopoDS_Wire into an ordered polyline.

    IMPORTANT:
    - TopExp_Explorer(wire, EDGE) does NOT guarantee edge order along the wire.
      If we simply append sampled points by explorer order, the resulting point
      sequence can "jump" across the model, which shows up as long unwanted
      segments when visualized in the frontend.

    Strategy:
    - Sample each edge independently.
    - Greedily build a continuous chain by always selecting the next edge whose
      endpoint matches current chain end (forward or reversed).
    - If no connecting edge is found, start a new chain (wire is disjoint or
      explorer order is inconsistent). We still append, but we avoid creating
      an artificial long segment between disconnected parts.

    NOTE:
    - Endpoint matching tolerance is tied to discretization deflection instead
      of a fixed epsilon, which is more robust for curved/large models.
    - If multiple disconnected chains remain, we keep only the longest chain.
      A single polyline cannot represent disjoint chains without introducing
      fake bridge segments between chains.
    """

    edges = []
    exp = TopExp_Explorer(wire, TopAbs_EDGE)
    while exp.More():
        edges.append(topods.Edge(exp.Current()))
        exp.Next()
    if not edges:
        return []

    # sample all edges first
    segs: list[list[tuple[float, float, float]]] = [
        discretize_edge(e, linear_deflection, angular_deflection) for e in edges
    ]

    used = [False] * len(segs)
    chains: list[list[tuple[float, float, float]]] = []
    join_tol = _join_tolerance(linear_deflection)

    def append_seg(chain: list[tuple[float, float, float]], seg: list[tuple[float, float, float]]) -> None:
        if not seg:
            return
        if not chain:
            chain.extend(seg)
            return
        if _dist(chain[-1], seg[0]) <= join_tol:
            chain.extend(seg[1:])
        elif _dist(chain[-1], seg[-1]) <= join_tol:
            chain.extend(list(reversed(seg[:-1])))
        else:
            # disconnected: start a new chain elsewhere
            chains.append(chain.copy())
            chain.clear()
            chain.extend(seg)

    # build chains
    cur: list[tuple[float, float, float]] = []

    # start from first non-empty seg
    start_idx = next((i for i, s in enumerate(segs) if s), None)
    if start_idx is None:
        return []

    cur.extend(segs[start_idx])
    used[start_idx] = True

    while True:
        found = False
        endp = cur[-1]
        for i, seg in enumerate(segs):
            if used[i] or not seg:
                continue
            if _dist(endp, seg[0]) <= join_tol or _dist(endp, seg[-1]) <= join_tol:
                append_seg(cur, seg)
                used[i] = True
                found = True
                break
        if found:
            continue

        # no next edge connects to current chain; try start a new chain
        next_idx = next((i for i, s in enumerate(segs) if (not used[i]) and s), None)
        if next_idx is None:
            break
        chains.append(cur.copy())
        cur = list(segs[next_idx])
        used[next_idx] = True

    if cur:
        chains.append(cur)

    # Keep the longest connected chain; avoid fake bridges between disjoint chains.
    chain = max(chains, key=_polyline_length, default=[])

    if chain and len(chain) >= 3:
        close_tol = max(join_tol * 2.0, linear_deflection * 2.0, 1e-3)
        if _dist(chain[0], chain[-1]) <= close_tol:
            chain.append(chain[0])

    if location is not None:
        return apply_location(chain, location)
    return chain


def wire_area_if_planar(wire) -> float | None:
    """Signed area in wire plane via BRepTools; None if not planar."""
    try:
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GProp import GProp_GProps

        props = GProp_GProps()
        brepgprop.SurfaceProperties(wire, props)
        return abs(props.Mass())
    except Exception:
        return None


def wire_length(wire) -> float:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps

    props = GProp_GProps()
    brepgprop.LinearProperties(wire, props)
    return props.Mass()


def _dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _join_tolerance(linear_deflection: float) -> float:
    """Adaptive wire endpoint tolerance in model units."""
    return max(1e-6, linear_deflection * 0.5)


def _polyline_length(pts: list[tuple[float, float, float]]) -> float:
    if len(pts) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(pts)):
        total += _dist(pts[i - 1], pts[i])
    return total
