"""Symmetric, serviceable speaker lead exits. Dimensions in millimetres.

The user measured two adjacent insulated leads, each 1.8 mm in diameter.
The terminals are on either short end; assemble both drivers terminals-up.
Only bare lead ends pass through these openings, not connectors.
"""
import FreeCAD as App
import Part

V = App.Vector
EXIT_X, EXIT_Y = 59.0, 47.0
ROOF_INNER, ROOF_OUTER = 118.0, 120.5
WIRE_DIAMETER = 1.8
THROAT = (4.6, 2.8)
POCKET = (8.6, 6.8)
POCKET_DEPTH = .6


def capsule(x, y, z, width, height, depth):
    """XY capsule extruded along Z, with its long axis along X."""
    straight = width - height
    middle = Part.makeBox(straight, height, depth,
                          V(x-straight/2, y-height/2, z))
    ends = [Part.makeCylinder(height/2, depth, V(x+dx, y, z))
            for dx in (-straight/2, straight/2)]
    return middle.multiFuse(ends).removeSplitter()


def exit_tools(sign):
    x = sign * EXIT_X
    throat = capsule(x, EXIT_Y, ROOF_INNER-.1, *THROAT,
                     ROOF_OUTER-ROOF_INNER+.2)
    pocket = capsule(x, EXIT_Y, ROOF_OUTER-POCKET_DEPTH, *POCKET,
                     POCKET_DEPTH+.1)
    return throat, pocket
