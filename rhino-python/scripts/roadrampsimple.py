# -*- coding: utf-8 -*-
# ================================================================================
# Script Name:     roadrampsimple.py
# Author:          Tom Dufficy
# Copyright:       Copyright (c) 2025 Tom Dufficy. All rights reserved.
# License:         MIT License (see LICENSE file for details)
# Version:         1.0.0
#
# Description:
#     Creates a simple uniformly sloped road surface from a LEFT-hand flat base
#     curve. The script builds two perpendicular section lines (at the start and
#     end of the rail), lowers the end section by the required drop from the
#     longitudinal slope, and sweeps a surface between them.
#
#     Preview (non-modal) lets you rotate/zoom the view and choose:
#       - Proceed (Enter)  : create the surface
#       - FlipSlope        : swap up/down along the rail
#       - FlipOffset       : switch side (right/left) of the base curve
#       - Cancel           : exit and remove preview
#
#     After the surface is generated, a popup asks if you would also like to
#     create a solid boolean volume to carve a cavity: a closed solid whose
#     bottom face is the new ramp surface and whose top face is a copy offset
#     vertically by 10 metres (i.e. a vertical “thickening”, not a normal offset).
#
# Requirements:
#     Rhino 7 / Rhino 8
#     Not tested with other versions of Rhino
# ================================================================================

import rhinoscriptsyntax as rs
import Rhino

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

# Check whether a curve is approximately flat in Z by sampling points
def is_flat_curve(curve_id, tol=1e-3):
    pts = rs.DivideCurve(curve_id, 50, create_points=False)
    if not pts:
        return False
    zs = [p.Z for p in pts]
    return (max(zs) - min(zs)) <= tol

# Build a perpendicular section line at parameter t
# lateral direction = world Z × tangent (perpendicular in plan)
def make_perp_section(curve_id, t, width, offset_dir=+1):
    pt = rs.EvaluateCurve(curve_id, t)
    tan = rs.CurveTangent(curve_id, t)
    if (pt is None) or (tan is None):
        return None
    tan.Unitize()
    z = Rhino.Geometry.Vector3d(0, 0, 1)
    x = Rhino.Geometry.Vector3d.CrossProduct(z, tan)
    if x.IsTiny():
        x = Rhino.Geometry.Vector3d(1, 0, 0)
    x.Unitize()
    a = Rhino.Geometry.Point3d(pt.X, pt.Y, pt.Z)
    b = a + x * (width * offset_dir)
    return rs.AddLine(a, b)

# Robustly obtain a curve parameter from a normalised value u ∈ [0,1]
def param_from_normalised(curve_id, u):
    t = rs.CurveParameter(curve_id, u)
    if t is not None:
        return t
    ok = rs.CurveNormalizedParameter(curve_id, u)
    if ok is not None:
        return ok
    d0, d1 = rs.CurveDomain(curve_id)
    return d0 + (d1 - d0) * u

# Build points for the graded RIGHT edge (preview curve), sampling along the rail
def build_right_edge_points(curve_id, width, dz_along, offset_dir, slope_sign, samples=24):
    if samples < 2:
        samples = 2
    pts = []
    for i in range(samples + 1):
        u = float(i) / float(samples)
        t = param_from_normalised(curve_id, u)

        pt = rs.EvaluateCurve(curve_id, t)
        tan = rs.CurveTangent(curve_id, t)
        if (pt is None) or (tan is None):
            continue

        tan.Unitize()
        z = Rhino.Geometry.Vector3d(0, 0, 1)
        x = Rhino.Geometry.Vector3d.CrossProduct(z, tan)
        if x.IsTiny():
            x = Rhino.Geometry.Vector3d(1, 0, 0)
        x.Unitize()

        # Lateral offset from base point
        lateral = Rhino.Geometry.Point3d(
            pt.X + x.X * (width * offset_dir),
            pt.Y + x.Y * (width * offset_dir),
            pt.Z + x.Z * (width * offset_dir)
        )

        # Longitudinal drop at fraction u (down if slope_sign = +1)
        dz = (u * dz_along) * (+1 if slope_sign > 0 else -1)

        graded = Rhino.Geometry.Point3d(lateral.X, lateral.Y, lateral.Z - dz)
        pts.append(graded)
    return pts

# Add an interpolated curve through points (degree 3)
def add_interp_curve(pts):
    if len(pts) < 2:
        return None
    return rs.AddInterpCurve(pts, degree=3, knotstyle=0)

# Return the endpoint that is NOT on the base (the offset end)
def right_edge_endpoint(section_id):
    return rs.CurveEndPoint(section_id)

# Build the full preview set (sections, right-edge preview curve, text dots)
def build_preview(rail, width, dz_along, offset_dir, slope_sign):
    d0, d1 = rs.CurveDomain(rail)

    sec0 = make_perp_section(rail, d0, width, offset_dir=offset_dir)
    sec1 = make_perp_section(rail, d1, width, offset_dir=offset_dir)
    if not (sec0 and sec1):
        return [], None, None

    # Lower the end section by the longitudinal drop
    rs.MoveObject(sec1, [0, 0, -(slope_sign * dz_along)])

    # Colour sections (blue)
    rs.ObjectColor(sec0, (0, 170, 255))
    rs.ObjectColor(sec1, (0, 170, 255))

    # Right-edge preview curve (darker blue)
    pts = build_right_edge_points(rail, width, dz_along, offset_dir, slope_sign, samples=24)
    edge = add_interp_curve(pts)
    if edge:
        rs.ObjectColor(edge, (0, 100, 255))
        rs.ObjectPrintWidth(edge, 0.4)

    # Labels at offset ends
    p_start = right_edge_endpoint(sec0)
    p_end   = right_edge_endpoint(sec1)
    dot_a = rs.AddTextDot("Start", p_start)
    dot_b = rs.AddTextDot(u"End (ΔZ = {:.3f} m)".format(slope_sign * dz_along), p_end)

    ids = [sec0, sec1, dot_a, dot_b]
    if edge:
        ids.append(edge)
    return ids, sec0, sec1

# Non-modal command-line options; Enter defaults to Proceed
# Returns: 1 Proceed, 2 Flip slope, 3 Flip offset, 4 Cancel/ESC
def ask_action():
    go = Rhino.Input.Custom.GetOption()
    go.SetCommandPrompt("Preview: Enter=Proceed  |  FlipSlope  |  FlipOffset  |  Cancel")

    optProceed   = go.AddOption("Proceed")
    optFlipSlope = go.AddOption("FlipSlope")
    optFlipSide  = go.AddOption("FlipOffset")
    optCancel    = go.AddOption("Cancel")

    go.AcceptNothing(True)

    while True:
        rc = go.Get()
        if rc == Rhino.Input.GetResult.Option:
            idx = go.OptionIndex()
            if idx == optProceed:   return 1
            if idx == optFlipSlope: return 2
            if idx == optFlipSide:  return 3
            if idx == optCancel:    return 4
        elif rc == Rhino.Input.GetResult.Nothing:
            return 1
        elif rc == Rhino.Input.GetResult.Cancel:
            return 4

# Ask user whether to create a vertical-offset solid volume (10 m up)
def ask_make_volume():
    msg = "Create a solid boolean volume to carve the cavity?\nBottom face = ramp surface; top face = ramp surface moved +10 m in Z."
    # Yes/No box: returns 6 for Yes, 7 for No
    return rs.MessageBox(msg, 4 | 64, "Create Cutter Volume?") == 6

# Duplicate ramp surface, copy it up in +Z by 'height', loft borders to make sides, join to a solid.
def make_vertical_offset_solid_from_surface(srf_id, height=10.0):
    # Duplicate the bottom face so the original remains for the user
    base_dup = rs.CopyObject(srf_id)
    if not base_dup:
        return None

    top_srf = rs.CopyObject(srf_id, [0, 0, height])
    if not top_srf:
        rs.DeleteObject(base_dup)
        return None

    # Get the outer borders on both faces (prefer single closed curve)
    def _outer_border(sid):
        crvs = rs.DuplicateSurfaceBorder(sid, type=0)
        if not crvs:
            return None
        # Could be a single id or a list; choose the longest if list
        if isinstance(crvs, list):
            best = None
            best_len = -1.0
            for c in crvs:
                L = rs.CurveLength(c) or 0.0
                if L > best_len:
                    best = c; best_len = L
            # delete any extras we won’t use
            for c in crvs:
                if c != best:
                    rs.DeleteObject(c)
            return best
        return crvs

    bot_border = _outer_border(base_dup)
    top_border = _outer_border(top_srf)
    if not (bot_border and top_border):
        if bot_border: rs.DeleteObject(bot_border)
        if top_border: rs.DeleteObject(top_border)
        rs.DeleteObject(base_dup); rs.DeleteObject(top_srf)
        return None

    # Side wall via loft between the two closed borders
    side = rs.AddLoftSrf([bot_border, top_border], loft_type=0, simplify_method=0, value=None)
    # Clean border curves
    rs.DeleteObject(bot_border)
    rs.DeleteObject(top_border)

    side_ids = []
    if isinstance(side, list):
        side_ids = [sid for sid in side if sid]
    elif side:
        side_ids = [side]

    if not side_ids:
        rs.DeleteObject(base_dup); rs.DeleteObject(top_srf)
        return None

    # Join bottom + top + side(s) into a closed solid (keep original ramp surface separate)
    join_list = [base_dup, top_srf] + side_ids
    solid = rs.JoinSurfaces(join_list, delete_input=True)
    if not solid:
        return None

    if not rs.IsObjectSolid(solid):
        try:
            rs.CapPlanarHoles(solid)
        except Exception:
            pass
    return solid

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main():
    rs.EnableRedraw(True)
    rs.UnselectAllObjects()

    rail = rs.GetObject("Select LEFT-hand road edge curve (flat in Z)", rs.filter.curve, preselect=False, select=False)
    if not rail:
        return

    if not is_flat_curve(rail, tol=1e-3):
        if rs.MessageBox("Curve does not appear to be flat in Z (ΔZ > 1 mm). Continue?", 4 | 48, "Warning") != 6:
            return

    # Defaults (European-style)
    width = rs.GetReal("Road width (metres)", number=6.0, minimum=0.01)
    if width is None:
        return

    slope_pct = rs.GetReal("Longitudinal slope (%)", number=5.0)
    if slope_pct is None:
        return

    # Total longitudinal drop along the rail (metres)
    L = rs.CurveLength(rail)
    dz_along = (slope_pct / 100.0) * L

    # Preview state
    offset_dir = +1   # +1 => right of base; -1 => left
    slope_sign = +1   # +1 => end goes DOWN by dz_along; -1 => up

    srf = None
    while True:
        rs.EnableRedraw(False)
        prev_ids, sec0, sec1 = build_preview(rail, width, dz_along, offset_dir, slope_sign)
        rs.EnableRedraw(True)

        if not prev_ids:
            rs.MessageBox("Failed to build preview. Please check inputs.", 16, "Error")
            return

        action = ask_action()

        # Clear preview before next step
        rs.EnableRedraw(False)
        for gid in prev_ids:
            if rs.IsObject(gid):
                rs.DeleteObject(gid)
        rs.EnableRedraw(True)

        if action == 2:  # flip slope
            slope_sign *= -1
            continue
        if action == 3:  # flip side
            offset_dir *= -1
            continue
        if action == 1:  # proceed
            rs.EnableRedraw(False)
            prev_ids, sec0, sec1 = build_preview(rail, width, dz_along, offset_dir, slope_sign)
            try:
                srf = rs.AddSweep1(rail, [sec0, sec1])
            except Exception:
                srf = None
            for gid in prev_ids:
                if rs.IsObject(gid):
                    rs.DeleteObject(gid)
            rs.EnableRedraw(True)
            if not srf:
                rs.MessageBox("Sweep1 failed. Try different inputs or check rail direction.", 16, "Sweep1 Error")
            else:
                # Offer to create vertical-offset solid (10 m)
                if ask_make_volume():
                    vol = make_vertical_offset_solid_from_surface(srf, height=10.0)
                    if not vol:
                        rs.MessageBox("Failed to create the solid volume.", 16, "Volume Error")
            return

        # Cancel / ESC
        return

if __name__ == "__main__":
    main()
