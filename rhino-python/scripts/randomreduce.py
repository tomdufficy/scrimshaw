# -*- coding: utf-8 -*-
# ================================================================================
# Script Name:     randomreduce.py
# Author:          Tom Dufficy
# Copyright:       Copyright (c) 2025 Tom Dufficy. All rights reserved.
# License:         MIT License (see LICENSE file for details)
# Version:         1.0.0
#
# Description:
#     Lets the user select multiple objects, choose a percentage (20/40/60/80),
#     and randomly deletes approximately that percentage of the selection.
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


def main():
    # Get objects (preselection supported)
    ids = rs.GetObjects("Select objects to randomly delete a percentage of",
                        preselect=True)
    if not ids:
        return

    # Choose deletion percentage from fixed options
    options = ["20%", "40%", "60%", "80%"]
    choice = rs.ListBox(options, "Choose percentage to delete", "Random Reduce")
    if not choice:
        return

    pct = int(choice.rstrip("%")) / 100.0

    total = len(ids)
    n_delete = int(round(total * pct))
    if n_delete <= 0:
        rs.MessageBox(
            "Nothing to delete at {} of {} objects.".format(choice, total),
            0, "Random Reduce"
        )
        return
    if n_delete > total:
        n_delete = total

    to_delete = random.sample(ids, n_delete)

    # Wrap in a single undo record and suspend redraw for performance
    undo_id = sc.doc.BeginUndoRecord("Random percentage delete")
    try:
        rs.EnableRedraw(False)
        rs.DeleteObjects(to_delete)
    finally:
        rs.EnableRedraw(True)
        sc.doc.EndUndoRecord(undo_id)

    kept = total - n_delete
    # Summarize outcome
    rs.MessageBox(
        "Deleted {} of {} objects (~{}%). {} kept.".format(
            n_delete, total, int(round(100.0 * n_delete / float(total))), kept
        ),
        0, "Random Reduce"
    )


if __name__ == "__main__":
    main()
