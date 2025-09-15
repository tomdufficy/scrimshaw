# -*- coding: utf-8 -*-
# ================================================================================
# Script Name:     scatterblocks.py
# Author:          Tom Dufficy
# Copyright:       Copyright (c) 2025 Tom Dufficy. All rights reserved.
# License:         MIT License (see LICENSE file for details)
# Version:         1.0.0
#
# Description:
#     Lets the user select a block instance or geometry, then scatter it
#     across a chosen surface or mesh with options for density, random
#     rotation, scaling, and alignment to surface/mesh normals. A preview
#     is shown and the user can accept, regenerate, or cancel. On acceptance,
#     the blocks are baked onto a new layer.
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
import random
import math


# ------------------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------------------

def _bb_center(obj_id):
    bb = rs.BoundingBox(obj_id)
    if not bb:
        return rs.WorldXYPlane().Origin
    x = sum([p.X for p in bb]) / 8.0
    y = sum([p.Y for p in bb]) / 8.0
    z = sum([p.Z for p in bb]) / 8.0
    return Rhino.Geometry.Point3d(x, y, z)


def _ensure_new_layer(base="ScatteredBlocks"):
    name = base
    i = 1
    while rs.IsLayer(name):
        name = "{}_{}".format(base, i)
        i += 1
    rs.AddLayer(name)
    return name


def _ask_yes_no_bool(prompt, default=False):
    result = rs.GetBoolean(prompt, ("Option", "No", "Yes"), (default,))
    if result is None:
        return None
    return bool(result[0])


def _delete_objects(ids):
    if ids:
        try:
            rs.DeleteObjects(ids)
        except:
            pass


# ------------------------------------------------------------------------------
# Sampling utilities
# ------------------------------------------------------------------------------

def _sample_on_surface(srf_id, n):
    out = []
    udom = rs.SurfaceDomain(srf_id, 0)
    vdom = rs.SurfaceDomain(srf_id, 1)
    for _ in range(n):
        u = random.uniform(udom[0], udom[1])
        v = random.uniform(udom[0], vdom[1])
        pt = rs.EvaluateSurface(srf_id, u, v)
        nrm = rs.SurfaceNormal(srf_id, (u, v))
        out.append((pt, nrm))
    return out


def _triangle_area(p0, p1, p2):
    v1 = p1 - p0
    v2 = p2 - p0
    cr = Rhino.Geometry.Vector3d.CrossProduct(v1, v2)
    return 0.5 * cr.Length


def _triangle_random_point(p0, p1, p2):
    r1 = random.random()
    r2 = random.random()
    s1 = math.sqrt(r1)
    u = 1.0 - s1
    v = r2 * s1
    w = 1.0 - u - v
    return Rhino.Geometry.Point3d(
        u * p0.X + v * p1.X + w * p2.X,
        u * p0.Y + v * p1.Y + w * p2.Y,
        u * p0.Z + v * p1.Z + w * p2.Z
    )


def _triangle_normal(p0, p1, p2):
    v1 = p1 - p0
    v2 = p2 - p0
    n = Rhino.Geometry.Vector3d.CrossProduct(v1, v2)
    if not n.IsZero:
        n.Unitize()
    return n


def _sample_on_mesh(mesh_id, n):
    mesh = rs.coercemesh(mesh_id)
    if mesh is None:
        return []

    mesh = mesh.DuplicateMesh()
    if mesh.Faces.QuadCount > 0:
        mesh.Faces.ConvertQuadsToTriangles()
        mesh.Normals.ComputeNormals()
        mesh.FaceNormals.ComputeFaceNormals()

    tris = []
    cum_areas = []
    total = 0.0

    for i in range(mesh.Faces.Count):
        a, b, c, d = mesh.Faces.GetFace(i)
        p0 = mesh.Vertices[a]
        p1 = mesh.Vertices[b]
        p2 = mesh.Vertices[c]
        area = _triangle_area(p0, p1, p2)
        if area <= 0:
            continue
        total += area
        cum_areas.append(total)
        tris.append((p0, p1, p2))

    if total <= 0 or not tris:
        cen = rs.MeshAreaCentroid(mesh_id)[0]
        nrm = Rhino.Geometry.Vector3d.ZAxis
        return [(cen, nrm) for _ in range(n)]

    out = []
    for _ in range(n):
        r = random.uniform(0.0, total)
        lo, hi = 0, len(cum_areas) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if r <= cum_areas[mid]:
                hi = mid
            else:
                lo = mid + 1
        p0, p1, p2 = tris[lo]
        pt = _triangle_random_point(p0, p1, p2)
        nrm = _triangle_normal(p0, p1, p2)
        out.append((pt, nrm))
    return out


# ------------------------------------------------------------------------------
# Preview helpers
# ------------------------------------------------------------------------------

def _add_preview_block(block_name, insert_pt):
    return rs.InsertBlock(block_name, insert_pt, (1, 1, 1), 0.0)


def _add_preview_geo_from_id(src_id, insert_pt):
    base = _bb_center(src_id)
    vec = insert_pt - base
    dup = rs.CopyObject(src_id)
    if not dup:
        return None
    rs.MoveObject(dup, vec)
    return dup


def _apply_xy_rotation(obj_id, center_pt, do_rotate):
    if not do_rotate:
        return
    ang = random.uniform(0.0, 360.0)
    rs.RotateObject(obj_id, center_pt, ang, None, copy=False)


def _apply_align_to_normal(obj_id, center_pt, normal, align):
    if not align or not normal:
        return
    z = Rhino.Geometry.Vector3d.ZAxis
    n = Rhino.Geometry.Vector3d(normal.X, normal.Y, normal.Z)
    if n.IsZero:
        return
    xform = Rhino.Geometry.Transform.Rotation(z, n, center_pt)
    rs.TransformObject(obj_id, xform, copy=False)


def _apply_uniform_scale(obj_id, center_pt, do_scale):
    if not do_scale:
        return
    s = random.uniform(0.8, 1.2)
    rs.ScaleObject(obj_id, center_pt, (s, s, s), copy=False)


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main():
    # Get source object (block instance or geometry)
    src = rs.GetObject("Select a block instance or geometry to scatter",
                       preselect=True, select=True)
    if not src:
        return

    block_name = None
    use_block = rs.IsBlockInstance(src)
    if use_block:
        block_name = rs.BlockInstanceName(src)

    # Get scatter target (surface or mesh)
    target = rs.GetObject("Select a surface or mesh to scatter onto",
                          filter=8 + 32)
    if not target:
        return

    is_surface = rs.IsSurface(target)
    is_mesh = rs.IsMesh(target)
    if not (is_surface or is_mesh):
        rs.MessageBox("Target must be a surface or mesh.")
        return

    # Scatter options
    align_to_normal = _ask_yes_no_bool("Align to target normal? (No = drop/project)", default=False)
    if align_to_normal is None:
        return

    rotate_random = _ask_yes_no_bool("Random XY rotation?", default=True)
    if rotate_random is None:
        return

    scale_random = _ask_yes_no_bool("Random uniform scale 0.8 to 1.2?", default=True)
    if scale_random is None:
        return

    density = rs.GetInteger("Density (0 = sparse, 10 = dense)", number=5, minimum=0, maximum=10)
    if density is None:
        return

    # Compute scatter count from area
    if is_surface:
        area_tuple = rs.SurfaceArea(target)
        area = area_tuple[0] if area_tuple else 0.0
    else:
        area_tuple = rs.MeshArea(target)
        area = area_tuple[0] if area_tuple else 0.0

    if area <= 0.0:
        rs.MessageBox("Target has zero area.")
        return

    num_points = max(1, int((area / 20.0) * (density / 10.0)))

    # Temporary preview layer
    preview_layer = "Scatter_PREVIEW"
    if not rs.IsLayer(preview_layer):
        rs.AddLayer(preview_layer)

    final_ids = []
    while True:
        # Generate samples
        if is_surface:
            samples = _sample_on_surface(target, num_points)
        else:
            samples = _sample_on_mesh(target, num_points)

        # Create preview objects
        preview_ids = []
        for pt, nrm in samples:
            p3d = pt if isinstance(pt, Rhino.Geometry.Point3d) else Rhino.Geometry.Point3d(*pt)
            if use_block:
                oid = _add_preview_block(block_name, p3d)
            else:
                oid = _add_preview_geo_from_id(src, p3d)
            if not oid:
                continue
            _apply_xy_rotation(oid, p3d, rotate_random)
            _apply_align_to_normal(oid, p3d, nrm, align_to_normal)
            _apply_uniform_scale(oid, p3d, scale_random)
            rs.ObjectLayer(oid, preview_layer)
            preview_ids.append(oid)

        rs.Redraw()

        # Confirm preview
        choice = rs.GetString("Preview OK? (Yes / No / Cancel)", "Yes",
                              ["Yes", "No", "Cancel"])
        if choice is None:
            _delete_objects(preview_ids)
            return

        if choice == "Yes":
            bake_layer = _ensure_new_layer("ScatteredBlocks")
            for oid in preview_ids:
                rs.ObjectLayer(oid, bake_layer)
            final_ids = preview_ids[:]
            break
        elif choice == "No":
            _delete_objects(preview_ids)
            continue
        else:
            _delete_objects(preview_ids)
            return

    if final_ids:
        # Remove preview layer
        if rs.IsLayer(preview_layer):
            try:
                rs.PurgeLayer(preview_layer)
            except:
                pass
        rs.Redraw()
        print("Baked {} objects.".format(len(final_ids)))


if __name__ == "__main__":
    main()
