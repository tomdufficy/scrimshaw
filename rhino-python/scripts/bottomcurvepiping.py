# ================================================================================
# Script Name:     bottomcurvepiping.py
# Author:          Tom Dufficy
# Copyright:       Copyright (c) 2025 Tom Dufficy. All rights reserved.
# License:         MIT License (see LICENSE file for details)
# Version:         1.0.0
#
# Description:
#     Generates curves around the outer perimeter of the bottom face
#     of selected volumes (BREPs), groups them, and prompts for curve
#     piping settings so the edges of separate volumes are rendered by Enscape
#     (which usually suppresses coplanar face edges).
#
# Requirements:
#     Rhino 8
#     Not tested with other versions of Rhino
#
# Change Log:
#     1.0.0 - Initial release.
# ================================================================================

import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import AreaMassProperties, Curve

# Find the bottom-most face of a given Brep
def get_bottom_face(brep):
    lowest_face = None
    lowest_z = None
    for face in brep.Faces:
        fbrep = face.DuplicateFace(False)
        amp = AreaMassProperties.Compute(fbrep)
        if amp:
            z = amp.Centroid.Z
            if lowest_face is None or z < lowest_z:
                lowest_face = face
                lowest_z = z
    return lowest_face

# Extract the joined outer border curve(s) from a BrepFace
def get_outer_border_curves(face):
    loop = face.OuterLoop
    if not loop:
        return []
    crvs = []
    for trim in loop.Trims:
        edge = trim.Edge
        if edge:
            c = edge.DuplicateCurve()
            if c:
                crvs.append(c)
    tol = sc.doc.ModelAbsoluteTolerance
    joined = Curve.JoinCurves(crvs, tol)
    return list(joined) if joined else crvs

# Main execution
def main():
    # Ask user to select volumes
    brep_ids = rs.GetObjects("Select BREPs", rs.filter.surface | rs.filter.polysurface, preselect=True)
    if not brep_ids:
        return

    baked = []
    for bid in brep_ids:
        brep = rs.coercebrep(bid)
        if not brep:
            continue
        face = get_bottom_face(brep)
        if not face:
            continue
        for crv in get_outer_border_curves(face):
            cid = sc.doc.Objects.AddCurve(crv)
            if cid:
                baked.append(cid)

    if not baked:
        print("No border curves created.")
        return

    # Group all baked curves
    gname = rs.AddGroup("BottomFaceCurves")
    rs.AddObjectsToGroup(baked, gname)

    # Select all curves and open curve piping settings in command line
    rs.UnselectAllObjects()
    rs.SelectObjects(baked)
    rs.Command("_-Properties _Object _CurvePiping _On _Enter", echo=True)

    print("Created {0} curve(s), grouped, and ready for curve piping settings.".format(len(baked)))

if __name__ == "__main__":
    main()
