"""Rear charging sockets: user-measured envelopes, glue sleeves and open bores."""
import FreeCAD as A
import Part

V = A.Vector
Y = V(0, 1, 0)
DC_X, DC_Z = -70.0, 12.0
USB_X, USB_Z = -70.0, 24.0
CENTERS_XZ = ((DC_X, DC_Z), (USB_X, USB_Z))
REAR_Y, INNER_Y = 93.0, 88.0
DC_DIAMETER, DC_LENGTH = 10.4, 31.5
USB_WIDTH, USB_HEIGHT, USB_LENGTH = 10.9, 5.3, 15.9
FIT_GAP = 0.2  # per side; physical PLA fit and adhesive thickness not verified
SLEEVE_WIDTH, SLEEVE_DEPTH = 14.8, 5.0
USB_SLEEVE_HEIGHT = 9.7  # 2 mm above and below the rectangular bore
SUPPORT_LENGTH = REAR_Y-INNER_Y+SLEEVE_DEPTH  # 10 mm including the rear wall
WIRE_LENGTH = 8.0  # design reservation, not a measured bend radius


def box(x, y, z, width, depth, height):
    return Part.makeBox(width, depth, height, V(x, y, z))


def bores():
    start = INNER_Y-SLEEVE_DEPTH-.1
    depth = REAR_Y-start+.1
    return Part.makeCompound([
        Part.makeCylinder(DC_DIAMETER/2+FIT_GAP, depth, V(DC_X, start, DC_Z), Y),
        box(USB_X-USB_WIDTH/2-FIT_GAP, start, USB_Z-USB_HEIGHT/2-FIT_GAP,
            USB_WIDTH+2*FIT_GAP, depth, USB_HEIGHT+2*FIT_GAP),
    ])


def sleeve_blanks():
    # User-selected front-left lower corner: USB above DC.
    # The two local sleeves are the documented exception to shell symmetry.
    # Overlap the rear wall by 1 mm; rear-wall-down printing needs no roof.
    return Part.makeCompound([
        Part.makeCylinder(SLEEVE_WIDTH/2, SLEEVE_DEPTH+1,
                          V(DC_X, INNER_Y-SLEEVE_DEPTH, DC_Z), Y),
        box(USB_X-SLEEVE_WIDTH/2, INNER_Y-SLEEVE_DEPTH, USB_Z-USB_SLEEVE_HEIGHT/2,
            SLEEVE_WIDTH, SLEEVE_DEPTH+1, USB_SLEEVE_HEIGHT),
    ])


def apply(rear):
    return rear.multiFuse(sleeve_blanks().Solids).cut(bores()).removeSplitter()


def socket_shapes():
    # Connector faces flush with Y=93; lengths include the 5 mm rear wall.
    # Solid keepouts describe housings, not electrical pin/socket internals.
    return {
        'DCChargeSocket': Part.makeCylinder(DC_DIAMETER/2, DC_LENGTH,
                                            V(DC_X, REAR_Y-DC_LENGTH, DC_Z), Y),
        'USBChargeSocket': box(USB_X-USB_WIDTH/2, REAR_Y-USB_LENGTH, USB_Z-USB_HEIGHT/2,
                              USB_WIDTH, USB_LENGTH, USB_HEIGHT),
    }


def wire_shapes():
    return {
        'DCChargeLead': box(DC_X-DC_DIAMETER/2, REAR_Y-DC_LENGTH-WIRE_LENGTH,
                            DC_Z-DC_DIAMETER/2, DC_DIAMETER, WIRE_LENGTH, DC_DIAMETER),
        'USBChargeLead': box(USB_X-USB_WIDTH/2, REAR_Y-USB_LENGTH-WIRE_LENGTH,
                             USB_Z-USB_HEIGHT/2, USB_WIDTH, WIRE_LENGTH, USB_HEIGHT),
    }
