"""Independent ducts with a short P3 mouth transition and trapezoid P2 outlets.

Dimensions describe a manufacturable layout, not a measured acoustic tuning.
All functions build the left side; the document mirrors it natively.
"""
import math
import FreeCAD as A
import Part

V = A.Vector
CENTER_X = -65.5
ELBOW_Z = 65.0
INLET_Z = 98.0
EXIT_X = -79.3


def prism(points, vector):
    wire = Part.makePolygon([V(*p) for p in points + [points[0]]])
    return Part.Face(wire).extrude(V(*vector))


def outlet_wire(x, offset=0):
    """Parallel offset of the 400 mm² house profile, in the YZ plane."""
    half = 10 + offset
    tip = 35 - offset * math.sqrt(2)
    profile = [(-half, 60 + offset), (half, 60 + offset),
               (half, tip + half), (0, tip), (-half, tip + half)]
    points = [V(x, y, ELBOW_Z + z) for z, y in profile]
    return Part.makePolygon(points + points[:1])


def outlet_prism(x, length, offset=0):
    return Part.Face(outlet_wire(x, offset)).extrude(V(length, 0, 0))


def rounded_outlet_wire(x, offset=0):
    """24 × 33 mm, R3 base profile; the outer lip adds 0.5 mm per side.

    The extended front end gives the inner house-to-rectangle transition
    enough slope for rear-down printing. Coordinates are (relative Z, Y).
    """
    half_z, half_y, radius = 12 + offset, 16.5 + offset, 3 + offset
    cy = 45.5
    a, b, r = half_z, half_y, radius
    points = [(-a+r, cy-b), (a-r, cy-b), (a, cy-b+r), (a, cy+b-r),
              (a-r, cy+b), (-a+r, cy+b), (-a, cy+b-r), (-a, cy-b+r)]
    centers = [(a-r, cy-b+r), (a-r, cy+b-r),
               (-a+r, cy+b-r), (-a+r, cy-b+r)]

    def vertex(point):
        return V(x, point[1], ELBOW_Z + point[0])

    edges = []
    for i, center in enumerate(centers):
        start, end, following = points[2*i], points[2*i+1], points[(2*i+2) % 8]
        edges.append(Part.makeLine(vertex(start), vertex(end)))
        direction = (end[0] + following[0] - 2*center[0],
                     end[1] + following[1] - 2*center[1])
        length = math.hypot(*direction)
        midpoint = (center[0] + direction[0]/length*r,
                    center[1] + direction[1]/length*r)
        edges.append(Part.Arc(vertex(end), vertex(midpoint), vertex(following)).toShape())
    return Part.Wire(edges)


def trapezoid_outlet_wire(x, offset=0):
    """Rounded, parallel-offset trapezoid; coordinates are (Y, relative Z).

    The inner profile contains the unchanged P3 throat plus its 1 mm
    clearance. The raked front edge closes progressively when rear-down.
    """
    vertices = [(24.75, -12.5), (62.5, -12.5), (62.5, 12.5), (37.25, 12.5)]
    normals = []
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        dy, dz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dy, dz)
        normals.append((dz / length, -dy / length))
    shifted = []
    for i, v in enumerate(vertices):
        a, b = normals[i-1], normals[i]
        det = a[0]*b[1] - a[1]*b[0]
        shifted.append((v[0] + offset*(b[1]-a[1])/det,
                        v[1] + offset*(a[0]-b[0])/det))
    corners = []
    radius = 4 + offset
    for i, v in enumerate(shifted):
        vectors = [(p[0]-v[0], p[1]-v[1])
                   for p in (shifted[i-1], shifted[(i+1) % 4])]
        u, w = [(a/math.hypot(a,b), b/math.hypot(a,b)) for a,b in vectors]
        angle = math.acos(u[0]*w[0] + u[1]*w[1])
        tangent = radius/math.tan(angle/2)
        entry = (v[0]+u[0]*tangent, v[1]+u[1]*tangent)
        leave = (v[0]+w[0]*tangent, v[1]+w[1]*tangent)
        bisector = (u[0]+w[0], u[1]+w[1])
        scale = radius/math.sin(angle/2)/math.hypot(*bisector)
        center = (v[0]+bisector[0]*scale, v[1]+bisector[1]*scale)
        length = math.hypot(v[0]-center[0], v[1]-center[1])
        middle = (center[0]+(v[0]-center[0])*radius/length,
                  center[1]+(v[1]-center[1])*radius/length)
        corners.append((entry, middle, leave))

    def point(p):
        return V(x, p[0], ELBOW_Z+p[1])

    edges = []
    for i, (entry, middle, leave) in enumerate(corners):
        edges.append(Part.Arc(point(entry), point(middle), point(leave)).toShape())
        edges.append(Part.makeLine(point(leave), point(corners[(i+1) % 4][0])))
    return Part.Wire(edges)


def left_panel_opening():
    return Part.Face(trapezoid_outlet_wire(-86, 2.7)).extrude(V(7, 0, 0))


def left_port():
    # Both ends use matching arcs/edges: one continuous shallow reveal,
    # without the previous rectangle-to-house silhouette inside P2.
    outside = Part.Face(trapezoid_outlet_wire(-85, 3)).extrude(V(5, 0, 0))
    throat = Part.makeLoft([trapezoid_outlet_wire(-86, 1.6),
                           trapezoid_outlet_wire(-85, 1.6),
                           trapezoid_outlet_wire(-80.15),
                           trapezoid_outlet_wire(-79.9)],
                          True, True)
    return outside.cut(throat).removeSplitter()


def vertical_wire(z, outside=False):
    t = min(1, max(0, (z - 55) / 43))
    tip, shoulder = 35 + 1.5 * t, 45 - 1.5 * t
    if outside:
        slope = (shoulder - tip) / 10
        tip -= 2.5 * math.sqrt(1 + slope * slope)
        points = [(-12.5, 62.5), (12.5, 62.5),
                  (12.5, tip + 12.5 * slope), (0, tip),
                  (-12.5, tip + 12.5 * slope)]
    else:
        points = [(-10, 60), (10, 60), (10, shoulder), (0, tip), (-10, shoulder)]
    vertices = [V(CENTER_X + x, y, z) for x, y in points]
    return Part.makePolygon(vertices + vertices[:1])


def terminal_mouth():
    """Last 4 mm of P3: house throat to a rounded trapezoid mouth.

    A 1.8 mm transverse rim fits inside the P2 profile. The solid collar
    extends 1.8 mm behind the flare root; the original rear bed plane stays
    at Y=62.5. The complete old air passage is retained by duct_shapes().
    """
    # Avoid coincident seam faces being misclassified by the Boolean kernel.
    # The 0.001 mm root allowance is confined to this local cutting tool.
    mouth = Part.makeLoft([outlet_wire(EXIT_X+4, .001),
                           trapezoid_outlet_wire(EXIT_X, -1.8),
                           trapezoid_outlet_wire(EXIT_X-1, -1.8)], True, True)
    collar = Part.Face(trapezoid_outlet_wire(EXIT_X)).extrude(V(5.8, 0, 0))
    return mouth, collar


def duct_shapes():
    # The 1.5 mm ridge rake closes the longitudinal roof progressively while
    # preserving 400 mm² at every section normal to the vertical leg.
    vertical = Part.makeLoft([vertical_wire(55), vertical_wire(INLET_Z)], True, True)
    horizontal = outlet_prism(-80, 14.5)
    lumen = vertical.fuse(horizontal).removeSplitter()
    envelope = Part.makeLoft([vertical_wire(52.5, True), vertical_wire(55, True),
                              vertical_wire(INLET_Z, True)], True, True)
    envelope = envelope.fuse(outlet_prism(EXIT_X, 13.8, 2.5)).removeSplitter()
    mouth, collar = terminal_mouth()
    lumen = lumen.fuse(mouth).removeSplitter()
    assert lumen.isValid() and len(lumen.Solids) == 1
    envelope = envelope.fuse(collar).removeSplitter()
    return lumen, envelope


def left_chamber(closed_chamber):
    lumen, envelope = duct_shapes()
    return closed_chamber.fuse(envelope).cut(lumen).removeSplitter()
