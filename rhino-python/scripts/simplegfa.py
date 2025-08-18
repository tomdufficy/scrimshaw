# -*- coding: utf-8 -*-
# ================================================================================
# Script Name:     simplegfa.py
# Author:          Tom Dufficy
# Copyright:       Copyright (c) 2025 Tom Dufficy. All rights reserved.
# License:         MIT License (see LICENSE file for details)
# Version:         1.0.0
#
# Description:
#     Calculates the total area of the bottom faces of selected volumes (BREPs)
#     and displays the result in square meters in a popup message box.
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
import Rhino
from Rhino.Geometry import AreaMassProperties

def get_bottom_face(brep):
    # Return the face with the lowest centroid Z value
    lowest_face = None
    lowest_z = None
    for face in brep.Faces:
        dup = face.DuplicateFace(False)
        amp = AreaMassProperties.Compute(dup)
        if amp:
            z = amp.Centroid.Z
            if lowest_face is None or z < lowest_z:
                lowest_face = face
                lowest_z = z
    return lowest_face

def main():
    ids = rs.GetObjects("Select BREPs", rs.filter.surface | rs.filter.polysurface, preselect=True)
    if not ids:
        return

    total_area_model = 0.0
    for oid in ids:
        brep = rs.coercebrep(oid)
        if not brep:
            continue
        face = get_bottom_face(brep)
        if not face:
            continue
        amp = AreaMassProperties.Compute(face)
        if amp:
            total_area_model += amp.Area

    # Convert model-units area to square meters
    length_scale = Rhino.RhinoMath.UnitScale(sc.doc.ModelUnitSystem, Rhino.UnitSystem.Meters)
    total_area_m2 = round(total_area_model * (length_scale * length_scale), 2)

    rs.MessageBox(u"Total bottom-face area: {0:.2f} m²".format(total_area_m2), 0, "Total Bottom-Face Area")

if __name__ == "__main__":
    main()
