"""Build a rigged, stylized 3D character wearing the event uniform.

Run with Blender's Python (bpy):
    python build_character.py            # builds, exports, renders previews

Outputs (in ../):
    character.blend   - editable Blender scene with armature
    character.glb     - rigged model for web / Unity / Unreal / After Effects plugins
    character.fbx     - rigged model for Maya / 3ds Max / Cinema 4D / Unity
    renders/*.png     - preview renders

The character faces -Y (Blender front view). Units are meters (~1.80 m tall).
"""
import math
import os
import sys

import bpy  # must be imported before bmesh / mathutils
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, ".."))
TEX = os.path.join(OUT, "textures")
RENDERS = os.path.join(OUT, "renders")
FAST = "--fast" in sys.argv

# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"

PARTS = []  # (object, weight_fn)


# ---------------------------------------------------------------- materials
def hex_rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


def material(name, color, rough=0.6, metal=0.0, sss=0.0, sheen=0.0, coat=0.0,
             transmission=0.0, alpha=1.0, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = hex_rgb(color)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Subsurface Weight"].default_value = sss
    if sss:
        bsdf.inputs["Subsurface Radius"].default_value = (0.9, 0.35, 0.2)
        bsdf.inputs["Subsurface Scale"].default_value = 0.01
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["Alpha"].default_value = alpha
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(TEX, image))
        tex.extension = "CLIP"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    if image or alpha < 1.0 or transmission:
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            pass
    return m


M = {
    "skin": material("Skin", "#D08E66", rough=0.5, sss=0.25),
    "skin_dark": material("Skin_Shadow", "#BD7C58", rough=0.55, sss=0.2),
    "stubble": material("Stubble", "#B98060", rough=0.8, sss=0.2),
    "hair": material("Hair", "#22170F", rough=0.55, sheen=0.4),
    "eye_white": material("Eye_White", "#F6F3EE", rough=0.15, coat=0.6),
    "iris": material("Iris", "#2E1C12", rough=0.1, coat=1.0),
    "lip": material("Lip", "#8A3A33", rough=0.4),
    "teeth": material("Teeth", "#F7F5EF", rough=0.3),
    "polo": material("Polo_Blue", "#1B2CB0", rough=0.85, sheen=0.5),
    "polo_dark": material("Polo_Placket", "#141F86", rough=0.85, sheen=0.4),
    "collar": material("Collar_White", "#E8EBF2", rough=0.8, sheen=0.3),
    "button": material("Button", "#F4F4F4", rough=0.3, coat=0.5),
    "pants": material("Pants_Beige", "#D3C6A9", rough=0.9, sheen=0.3),
    "pants_dark": material("Pants_Pocket", "#C3B594", rough=0.9, sheen=0.2),
    "cap": material("Cap_White", "#F4F5F7", rough=0.8, sheen=0.3),
    "cap_brim": material("Cap_Brim", "#E4E6EC", rough=0.75),
    "frame": material("Glasses_Frame", "#0E0E12", rough=0.35, coat=0.2),
    "lens": material("Glasses_Lens", "#FFFFFF", rough=0.03, transmission=1.0, alpha=0.25),
    "lanyard": material("Lanyard", "#16237A", rough=0.6, sheen=0.4),
    "clip": material("Badge_Clip", "#C9CCD2", rough=0.25, metal=1.0),
    "badge": material("Badge_Holder", "#DCE7F5", rough=0.05, transmission=0.9, alpha=0.35),
    "shoe": material("Shoe_Navy", "#1E2433", rough=0.6, sheen=0.1),
    "sole": material("Shoe_Sole", "#F2F2EF", rough=0.6),
    "dec_chest": material("Decal_ChestLogo", "#FFFFFF", rough=0.8, image="chest_logo.png"),
    "dec_cap": material("Decal_CapLogo", "#FFFFFF", rough=0.6, image="cap_logo.png"),
    "dec_pocket": material("Decal_PocketLogo", "#FFFFFF", rough=0.7, image="pocket_logo.png"),
    "dec_badge": material("Decal_BadgeCard", "#FFFFFF", rough=0.4, image="badge_card.png"),
}


# ---------------------------------------------------------------- geometry helpers
def new_obj(name, me, mat, smooth=True):
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    if isinstance(mat, list):
        for mm in mat:
            ob.data.materials.append(M[mm])
    else:
        ob.data.materials.append(M[mat])
    if smooth and hasattr(ob.data, "polygons"):
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def frame_for(axis, up=None):
    a = Vector(axis).normalized()
    if up is None:
        up = Vector((1, 0, 0)) if abs(a.x) < 0.9 else Vector((0, 1, 0))
    u = (Vector(up) - a * a.dot(up)).normalized()
    v = a.cross(u).normalized()
    return a, u, v


def lathe(name, mat, profile, origin=(0, 0, 0), axis=(0, 0, 1), sx=1.0, sy=1.0,
          n=32, up=None, subsurf=1, solidify=0.0):
    """Surface of revolution with elliptical cross-section.

    profile: list of (t, r) along `axis`; r == 0 at an end closes it with a pole.
    sx scales the cross-section along `up` (world X by default), sy along axis x up (world Y).
    """
    a, u, v = frame_for(axis, up)
    o = Vector(origin)
    bm = bmesh.new()
    rings = []
    for t, r in profile:
        c = o + a * t
        if r == 0:
            rings.append([bm.verts.new(c)])
        else:
            rings.append([bm.verts.new(c + u * (r * sx * math.cos(2 * math.pi * i / n))
                                       + v * (r * sy * math.sin(2 * math.pi * i / n)))
                          for i in range(n)])
    for r0, r1 in zip(rings, rings[1:]):
        if len(r0) == 1:
            for i in range(n):
                bm.faces.new((r0[0], r1[i], r1[(i + 1) % n]))
        elif len(r1) == 1:
            for i in range(n):
                bm.faces.new((r0[(i + 1) % n], r0[i], r1[0]))
        else:
            for i in range(n):
                bm.faces.new((r0[i], r1[i], r1[(i + 1) % n], r0[(i + 1) % n]))
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = new_obj(name, me, mat)
    if solidify:
        md = ob.modifiers.new("solid", "SOLIDIFY")
        md.thickness = solidify
        md.offset = 0
    if subsurf:
        md = ob.modifiers.new("subd", "SUBSURF")
        md.levels = md.render_levels = subsurf
    return ob


def ellipsoid(name, mat, center, radii, rot=(0, 0, 0), seg=32, subsurf=1):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=1,
                                         location=center, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = radii
    ob.data.materials.append(M[mat])
    for p in ob.data.polygons:
        p.use_smooth = True
    if subsurf:
        md = ob.modifiers.new("subd", "SUBSURF")
        md.levels = md.render_levels = subsurf
    return ob


def rounded_box(name, mat, center, half, rot=(0, 0, 0), level=2, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=2, location=center, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = half
    ob.data.materials.append(M[mat])
    for p in ob.data.polygons:
        p.use_smooth = True
    if bevel:
        md = ob.modifiers.new("bev", "BEVEL")
        md.width = bevel
        md.segments = 3
    if level:
        md = ob.modifiers.new("subd", "SUBSURF")
        md.levels = md.render_levels = level
    return ob


def capsule(name, mat, p0, p1, r0, r1=None, n=16):
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    prof = [(-r0, 0), (-r0 * 0.7, r0 * 0.71), (0, r0), (L, r1), (L + r1 * 0.7, r1 * 0.71), (L + r1, 0)]
    return lathe(name, mat, prof, origin=p0, axis=p1 - p0, n=n, subsurf=1)


def tube(name, mat, pts, radius, radii=None, res=12):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1)
        sp.points[i].radius = radii[i] if radii else 1.0
    sp.use_endpoint_u = True
    sp.order_u = 3
    sp.resolution_u = res
    ob = bpy.data.objects.new(name, cu)
    scene.collection.objects.link(ob)
    ob.data.materials.append(M[mat])
    return ob


def decal(name, mat, center, size, normal, target=None, offset=0.0015, up=(0, 0, 1)):
    """Image plane facing `normal`, optionally shrink-wrapped onto `target`."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=12, y_subdivisions=12, size=1, location=(0, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    nz = Vector(normal).normalized()
    ux = Vector(up).cross(nz).normalized()
    uy = nz.cross(ux)
    ob.matrix_world = Matrix.Translation(center) @ Matrix((ux, uy, nz)).transposed().to_4x4()
    ob.data.materials.append(M[mat])
    if target is not None:
        md = ob.modifiers.new("wrap", "SHRINKWRAP")
        md.target = target
        md.wrap_method = "NEAREST_SURFACEPOINT"
        md.wrap_mode = "OUTSIDE_SURFACE"
        md.offset = offset
    return ob


def bake(ob):
    """Apply all modifiers / convert curves, returning a mesh object."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    name = ob.name
    mw = ob.matrix_world.copy()
    mats = [s.material for s in ob.material_slots]
    bpy.data.objects.remove(ob)
    nob = bpy.data.objects.new(name, me)
    nob.matrix_world = mw
    scene.collection.objects.link(nob)
    if not me.materials:
        for m in mats:
            me.materials.append(m)
    return nob


def part(ob, weights):
    PARTS.append((ob, weights))
    return ob


# ---------------------------------------------------------------- body landmarks
HEAD_Z0 = 1.50
HEAD_PROFILE = [(0.0, 0.0), (0.012, 0.045), (0.035, 0.080), (0.07, 0.108), (0.115, 0.124),
                (0.17, 0.132), (0.225, 0.128), (0.27, 0.110), (0.305, 0.075), (0.325, 0.035), (0.333, 0.0)]
HEAD_SY = 1.10
TORSO_Z0 = 0.88
TORSO_PROFILE = [(0.0, 0.192), (0.10, 0.196), (0.22, 0.190), (0.34, 0.196), (0.43, 0.206),
                 (0.48, 0.204), (0.515, 0.180), (0.545, 0.120), (0.565, 0.068)]
TORSO_SY = 0.66


def radius_at(profile, z0, z):
    t = z - z0
    for (t0, r0), (t1, r1) in zip(profile, profile[1:]):
        if t0 <= t <= t1:
            return r0 + (r1 - r0) * (t - t0) / (t1 - t0)
    return 0.0


def head_y(x, z, push=0.0):
    r = radius_at(HEAD_PROFILE, HEAD_Z0, z)
    return -HEAD_SY * math.sqrt(max(r * r - x * x, 0)) - push


def torso_y(x, z, push=0.0):
    r = radius_at(TORSO_PROFILE, TORSO_Z0, z)
    return -TORSO_SY * math.sqrt(max(r * r - x * x, 0)) - push


SHOULDER = {+1: Vector((0.172, 0, 1.365)), -1: Vector((-0.172, 0, 1.365))}
ARM_ANGLE = math.radians(17)


def arm_dir(s):
    return Vector((s * math.sin(ARM_ANGLE), 0, -math.cos(ARM_ANGLE)))


UPPER_LEN, FORE_LEN, HAND_LEN = 0.285, 0.255, 0.17
HIP = {+1: Vector((0.095, 0, 0.90)), -1: Vector((-0.095, 0, 0.90))}
KNEE = {+1: Vector((0.102, -0.01, 0.50)), -1: Vector((-0.102, -0.01, 0.50))}
ANKLE = {+1: Vector((0.11, 0, 0.10)), -1: Vector((-0.11, 0, 0.10))}
TOE = {+1: Vector((0.115, -0.15, 0.03)), -1: Vector((-0.115, -0.15, 0.03))}


def arm_joints(s):
    sh = SHOULDER[s]
    el = sh + arm_dir(s) * UPPER_LEN
    wr = el + arm_dir(s) * FORE_LEN
    tip = wr + arm_dir(s) * HAND_LEN
    return sh, el, wr, tip


# ---------------------------------------------------------------- weight functions
def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def chain_weights(bones, joints, blend=0.04):
    """Weights along a polyline of joints: bones[i] spans joints[i]..joints[i+1]."""
    joints = [Vector(j) for j in joints]
    seg_len = [(b - a).length for a, b in zip(joints, joints[1:])]
    cum = [0.0]
    for L in seg_len:
        cum.append(cum[-1] + L)

    def fn(co):
        best, best_s = None, 0.0
        for i, (a, b) in enumerate(zip(joints, joints[1:])):
            ab = b - a
            t = max(0.0, min(1.0, (co - a).dot(ab) / ab.length_squared))
            d = (a + ab * t - co).length
            if best is None or d < best:
                best, best_s = d, cum[i] + t * seg_len[i]
        w = {}
        for i, b in enumerate(bones):
            lo = 1.0 if i == 0 else smoothstep((best_s - cum[i] + blend) / (2 * blend))
            hi = 1.0 if i == len(bones) - 1 else 1.0 - smoothstep((best_s - cum[i + 1] + blend) / (2 * blend))
            val = lo * hi
            if val > 1e-3:
                w[b] = val
        return w
    return fn


def rigid(bone):
    fn = lambda co: {bone: 1.0}  # noqa: E731
    fn.bone = bone
    return fn


SPINE = chain_weights(["hips", "spine", "chest"], [(0, 0, 0.80), (0, 0, 1.05), (0, 0, 1.20), (0, 0, 1.45)], 0.06)


def arm_weights(s):
    side = "L" if s > 0 else "R"
    sh, el, wr, tip = arm_joints(s)
    return chain_weights(["chest", f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}"],
                         [sh - arm_dir(s) * 0.08 + Vector((-s * 0.05, 0, 0)), sh, el, wr, tip], 0.035)


def leg_weights(s):
    side = "L" if s > 0 else "R"
    return chain_weights(["hips", f"thigh.{side}", f"shin.{side}", f"foot.{side}"],
                         [Vector((HIP[s].x * 0.4, 0, 1.0)), HIP[s], KNEE[s], ANKLE[s], TOE[s]], 0.045)


# ================================================================ HEAD
head = lathe("Head", ["skin", "stubble"], HEAD_PROFILE, origin=(0, 0, HEAD_Z0), sy=HEAD_SY, n=40, subsurf=0)
# stubble on jaw, chin and around the mouth
for poly in head.data.polygons:
    c = poly.center
    if c.z < 1.605 and c.y < 0.0 and not (c.z > 1.60 and abs(c.x) < 0.03 and c.y < -0.12):
        poly.material_index = 1
sd = head.modifiers.new("subd", "SUBSURF")
sd.levels = sd.render_levels = 2
part(head, rigid("head"))

for s in (1, -1):
    part(ellipsoid(f"Ear.{s}", "skin_dark", (s * 0.128, 0.008, 1.665), (0.014, 0.026, 0.036),
                   rot=(0, s * math.radians(-12), 0)), rigid("head"))
part(ellipsoid("Nose", "skin", (0, head_y(0, 1.645, -0.006), 1.645), (0.020, 0.024, 0.027)), rigid("head"))
part(ellipsoid("NoseTip", "skin", (0, head_y(0, 1.632, 0.008), 1.632), (0.016, 0.014, 0.013)), rigid("head"))

# hair shell: back and sides of the head, visible under the cap
hair = lathe("Hair", "hair", [(0.15, 0.133), (0.18, 0.138), (0.22, 0.136), (0.26, 0.120), (0.29, 0.09)],
             origin=(0, 0, HEAD_Z0), sx=1.0, sy=HEAD_SY * 1.03, n=40, subsurf=0)
bm = bmesh.new()
bm.from_mesh(hair.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.02], context="FACES")
bm.to_mesh(hair.data)
bm.free()
hm = hair.modifiers.new("solid", "SOLIDIFY")
hm.thickness = 0.008
hm2 = hair.modifiers.new("subd", "SUBSURF")
hm2.levels = hm2.render_levels = 2
part(hair, rigid("head"))
for s in (1, -1):
    part(rounded_box(f"Sideburn.{s}", "hair", (s * 0.124, -0.045, 1.675), (0.008, 0.012, 0.022), level=2), rigid("head"))

# eyes
EYE_Z = 1.688
for s in (1, -1):
    ex = s * 0.047
    ey = head_y(ex, EYE_Z, -0.012)
    part(ellipsoid(f"EyeWhite.{s}", "eye_white", (ex, ey, EYE_Z), (0.021, 0.014, 0.019)), rigid("head"))
    part(ellipsoid(f"Iris.{s}", "iris", (ex - s * 0.002, ey - 0.0115, EYE_Z), (0.0115, 0.005, 0.0125)), rigid("head"))
    part(ellipsoid(f"EyeSpark.{s}", "eye_white", (ex + 0.004 - s * 0.002, ey - 0.0165, EYE_Z + 0.005),
                   (0.0028, 0.0012, 0.0028), seg=12, subsurf=0), rigid("head"))
    # upper eyelid
    part(ellipsoid(f"Eyelid.{s}", "skin", (ex, ey + 0.001, EYE_Z + 0.008), (0.023, 0.0145, 0.012)), rigid("head"))
    # eyebrows
    xs = [s * x for x in (0.020, 0.040, 0.062, 0.082)]
    zs = [1.727, 1.735, 1.736, 1.729]
    pts = [(x, head_y(x, z, 0.005), z) for x, z in zip(xs, zs)]
    part(bake(tube(f"Brow.{s}", "hair", pts, 0.0065, radii=[1.25, 1.2, 1.0, 0.65])), rigid("head"))

# mustache
mx = [-0.050, -0.032, -0.012, 0.0, 0.012, 0.032, 0.050]
mz = [1.598, 1.609, 1.616, 1.614, 1.616, 1.609, 1.598]
mr = [0.45, 1.0, 1.25, 1.1, 1.25, 1.0, 0.45]
part(bake(tube("Mustache", "hair", [(x, head_y(x, z, 0.006), z) for x, z in zip(mx, mz)], 0.0085, radii=mr)),
     rigid("head"))
# smile
sx_ = [-0.034, -0.018, 0.0, 0.018, 0.034]
sz_ = [1.589, 1.581, 1.578, 1.581, 1.589]
part(bake(tube("Mouth", "lip", [(x, head_y(x, z, 0.001), z) for x, z in zip(sx_, sz_)], 0.0055,
               radii=[0.5, 1.0, 1.1, 1.0, 0.5])), rigid("head"))
part(bake(tube("Teeth", "teeth", [(x, head_y(x, z + 0.004, 0.0035), z + 0.004)
                                   for x, z in zip(sx_[1:-1], sz_[1:-1])], 0.0032)), rigid("head"))

# glasses
GZ = 1.690
for s in (1, -1):
    gx = s * 0.052
    gy = head_y(gx, GZ, 0.030)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.034, minor_radius=0.0052, major_segments=48,
                                     minor_segments=12, location=(gx, gy, GZ), rotation=(math.pi / 2, 0, 0))
    fr = bpy.context.active_object
    fr.name = f"GlassesFrame.{s}"
    fr.scale = (1.18, 0.86, 1.0)
    fr.data.materials.append(M["frame"])
    for p in fr.data.polygons:
        p.use_smooth = True
    part(fr, rigid("head"))
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.034, depth=0.0016, location=(gx, gy, GZ),
                                        rotation=(math.pi / 2, 0, 0))
    ln = bpy.context.active_object
    ln.name = f"GlassesLens.{s}"
    ln.scale = (1.18, 0.86, 1.0)
    ln.data.materials.append(M["lens"])
    part(ln, rigid("head"))
    tx = s * 0.092
    part(capsule(f"GlassesTemple.{s}", "frame", (tx, gy + 0.004, GZ + 0.012),
                 (s * 0.130, 0.010, GZ + 0.004), 0.0045), rigid("head"))
part(bake(tube("GlassesBridge", "frame",
               [(-0.014, head_y(0.014, GZ, 0.028), GZ + 0.012), (0, head_y(0, GZ, 0.030), GZ + 0.017),
                (0.014, head_y(0.014, GZ, 0.028), GZ + 0.012)], 0.0045)), rigid("head"))

# cap
cap = lathe("CapCrown", "cap", [(0.0, 0.145), (0.03, 0.146), (0.065, 0.136), (0.095, 0.114),
                                (0.12, 0.080), (0.135, 0.040), (0.14, 0.0)],
            origin=(0, 0.004, 1.725), sy=1.10, n=48, subsurf=2, solidify=0.004)
part(cap, rigid("head"))
for ang in (-50, 0, 50, 180):  # crown seams / panel stitching
    a = math.radians(ang)
    pts = []
    for t in (0.0, 0.05, 0.09, 0.12, 0.137):
        r = radius_at([(0.0, 0.145), (0.03, 0.146), (0.065, 0.136), (0.095, 0.114), (0.12, 0.080),
                       (0.135, 0.040), (0.14, 0.0)], 0.0, t) + 0.0025
        pts.append((r * math.sin(a), 0.004 - 1.10 * r * math.cos(a), 1.725 + t))
    part(bake(tube(f"CapSeam.{ang}", "cap_brim", pts, 0.0016)), rigid("head"))
part(ellipsoid("CapButton", "cap", (0, 0.004, 1.866), (0.012, 0.012, 0.006)), rigid("head"))

bm = bmesh.new()
outer = []
n_b = 24
for i in range(n_b + 1):
    th = math.pi * i / n_b
    x = 0.148 * math.cos(th)
    y = -0.06 - 0.17 * math.sin(th) ** 0.85
    outer.append((x, y))
inner = [(0.140 * math.cos(math.pi * i / n_b), -0.10 * math.sin(math.pi * i / n_b) - 0.06) for i in range(n_b + 1)]
vo = [bm.verts.new((x, y, 0)) for x, y in outer]
vi = [bm.verts.new((x, y, 0)) for x, y in inner]
for i in range(n_b):
    bm.faces.new((vi[i], vi[i + 1], vo[i + 1], vo[i]))
for v in bm.verts:  # curve the brim down at the sides and tilt it slightly
    v.co.z = 1.731 - 0.55 * (v.co.x ** 2) + 0.10 * (v.co.y + 0.06)
bm.normal_update()
me = bpy.data.meshes.new("CapBrim")
bm.to_mesh(me)
bm.free()
brim = new_obj("CapBrim", me, "cap_brim")
bs = brim.modifiers.new("solid", "SOLIDIFY")
bs.thickness = 0.010
bs.offset = 0
bsub = brim.modifiers.new("subd", "SUBSURF")
bsub.levels = bsub.render_levels = 2
part(brim, rigid("head"))
part(decal("CapLogo", "dec_cap", Vector((0, -0.22, 1.785)), (0.066, 0.066), (0, -1, 0.45), target=cap, offset=0.0045),
     rigid("head"))

# ================================================================ NECK & TORSO
part(lathe("Neck", "skin", [(0, 0.056), (0.08, 0.054), (0.14, 0.055)], origin=(0, 0.008, 1.40),
           sy=1.0, subsurf=1), chain_weights(["chest", "neck", "head"], [(0, 0, 1.38), (0, 0, 1.43), (0, 0, 1.49),
                                                                     (0, 0, 1.6)], 0.025))
torso = lathe("PoloBody", "polo", TORSO_PROFILE, origin=(0, 0, TORSO_Z0), sy=TORSO_SY, n=48, subsurf=2, solidify=0.006)
part(torso, SPINE)

# collar band and flaps
part(lathe("CollarBand", "collar", [(0, 0.088), (0.022, 0.074), (0.04, 0.066)], origin=(0, 0.004, 1.405),
           sy=0.92, n=40, subsurf=2, solidify=0.004), rigid("chest"))
for s in (1, -1):
    bm = bmesh.new()
    pts = [(s * 0.014, 1.405), (s * 0.075, 1.428), (s * 0.066, 1.392), (s * 0.044, 1.352)]
    vs = [bm.verts.new((x, torso_y(x, z, 0.012) if z < 1.42 else torso_y(min(abs(x), 0.06), 1.415, 0.012), z))
          for x, z in pts]
    bm.faces.new(vs if s < 0 else vs[::-1])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
    me = bpy.data.meshes.new(f"CollarFlap.{s}")
    bm.to_mesh(me)
    bm.free()
    fl = new_obj(f"CollarFlap.{s}", me, "collar")
    fs = fl.modifiers.new("solid", "SOLIDIFY")
    fs.thickness = 0.005
    fsub = fl.modifiers.new("subd", "SUBSURF")
    fsub.levels = fsub.render_levels = 2
    part(fl, rigid("chest"))
part(rounded_box("Undershirt", "collar", (0, torso_y(0, 1.395, -0.002), 1.395), (0.022, 0.004, 0.018), level=1),
     rigid("chest"))
part(rounded_box("Placket", "polo_dark", (0, torso_y(0, 1.33, 0.003), 1.33), (0.016, 0.003, 0.058),
                 level=2, bevel=0.002), rigid("chest"))
for bz in (1.365, 1.305):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.0065, depth=0.003,
                                        location=(0, torso_y(0, bz, 0.007), bz), rotation=(math.pi / 2, 0, 0))
    b = bpy.context.active_object
    b.name = f"Button.{bz}"
    b.data.materials.append(M["button"])
    part(b, rigid("chest"))
part(decal("ChestLogo", "dec_chest", Vector((0.105, torso_y(0.105, 1.30, 0.02), 1.30)), (0.075, 0.075),
           (0.35, -1, 0), target=torso, offset=0.0045), rigid("chest"))

# lanyard and badge
BADGE = Vector((0.085, torso_y(0.085, 1.10, 0.020), 1.10))
for s in (1, -1):
    xs_ = [s * 0.07, s * 0.075 + 0.02, 0.04 + s * 0.035, BADGE.x + s * 0.012]
    zs_ = [1.415, 1.33, 1.22, 1.165]
    pts = [(x, torso_y(x, z, 0.009) if z < 1.40 else torso_y(min(abs(x), 0.07), 1.40, 0.02), z)
           for x, z in zip(xs_, zs_)]
    pts.insert(0, (s * 0.068, 0.02, 1.43))
    pts.insert(1, (s * 0.074, -0.05, 1.432))
    part(bake(tube(f"Lanyard.{s}", "lanyard", pts, 0.0055)), rigid("chest"))
part(rounded_box("BadgeClip", "clip", BADGE + Vector((0, -0.002, 0.058)), (0.010, 0.004, 0.009), level=1,
                 bevel=0.002), rigid("chest"))
part(rounded_box("BadgeHolder", "badge", BADGE, (0.037, 0.0035, 0.050), level=1, bevel=0.003), rigid("chest"))
part(decal("BadgeCard", "dec_badge", BADGE + Vector((0, -0.0005, -0.002)), (0.064, 0.085), (0, -1, 0)),
     rigid("chest"))

# ================================================================ ARMS
for s in (1, -1):
    side = "L" if s > 0 else "R"
    sh, el, wr, tip = arm_joints(s)
    d = arm_dir(s)
    W = arm_weights(s)
    up = Vector((0, 1, 0))
    part(lathe(f"Sleeve.{side}", "polo", [(-0.05, 0.0), (-0.035, 0.058), (-0.01, 0.074), (0.08, 0.074),
                                          (0.17, 0.069), (0.195, 0.070)],
               origin=sh, axis=d, sx=0.96, sy=1.0, up=up, n=32, subsurf=2, solidify=0.005), W)
    part(lathe(f"SleeveHem.{side}", "polo_dark", [(0.180, 0.0705), (0.196, 0.0715)],
               origin=sh, axis=d, sx=0.96, up=up, n=32, subsurf=1, solidify=0.006), W)
    L = UPPER_LEN + FORE_LEN
    part(lathe(f"Arm.{side}", "skin", [(0.0, 0.0), (0.01, 0.040), (0.12, 0.047), (0.25, 0.041),
                                       (UPPER_LEN, 0.042), (UPPER_LEN + 0.06, 0.043), (L - 0.07, 0.034),
                                       (L, 0.028), (L + 0.03, 0.027), (L + 0.045, 0.0)],
               origin=sh, axis=d, sx=1.0, sy=0.85, up=up, n=24, subsurf=1), W)
    # hand: palm faces the body, fingers point down the arm
    side_axis = Vector((-s * math.cos(ARM_ANGLE), 0, -s * math.sin(ARM_ANGLE)))  # toward the body
    palm_c = wr + d * 0.055
    palm = ellipsoid(f"Palm.{side}", "skin", palm_c, (0.020, 0.040, 0.050), seg=24)
    palm.rotation_euler = (0, s * ARM_ANGLE, 0)
    part(palm, W)
    for i, (fy, flen) in enumerate([(-0.026, 0.060), (-0.009, 0.068), (0.009, 0.064), (0.025, 0.052)]):
        base = wr + d * 0.095 + Vector((0, fy, 0)) + side_axis * 0.004
        mid = base + d * flen * 0.55 + side_axis * 0.006
        end = mid + d * flen * 0.45 + side_axis * 0.012
        part(capsule(f"Finger{i}a.{side}", "skin", base, mid, 0.0095, 0.0088), W)
        part(capsule(f"Finger{i}b.{side}", "skin", mid, end, 0.0088, 0.0078), W)
    tb = wr + d * 0.03 + Vector((0, -0.030, 0)) + side_axis * 0.010
    tm = tb + d * 0.030 + Vector((0, -0.012, 0)) + side_axis * 0.012
    te = tm + d * 0.028 + side_axis * 0.006
    part(capsule(f"Thumb_a.{side}", "skin", tb, tm, 0.0115, 0.0100), W)
    part(capsule(f"Thumb_b.{side}", "skin", tm, te, 0.0100, 0.0088), W)

# ================================================================ LEGS / PANTS
part(lathe("PantsHips", "pants", [(0.0, 0.180), (0.08, 0.186), (0.15, 0.188), (0.20, 0.17), (0.215, 0.0)],
           origin=(0, 0, 0.80), sy=0.62, n=40, subsurf=2), rigid("hips"))
for s in (1, -1):
    side = "L" if s > 0 else "R"
    W = leg_weights(s)
    top = HIP[s] + Vector((0, 0, 0.02))
    axis = ANKLE[s] - top
    Lg = axis.length
    part(lathe(f"PantLeg.{side}", "pants", [(-0.02, 0.0), (-0.005, 0.088), (0.10, 0.092), (0.25, 0.082),
                                            (0.42, 0.071), (0.60, 0.066), (Lg - 0.04, 0.066), (Lg - 0.02, 0.067)],
               origin=top, axis=axis, sy=0.95, n=32, subsurf=2, solidify=0.004), W)
    part(lathe(f"Ankle.{side}", "skin", [(0, 0.034), (0.08, 0.032)], origin=ANKLE[s] + Vector((0, 0, -0.03)),
               n=16, subsurf=1), W)
    # knee crease hint
    part(bake(tube(f"KneeFold.{side}", "pants_dark",
                   [(KNEE[s].x + dx, -0.075, KNEE[s].z + dz) for dx, dz in ((-0.035, 0.03), (0, 0.04), (0.035, 0.03))],
                   0.0025)), W)

    # loafers
    shoe_c = Vector((ANKLE[s].x, -0.045, 0.058))
    part(rounded_box(f"ShoeUpper.{side}", "shoe", shoe_c, (0.066, 0.150, 0.056), level=3), W)
    part(rounded_box(f"ShoeSole.{side}", "sole", shoe_c + Vector((0, -0.002, -0.044)), (0.070, 0.156, 0.018),
                     level=2), W)
    part(ellipsoid(f"ShoeOpening.{side}", "hair", shoe_c + Vector((0, 0.04, 0.043)), (0.040, 0.055, 0.006),
                   seg=24), W)
    part(bake(tube(f"ShoeApron.{side}", "sole",
                   [(shoe_c.x - 0.035, shoe_c.y - 0.06, 0.098), (shoe_c.x, shoe_c.y - 0.10, 0.093),
                    (shoe_c.x + 0.035, shoe_c.y - 0.06, 0.098)], 0.0022)), W)

# cargo pocket on the character's right thigh (viewer's left, -X)
PK = Vector((-0.192, -0.005, 0.64))
for name, c, half, mat in (("CargoPocket", PK, (0.014, 0.068, 0.085), "pants_dark"),
                           ("CargoFlap", PK + Vector((-0.006, 0, 0.080)), (0.012, 0.072, 0.024), "pants")):
    ob = rounded_box(name, mat, c, half, rot=(0, math.radians(-4), 0), level=2, bevel=0.004)
    part(ob, leg_weights(-1))
part(ellipsoid("CargoButton", "pants_dark", PK + Vector((-0.020, 0, 0.074)), (0.003, 0.008, 0.008), seg=16),
     leg_weights(-1))
part(decal("PocketLogo", "dec_pocket", PK + Vector((-0.0155, 0, -0.012)), (0.07, 0.07), (-1, 0, 0)),
     leg_weights(-1))

# ================================================================ ARMATURE
arm_data = bpy.data.armatures.new("Rig")
rig = bpy.data.objects.new("Rig", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones


def bone(name, head, tail, parent=None, connect=False, roll=0.0):
    b = eb.new(name)
    b.head, b.tail, b.roll = Vector(head), Vector(tail), roll
    if parent:
        b.parent = eb[parent]
        b.use_connect = connect
    return b


bone("root", (0, 0, 0), (0, 0.25, 0))
bone("hips", (0, 0, 0.92), (0, 0, 1.05), "root")
bone("spine", (0, 0, 1.05), (0, 0, 1.20), "hips", True)
bone("chest", (0, 0, 1.20), (0, 0, 1.40), "spine", True)
bone("neck", (0, 0, 1.40), (0, 0, 1.49), "chest", True)
bone("head", (0, 0, 1.49), (0, 0, 1.88), "neck", True)
for s in (1, -1):
    side = "L" if s > 0 else "R"
    sh, el, wr, tip = arm_joints(s)
    bone(f"upper_arm.{side}", sh, el, "chest")
    bone(f"forearm.{side}", el, wr, f"upper_arm.{side}", True)
    bone(f"hand.{side}", wr, tip, f"forearm.{side}", True)
    bone(f"thigh.{side}", HIP[s], KNEE[s], "hips")
    bone(f"shin.{side}", KNEE[s], ANKLE[s], f"thigh.{side}", True)
    bone(f"foot.{side}", ANKLE[s], TOE[s], f"shin.{side}", True)
bpy.ops.object.mode_set(mode="OBJECT")

# ================================================================ BAKE, WEIGHT, JOIN
HEAD_PIVOT = Vector((0, 0, 1.50))
HEAD_XFORM = (Matrix.Translation(HEAD_PIVOT + Vector((0, 0, -0.035))) @ Matrix.Scale(1.12, 4)
              @ Matrix.Translation(-HEAD_PIVOT))
objs = []
for ob, wfn in PARTS:
    if ob.name not in scene.objects:
        continue
    ob = bake(ob) if (ob.modifiers or ob.type != "MESH") else ob
    if getattr(wfn, "bone", None) == "head":
        ob.matrix_world = HEAD_XFORM @ ob.matrix_world
    mw = ob.matrix_world.copy()
    ob.data.transform(mw)
    ob.matrix_world = Matrix.Identity(4)
    groups = {}
    for v in ob.data.vertices:
        for bname, w in wfn(v.co).items():
            if bname not in groups:
                groups[bname] = ob.vertex_groups.new(name=bname)
            groups[bname].add([v.index], w, "REPLACE")
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name="UVMap")
    else:
        ob.data.uv_layers[0].name = "UVMap"
    objs.append(ob)

bpy.ops.object.select_all(action="DESELECT")
for ob in objs:
    ob.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
body = bpy.context.active_object
body.name = "Character"
body.data.name = "Character"
bpy.ops.object.shade_smooth()
# remove duplicate material slots created by joining
bpy.ops.object.material_slot_remove_unused()

body.parent = rig
md = body.modifiers.new("Armature", "ARMATURE")
md.object = rig
print("vertices:", len(body.data.vertices), "faces:", len(body.data.polygons))

# ================================================================ SAVE & EXPORT
os.makedirs(RENDERS, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "character.blend"))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "character.glb"), export_format="GLB",
                          use_selection=False, export_skins=True, export_apply=False)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "character.fbx"), use_selection=False,
                         object_types={"ARMATURE", "MESH"}, add_leaf_bones=False, path_mode="COPY",
                         embed_textures=True, bake_anim=False)

# ================================================================ RENDER PREVIEWS
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24 if FAST else 128
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = (600, 800) if FAST else (1200, 1600)
scene.render.film_transparent = True
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Punchy"
scene.view_settings.exposure = -0.35

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.80, 0.9, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35


def light(name, kind, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 1.1)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(lo)


light("Key", "AREA", (-1.8, -2.6, 2.6), 450, 2.0, (1.0, 0.96, 0.9))
light("Fill", "AREA", (2.4, -2.0, 1.4), 160, 2.5, (0.85, 0.9, 1.0))
light("Rim", "AREA", (0.8, 2.6, 2.4), 320, 1.5)

bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "ShadowCatcher"
ground.is_shadow_catcher = True

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 60
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def shoot(fname, loc, target=(0, 0, 0.93)):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(RENDERS, fname)
    bpy.ops.render.render(write_still=True)
    print("rendered", fname)


shoot("front.png", (0, -4.6, 1.0))
shoot("three_quarter.png", (2.6, -3.8, 1.25))
shoot("face_closeup.png", (0.35, -1.25, 1.70), target=(0, 0, 1.68))

# posed test: wave + head turn + step, proves the rig deforms correctly
pb = rig.pose.bones
for b in pb:
    b.rotation_mode = "XYZ"


def best_rotation(bname, probe, angle, score):
    """Pick the local axis/sign whose rotation maximises score(probe bone tail)."""
    best = None
    for ax in range(3):
        for sign in (1, -1):
            e = [0.0, 0.0, 0.0]
            e[ax] = sign * angle
            pb[bname].rotation_euler = e
            bpy.context.view_layer.update()
            val = score(rig.matrix_world @ pb[probe].tail)
            if best is None or val > best[0]:
                best = (val, tuple(e))
    pb[bname].rotation_euler = best[1]
    bpy.context.view_layer.update()


best_rotation("upper_arm.L", "upper_arm.L", math.radians(125), lambda p: p.z + 0.3 * p.x)
best_rotation("forearm.L", "forearm.L", math.radians(40), lambda p: p.z - 0.5 * abs(p.x - 0.30))
best_rotation("head", "head", math.radians(10), lambda p: p.x)
best_rotation("thigh.R", "thigh.R", math.radians(14), lambda p: -p.y)
best_rotation("shin.R", "shin.R", math.radians(22), lambda p: p.y)
shoot("pose_wave.png", (1.9, -4.2, 1.2))
