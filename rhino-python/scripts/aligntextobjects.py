# ================================================================================
# Script Name:     aligntextobjects.py
# Author:          Tom Dufficy
# Copyright:       Copyright (c) 2025 Tom Dufficy. All rights reserved.
# License:         MIT License (see LICENSE file for details)
# Version:         1.0.0
#
# Description:
#     Aligns selected Rhino text objects (TextEntity annotations) to a chosen
#     reference text object along either the X or Y axis. The script provides a
#     preview mechanism on a temporary layer, allowing the user to accept,
#     swap axis, or cancel before committing changes. Preview objects are placed
#     on a teal-coloured layer so they are visually distinct.
#
# Requirements:
#     Rhino 8
#     Not tested with other versions of Rhino
#
# Change Log:
#     1.0.0 - Initial release.
# ================================================================================

import rhinoscriptsyntax as rs

# -------------------------------------------------------------------------------
# Create or ensure preview layer, assign colour
# -------------------------------------------------------------------------------
def ensure_preview_layer(name="ALIGN_PREVIEW"):
    if not rs.IsLayer(name):
        rs.AddLayer(name, color=(77, 249, 255))  # teal RGB
    else:
        rs.LayerColor(name, (77, 249, 255))
    return name

# -------------------------------------------------------------------------------
# Move preview copies of text objects onto the preview layer
# -------------------------------------------------------------------------------
def show_preview(ref_id, target_ids, axis, layer):
    ref_pt = rs.TextObjectPoint(ref_id)
    if not ref_pt:
        return []

    preview_ids = []
    for tid in target_ids:
        base_pt = rs.TextObjectPoint(tid)
        if not base_pt:
            continue
        move_vec = [0,0,0]
        if axis == "X":
            move_vec[0] = ref_pt[0] - base_pt[0]
        else:
            move_vec[1] = ref_pt[1] - base_pt[1]
        pid = rs.CopyObject(tid, move_vec)
        if pid:
            rs.ObjectLayer(pid, layer)
            preview_ids.append(pid)
    return preview_ids

# -------------------------------------------------------------------------------
# Delete previews and optionally the preview layer
# -------------------------------------------------------------------------------
def clear_preview(preview_ids, layer):
    if preview_ids:
        rs.DeleteObjects(preview_ids)
    if rs.IsLayer(layer):
        objs = rs.ObjectsByLayer(layer)
        if not objs:
            rs.PurgeLayer(layer)

# -------------------------------------------------------------------------------
# Commit actual movement of target text objects
# -------------------------------------------------------------------------------
def commit_alignment(ref_id, target_ids, axis):
    ref_pt = rs.TextObjectPoint(ref_id)
    if not ref_pt:
        return

    for tid in target_ids:
        base_pt = rs.TextObjectPoint(tid)
        if not base_pt:
            continue
        move_vec = [0,0,0]
        if axis == "X":
            move_vec[0] = ref_pt[0] - base_pt[0]
        else:
            move_vec[1] = ref_pt[1] - base_pt[1]
        rs.MoveObject(tid, move_vec)

# -------------------------------------------------------------------------------
# Main execution
# -------------------------------------------------------------------------------
def main():
    # Select reference text
    ref_id = rs.GetObject("Select reference text object", rs.filter.annotation)
    if not ref_id:
        return

    # Select target texts
    target_ids = rs.GetObjects("Select text objects to align", rs.filter.annotation)
    if not target_ids:
        return

    # Ask for initial axis
    axis_choice = rs.GetString("Align on which axis?", "X", ["X","Y"])
    if axis_choice not in ["X","Y"]:
        return

    layer = ensure_preview_layer()
    preview_ids = show_preview(ref_id, target_ids, axis_choice, layer)

    while True:
        opt = rs.GetString("Preview shown. Accept / Swap / Cancel?", "Accept", ["Accept","Swap","Cancel"])
        if opt == "Accept":
            clear_preview(preview_ids, layer)
            commit_alignment(ref_id, target_ids, axis_choice)
            print("Alignment applied on {} axis.".format(axis_choice))
            break
        elif opt == "Swap":
            clear_preview(preview_ids, layer)
            axis_choice = "Y" if axis_choice == "X" else "X"
            layer = ensure_preview_layer()
            preview_ids = show_preview(ref_id, target_ids, axis_choice, layer)
        else:  # Cancel
            clear_preview(preview_ids, layer)
            print("Alignment cancelled.")
            break

if __name__ == "__main__":
    main()
