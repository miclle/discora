"""Discora perfboard, carrier and connector geometry shared by the build and checks."""
import json
from pathlib import Path

import FreeCAD as App
import Part

V = App.Vector
LAYOUT = Path(__file__).resolve().parents[1] / "perfboard" / "layout.json"
BOARD_CORNER = (57, 20, 142.8)
BOARD_THICKNESS = 1.6
WIRING_DEPTH = 2
SERVICE_OPENING = 60
MOUNTS = (
    # World X, Y, screw length, and silkscreen hole.
    (-27.28, 23.00, 4, "G₂ / A"),
    (13.36, 56.02, 4, "Q / N"),
    (54.00, 61.10, 4, "A / P"),
)
CONNECTORS = {
    # Plugged envelope, local wire bend, and unplug/grip envelope.
    "Buttons": (
        (-48.90, 22.62, 144.4, 18, 16, 8),
        (-54.90, 22.62, 145.4, 6, 16, 7),
        (-58.90, 21.12, 144.9, 19, 19, 9),
    ),
    "OLED": (
        (-40.38, 41.86, 144.4, 13.5, 8, 11),
        (-40.38, 35.86, 155.4, 13.5, 14, 6),
        (-41.88, 40.36, 152.4, 16.5, 11, 17),
    ),
    "VolumeSwitch": (
        (-53.12, 41.86, 144.4, 8.5, 8, 11),
        (-53.12, 35.86, 155.4, 8.5, 14, 6),
        (-54.62, 40.36, 152.4, 11.5, 11, 17),
    ),
}


def box(x, y, z, width, depth, height):
    return Part.makeBox(width, depth, height, V(x, y, z))


def bore(x, y, z, radius, depth):
    return Part.makeCylinder(radius, depth, V(x, y, z))


def outline(z, height):
    return box(-43, 20, z, 100, 55, height).cut(
        box(40.25, 20, z-.1, 16.75, 32, height+.2)
    ).fuse(box(-54, 40.86, z, 11, 10, height)).removeSplitter()


def board_shape():
    blank = outline(BOARD_CORNER[2], BOARD_THICKNESS)
    holes = [bore(x, y, 142.7, 1.1, 1.8) for x, y, _, _ in MOUNTS]
    return blank.cut(Part.makeCompound(holes)).removeSplitter()


def carrier_sources():
    # Two cantilever seats clear the top of the amp and its plug allowances.
    # The rear rail is behind the amp, tying both upright ribs together.
    front_rib = box(-53, 20.5, 121.8, 4, 8, 21)
    left_rib = box(-53, 51.5, 121.8, 4, 11, 19)
    right_rib = box(49, 51.5, 121.8, 5, 11, 19)
    rear_rail = box(-53, 60, 136.8, 110, 5, 4)
    # Keep the sub-board copper above this front ledge clear of added wires.
    front_pad = bore(-27.28, 23, 140.2, 2.5, 2.6).fuse(
        box(-51, 20.5, 140.2, 23.72, 3.5, 2.6)
    )
    mid_pad = bore(13.36, 56.02, 140.2, 2.5, 2.6).fuse(
        box(10.86, 56.02, 140.2, 5, 5.98, 2.6)
    )
    rear_pad = bore(54, 61.1, 140.2, 2.5, 2.6)
    seats = front_pad.fuse(mid_pad).fuse(rear_pad)
    pilots = Part.makeCompound(
        [bore(x, y, 142.8-(length-1.6)-.25, .8, length-1.6+.35)
         for x, y, length, _ in MOUNTS]
    )
    # The left board extension bears on the upright rib without a screw hole.
    edge_pad = box(-51, 49, 140.2, 5, 6, 2.6)
    return {
        "PerfboardFrontRib": front_rib.cut(pilots),
        "PerfboardLeftRib": left_rib.cut(pilots),
        "PerfboardRightRib": right_rib.cut(pilots),
        "PerfboardRearRail": rear_rail.cut(pilots),
        "PerfboardSeats": seats.cut(pilots).removeSplitter(),
        "PerfboardEdgePad": edge_pad.cut(pilots),
    }


def wiring_under_board(carrier):
    blank = outline(142.8-WIRING_DEPTH, WIRING_DEPTH)
    return blank.cut(Part.makeCompound([carrier, *[
        bore(x, y, 140.7, 2.5, 2.2) for x, y, _, _ in MOUNTS
    ]])).removeSplitter()


def module_shapes():
    data = json.loads(LAYOUT.read_text())
    x, y, z = BOARD_CORNER
    z += BOARD_THICKNESS
    shapes = {}
    for part in data["parts"] + data["service_zones"]:
        name = part["id"]
        if name == "USBService":
            continue
        u, v = part["uv_mm"]
        width, depth = part["size_uv_mm"]
        front_left = (x-u-width, y+v)
        if name in ("MCU", "DAC"):
            shapes[name+"Sockets"] = box(*front_left, z, width, depth, 8.5)
            shapes[name] = box(*front_left, z+8.5, width, depth, 1.6)
            shapes[name+"Chip"] = box(*front_left, z+10.1, width, depth, 7)
        else:
            shapes[name] = box(*front_left, z, width, depth, part["above_board_mm"])
    return shapes


def screw_shape(x, y, length):
    top = BOARD_CORNER[2] + BOARD_THICKNESS
    return bore(x, y, top-length, .8, length).fuse(bore(x, y, top, 2.15, 1.55))

# Each service loop sits above the board and releases length as P1 travels
# forward. Endpoints at the controls are provisional wire exits. The small
# straight tails inside the supplied control housings are not included.
HARNESS_ROUTES = {
    "Buttons": (
        1.25, 68.5, (-71, -60, 160),
        [(-54.9, 30.62, 149), (-63, 30.62, 149), (-69, 32, 153), (-71, 35, 160)],
        [(-60, 39, 160), (-61, 43, 166), (-61, 44, 173), (-59, 42, 174)],
    ),
    "OLED": (
        1.2, 66.5, (-28, -14, 166),
        [(-33.63, 35.86, 158.4), (-32, 32, 159), (-29, 32.5, 165), (-28, 32.5, 166)],
        [(-14, 41, 166), (-10, 44, 169), (0, 44, 170.228), (0, 38.952, 170.228)],
    ),
    "VolumeSwitch": (
        1.0, 68, (-50, -39, 166),
        [(-48.87, 35.86, 158.4), (-50, 32, 158.5), (-51, 35, 163), (-50, 38, 166)],
        [(-39, 45, 166), (-35, 50, 166), (-33, 47, 173), (-25, 48, 174), (-9, 48, 174),
         (20, 48, 174), (38, 48, 174), (59, 48, 173), (60, 44, 169),
         (58, 42, 169), (56.5, 42, 169)],
    ),
}


def harness_segments(name, opening=0):
    """Build an envelope with a swept semicircle and straight routing segments."""
    radius, loop_y, (left, right, z), board_end, cover_end = HARNESS_ROUTES[name]
    loop_y -= opening / 2
    start, finish = V(left, loop_y, z), V(right, loop_y, z)
    bend_radius = (right-left) / 2
    crown = V((left+right)/2, loop_y+bend_radius, z)
    bend = Part.Wire([Part.Arc(start, crown, finish).toShape()])
    profile = Part.Wire([Part.makeCircle(radius, start, V(0, 1, 0))])
    loop = bend.makePipeShell([profile], True, False)
    before = [V(*point) for point in board_end] + [start]
    after = [finish] + [V(x, y-opening, z) for x, y, z in cover_end]
    segments = [loop]
    length = bend.Length
    for points in (before, after):
        for first, last in zip(points, points[1:]):
            axis = last-first
            if axis.Length > 1e-7:
                segments.append(Part.makeCylinder(radius, axis.Length, first, axis))
                length += axis.Length
        # Spherical joints close the routing envelope at corners without
        # implying a wire's attainable bend radius at the guide points.
        segments.extend(Part.makeSphere(radius, point) for point in points[1:-1])
    return segments, length


def harness_shape(name, opening=0):
    segments, _ = harness_segments(name, opening)
    return Part.makeCompound(segments)

FIXED_WIRE_ROUTES = {
    "DriveDataWire": (
        .9, [(-17.12, 24, 141.8), (-17.12, 20, 141.8), (-19, 15, 141.8),
             (-34, 13, 141.8), (-57, 13, 142), (-61, 19, 139), (-61, 52, 130),
             (-61, 68, 128), (-65, 71, 122), (-70, 71, 114), (-72, 72, 69),
             (-72, 72, 31), (-72, 71, 29), (-61, 70, 29.7), (65, 70, 29.7),
             (72, 72, 28), (72, 79, 20)],
    ),
    "DACAudioWire": (
        .9, [(51, 62, 158), (57, 62, 158), (64, 61, 154), (65, 57, 145),
             (61, 47, 135), (57, 43, 134), (48, 43, 134)],
    ),
}


def fixed_wire_shape(name):
    radius, points = FIXED_WIRE_ROUTES[name]
    points = [V(*point) for point in points]
    tubes = [Part.makeCylinder(radius, (last-first).Length, first, last-first)
             for first, last in zip(points, points[1:])]
    tubes.extend(Part.makeSphere(radius, point) for point in points[1:-1])
    return Part.makeCompound(tubes)
