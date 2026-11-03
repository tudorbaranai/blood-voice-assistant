"""Blood · the God Hand, built and rendered in Blender (4.2+ / 5.x).

Units: 1 = the sun's radius (R). The eclipse sits at the origin in the plane
Y = 0; the camera looks along +Y from Y = -cam_dist. The palm hangs BEHIND the
sun (Y > 0) and the fingers fold forward through the sun's plane, so:
  - the BACK pass renders the whole hand (the page draws the black disc over it),
  - the FRONT pass adds a camera-only holdout plane at Y = 0 and keeps exactly
    what lies nearer than the sun (the folded fingers and thumb).
The page composites: back layer -> black disc -> corona -> front layer.

Poses are a pure function of one number, curl (0 = open, 1 = fist), with the
same per-finger delays as the page's own choreography (d-eclipse.js), so the
page picks a frame from its curl value and never needs a clock.

Inside Blender:
    import hand_scene as hs
    hs.build(); hs.load_hand(); hs.pose(0.0)
    hs.render_pose_tests()          # open / half / fist / fist-front stills
    hs.render_sweep()               # every curl level, back + front, + meta.json
"""
import json
import math
import os

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # docs/design/manga-v3
CONFIG_PATH = os.path.join(HERE, "hand_config.json")
SCENE_NAME = "BloodHand"
POSE_NAMES = ["pinky", "ring", "middle", "index"]  # left -> right on screen (right hand, palm to us)


def cfg():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def hexcol(h, alpha=None):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4   # sRGB -> linear
    out = (lin(r), lin(g), lin(b))
    return out + (alpha,) if alpha is not None else out


def smooth(a, b, x):
    """The page's I.smooth: 0 below a, 1 above b, smoothstep between."""
    if b == a:
        return 0.0 if x < a else 1.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def ease(c):
    return c * c * (3 - 2 * c)


# ---------------------------------------------------------------- choreography
def finger_curls(curl, pose_cfg):
    """How far each finger (pinky, ring, middle, index) and the thumb have folded.
    1:1 with handGeom() in d-eclipse.js."""
    d = pose_cfg["delays"]
    span = pose_cfg["span"]
    fcs = {n: smooth(d[n], d[n] + span, curl) for n in POSE_NAMES}
    tc = smooth(pose_cfg["thumb_from"], pose_cfg["thumb_to"], curl)
    return fcs, tc


# ---------------------------------------------------------------- the scene
def scene():
    return bpy.data.scenes.get(SCENE_NAME)


def _set_engine(sc, name):
    try:
        sc.render.engine = name
        return True
    except TypeError as e:
        print("engine", name, "not available:", e)
        return False


def _gpu():
    try:
        cp = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("CUDA", "OPTIX"):      # OptiX kernels fail to compile on this driver; CUDA is safe
            try:
                cp.compute_device_type = kind
                cp.get_devices()
                on = [d for d in cp.devices if d.type == kind]
                if on:
                    for d in cp.devices:
                        d.use = d.type in (kind, "CPU")
                    print("cycles device:", kind, [d.name for d in on])
                    return True
            except TypeError:
                continue
    except Exception as e:
        print("gpu prefs:", e)
    return False


def _new_material(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m


def _skin_material(look):
    m = _new_material("GodHandSkin")
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    for n in list(nodes):
        nodes.remove(n)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    mix = nodes.new("ShaderNodeMixShader")
    mix.location = (380, 0)
    mix.inputs[0].default_value = look.get("translucent_mix", 0.18)
    p = nodes.new("ShaderNodeBsdfPrincipled")
    p.location = (0, 120)
    p.inputs["Base Color"].default_value = hexcol(look["skin"], 1)
    p.inputs["Roughness"].default_value = look["roughness"]
    p.inputs["Subsurface Weight"].default_value = look["sss_weight"]
    p.inputs["Subsurface Radius"].default_value = tuple(look["sss_radius"])
    p.inputs["Subsurface Scale"].default_value = look["sss_scale"]
    if "Specular IOR Level" in p.inputs:
        p.inputs["Specular IOR Level"].default_value = 0.25
    if "Sheen Weight" in p.inputs:
        p.inputs["Sheen Weight"].default_value = 0.12
        p.inputs["Sheen Tint"].default_value = hexcol("#ff6a3a", 1)
    try:
        p.subsurface_method = "RANDOM_WALK"
    except Exception:
        pass
    tr = nodes.new("ShaderNodeBsdfTranslucent")
    tr.location = (0, -200)
    tr.inputs["Color"].default_value = hexcol(look["sss_color"], 1)
    # skin grain: a fine noise bump (ancient and cracked rather than glossy)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-600, 0)
    noise.inputs["Scale"].default_value = look.get("grain_scale", 9.0)
    noise.inputs["Detail"].default_value = 9.0
    noise.inputs["Roughness"].default_value = 0.62
    bump = nodes.new("ShaderNodeBump")
    bump.location = (-300, 0)
    bump.inputs["Strength"].default_value = look.get("grain_strength", 0.3)
    bump.inputs["Distance"].default_value = 0.04
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    D = look.get("detail")
    last = bump
    if D:
        uv = nodes.new("ShaderNodeTexCoord")
        uv.location = (-1300, -200)
        # UV space when the mesh has a map, else object space (scales multiplied to match)
        use_uv = D.get("coords", "auto") == "uv" or (D.get("coords", "auto") == "auto" and any(
            o.type == "MESH" and o.data.uv_layers for o in scene().objects if o.name not in ("SunRing", "SunPlaneHoldout", "FrontMask", "SunBall")))
        coord_out = uv.outputs["UV"] if use_uv else uv.outputs["Object"]
        k = 1.0 if use_uv else D.get("object_scale_factor", 5.0)
        print("skin detail coords:", "UV" if use_uv else "Object")
        pores = nodes.new("ShaderNodeTexNoise")
        pores.location = (-1000, -100)
        pores.inputs["Scale"].default_value = D.get("pores_scale", 70) * k
        pores.inputs["Detail"].default_value = 4.0
        cracks = nodes.new("ShaderNodeTexVoronoi")
        cracks.location = (-1000, -350)
        cracks.feature = "DISTANCE_TO_EDGE"
        cracks.inputs["Scale"].default_value = D.get("cracks_scale", 28) * k
        wave = nodes.new("ShaderNodeTexWave")
        wave.location = (-1000, -600)
        wave.inputs["Scale"].default_value = D.get("wave_scale", 16) * k
        wave.inputs["Distortion"].default_value = D.get("wave_distortion", 5.0)
        wave.inputs["Detail"].default_value = 3.0
        for t in (pores, cracks, wave):
            links.new(coord_out, t.inputs["Vector"])
        inv = nodes.new("ShaderNodeMath")            # cracks: dark where the cell edge is near
        inv.location = (-750, -350)
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        links.new(cracks.outputs["Distance"], inv.inputs[1])
        pw = nodes.new("ShaderNodeMath")
        pw.location = (-600, -350)
        pw.operation = "POWER"
        pw.inputs[1].default_value = D.get("crack_power", 6.0)
        links.new(inv.outputs[0], pw.inputs[0])
        mixa = nodes.new("ShaderNodeMath")
        mixa.location = (-450, -200)
        mixa.operation = "MULTIPLY_ADD"
        Wt = D.get("weights", {"pores": 0.35, "cracks": 1.0, "wave": 0.25})
        crk = nodes.new("ShaderNodeMath")
        crk.location = (-450, -450)
        crk.operation = "MULTIPLY"
        crk.inputs[1].default_value = Wt["cracks"]
        links.new(pw.outputs[0], crk.inputs[0])
        mixa.inputs[1].default_value = Wt["pores"]
        links.new(pores.outputs["Fac"], mixa.inputs[0])
        links.new(crk.outputs[0], mixa.inputs[2])
        mixb = nodes.new("ShaderNodeMath")
        mixb.location = (-300, -300)
        mixb.operation = "MULTIPLY_ADD"
        mixb.inputs[1].default_value = Wt["wave"]
        links.new(wave.outputs["Fac"], mixb.inputs[0])
        links.new(mixa.outputs[0], mixb.inputs[2])
        bump2 = nodes.new("ShaderNodeBump")
        bump2.location = (-150, -100)
        bump2.inputs["Strength"].default_value = D.get("strength", 0.5)
        bump2.inputs["Distance"].default_value = 0.02
        links.new(mixb.outputs[0], bump2.inputs["Height"])
        links.new(bump.outputs["Normal"], bump2.inputs["Normal"])
        last = bump2
    links.new(last.outputs["Normal"], p.inputs["Normal"])
    links.new(last.outputs["Normal"], tr.inputs["Normal"])
    links.new(p.outputs[0], mix.inputs[1])
    links.new(tr.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def _emission_material(name, color, strength):
    m = _new_material(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hexcol(color, 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def _ray_vis(obj, camera=True, light=True):
    obj.visible_camera = camera
    for k in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter", "visible_shadow"):
        setattr(obj, k, light)


def build():
    """A fresh scene with everything but the hand."""
    C = cfg()
    F, L = C["frame"], C["look"]
    old = scene()
    if old:
        bpy.data.scenes.remove(old)
    sc = bpy.data.scenes.new(SCENE_NAME)
    bpy.context.window.scene = sc
    col = sc.collection

    # --- render settings
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.render.image_settings.compression = 60
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.use_persistent_data = True
    sc.frame_start = sc.frame_end = 1
    if _set_engine(sc, "CYCLES"):
        cy = sc.cycles
        cy.device = "GPU" if _gpu() else "CPU"
        cy.samples = L["samples"]
        cy.use_adaptive_sampling = True
        cy.adaptive_threshold = 0.02
        cy.use_denoising = True
        try:
            cy.denoiser = "OPENIMAGEDENOISE"
        except TypeError:
            pass
        cy.max_bounces = 6
        cy.diffuse_bounces = 3
        cy.glossy_bounces = 2
        cy.transmission_bounces = 4
        cy.caustics_reflective = cy.caustics_refractive = False
        cy.film_exposure = 1.0

    # --- world: a breath of dark crimson
    w = bpy.data.worlds.get("GodHandWorld") or bpy.data.worlds.new("GodHandWorld")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = hexcol(L["world"]["color"], 1)
    bg.inputs["Strength"].default_value = L["world"]["strength"]
    sc.world = w

    setup_camera(sc)

    # --- the sun: a ring of fire at the origin, in the plane Y = 0, unseen by the camera
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=L["ring"]["minor_r"], major_segments=128,
                                     minor_segments=16, location=(0, 0, 0), rotation=(math.pi / 2, 0, 0))
    ring = bpy.context.active_object
    ring.name = "SunRing"
    ring.data.materials.append(_emission_material("SunRingEmit", L["ring"]["color"], L["ring"]["strength"]))
    _ray_vis(ring, camera=False, light=True)
    ring.visible_shadow = False

    # --- lights, world, ring, skin: all from the config
    _skin_material(L)
    apply_look(sc)

    # --- the holdout at the sun's plane: only camera rays see it (front pass only)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0), rotation=(math.pi / 2, 0, 0))
    hold = bpy.context.active_object
    hold.name = "SunPlaneHoldout"
    hold.is_holdout = True
    _ray_vis(hold, camera=True, light=False)
    hold.hide_render = True
    hold.hide_viewport = True

    _front_mask(sc)

    # --- the hand's root: palm centre behind the sun
    root = bpy.data.objects.new("HandRoot", None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 1.0
    root.location = (0, C["hand"]["palm_depth_r"], 0)
    col.objects.link(root)

    _skin_material(L)
    print(f"scene {SCENE_NAME} built; sun at px {sun_pixels()}")
    return sc


def _front_mask(sc):
    """A camera-only holdout wall in front of everything, below the wrist line: the front
    pass keeps only the hand (the forearm's bulge may cross the sun's plane)."""
    C = cfg()
    D = C["frame"]["cam_dist_r"]
    ym = 3.0
    z_top = C["hand"].get("front_mask_z_r", -1.9) * (D - ym) / D
    old = bpy.data.objects.get("FrontMask")
    if old:
        bpy.data.objects.remove(old)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, -ym, z_top - 200), rotation=(math.pi / 2, 0, 0))
    m = bpy.context.active_object
    m.name = "FrontMask"
    m.is_holdout = True
    _ray_vis(m, camera=True, light=False)
    m.hide_render = True
    m.hide_viewport = True
    return m


def setup_camera(sc=None):
    """Resolution and camera from the config: optical axis through the sun, the frame shifted
    down to hold the arm; 1 unit = 1 sun radius = px_per_r pixels at the sun's plane."""
    C = cfg()
    F = C["frame"]
    sc = sc or scene()
    W = int(round(F["w_r"] * F["px_per_r"]))
    H = int(round(F["h_r"] * F["px_per_r"]))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    D = F["cam_dist_r"]
    cam = bpy.data.objects.get("HandCam")
    if cam is None:
        cam = bpy.data.objects.new("HandCam", bpy.data.cameras.new("HandCam"))
        sc.collection.objects.link(cam)
    cam_d = cam.data
    cam_d.sensor_fit = "VERTICAL"
    cam_d.sensor_height = 36.0
    cam_d.lens = 36.0 * D / F["h_r"]
    cam_d.shift_x = 0.0
    cam_d.shift_y = (F["sun_from_top_r"] - F["h_r"] / 2) / F["h_r"]
    cam_d.clip_start, cam_d.clip_end = 0.1, D * 4
    cam.location = (0, -D, 0)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.camera = cam
    print(f"camera: {W}x{H}, lens {cam_d.lens:.2f} mm, shift_y {cam_d.shift_y:.4f}, sun at px {sun_pixels()}")
    return cam


def apply_look(sc=None):
    """Re-create the lights, the world, the ring and the skin from the config (iterate without rebuilding)."""
    C = cfg()
    L = C["look"]
    sc = sc or scene()
    col = sc.collection
    for o in list(sc.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    for ld in [d for d in bpy.data.lights if d.users == 0]:
        bpy.data.lights.remove(ld)
    aim_at = (0, C["hand"]["palm_depth_r"], -0.5)

    def area(name, pos, aim, color, energy, size):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.color, ld.size = energy, hexcol(color), size
        ld.spread = math.radians(110)
        lo = bpy.data.objects.new(name, ld)
        lo.location = pos
        col.objects.link(lo)
        _aim(lo, aim)
        return lo
    for i, pos in enumerate(L["rim"]["pos"]):
        area(f"Rim{i}", pos, aim_at, L["rim"]["color"], L["rim"]["energy"], L["rim"]["size"])
    area("LavaFill", L["fill"]["pos"], (0, C["hand"]["palm_depth_r"], -3), L["fill"]["color"], L["fill"]["energy"], L["fill"]["size"])
    for X in L.get("extra_lights", []):
        area(X["name"], X["pos"], X.get("aim", aim_at), X["color"], X["energy"], X["size"])
    w = sc.world
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = hexcol(L["world"]["color"], 1)
    bg.inputs["Strength"].default_value = L["world"]["strength"]
    em = next(n for n in bpy.data.materials["SunRingEmit"].node_tree.nodes if n.type == "EMISSION")
    em.inputs["Color"].default_value = hexcol(L["ring"]["color"], 1)
    em.inputs["Strength"].default_value = L["ring"]["strength"]
    mat = _skin_material(L)
    for o in sc.objects:
        if o.type in ("MESH", "META") and o.name not in ("SunRing", "SunPlaneHoldout", "FrontMask"):
            o.data.materials.clear()
            o.data.materials.append(mat)
    if hasattr(sc, "cycles"):
        sc.cycles.samples = L["samples"]
    print("look applied:", [o.name for o in sc.objects if o.type == "LIGHT"])


def sun_pixels():
    """Where the sun's centre and its radius land in the render, measured from the camera."""
    from bpy_extras.object_utils import world_to_camera_view as w2c
    sc = scene()
    W, H = sc.render.resolution_x, sc.render.resolution_y
    c = w2c(sc, sc.camera, Vector((0, 0, 0)))
    e = w2c(sc, sc.camera, Vector((1, 0, 0)))
    return {"x": c.x * W, "y": (1 - c.y) * H, "r": (e.x - c.x) * W}


# ---------------------------------------------------------------- the stand-in hand (metaballs)
_STIFF = 10.0
_K = 0.78        # visible radius / element radius at stiffness 10, threshold 0.6


def _mb_clear():
    mb = bpy.data.metaballs.get("GodHandMB")
    if mb:
        mb.elements.clear()
    return mb


def _mb_capsule(mb, a, b, r):
    a, b = Vector(a), Vector(b)
    d = b - a
    el = mb.elements.new()
    el.type = "CAPSULE"
    el.co = (a + b) / 2
    el.size_x = max(0.001, d.length / 2)
    el.radius = r / _K
    el.stiffness = _STIFF
    el.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized()) if d.length > 1e-6 else Quaternion()
    return el


def _mb_ball(mb, p, r):
    el = mb.elements.new()
    el.type = "BALL"
    el.co = p
    el.radius = r / _K
    el.stiffness = _STIFF
    return el


def _mb_ellipsoid(mb, p, half, rot=None):
    el = mb.elements.new()
    el.type = "ELLIPSOID"
    el.co = p
    el.size_x, el.size_y, el.size_z = half
    el.radius = 1.0 / _K
    el.stiffness = _STIFF
    if rot is not None:
        el.rotation = rot
    return el


def _finger_chain(base, lengths, splay, flex):
    """Forward kinematics in hand space: fingers point +Z, flex folds them toward -Y (the camera)."""
    pts = [Vector(base)]
    rot = Quaternion((0, 1, 0), math.radians(splay))
    for L, a in zip(lengths, flex):
        rot = rot @ Quaternion((1, 0, 0), math.radians(a))
        pts.append(pts[-1] + rot @ Vector((0, 0, L)))
    return pts


def _slerp_dir(a, b, t):
    a, b = Vector(a).normalized(), Vector(b).normalized()
    q = a.rotation_difference(b)
    return (Quaternion().slerp(q, t) @ a).normalized()


def load_standin():
    C = cfg()
    sc = scene()
    mb = bpy.data.metaballs.get("GodHandMB") or bpy.data.metaballs.new("GodHandMB")
    mb.resolution = 0.12
    mb.render_resolution = C["hand"].get("mb_resolution", 0.035)
    mb.threshold = 0.6
    obj = bpy.data.objects.get("GodHand")
    if not obj:
        obj = bpy.data.objects.new("GodHand", mb)
        sc.collection.objects.link(obj)
    obj.parent = bpy.data.objects["HandRoot"]
    obj.matrix_parent_inverse.identity()
    obj.location = (0, 0, 0)
    mb.materials.clear()
    mb.materials.append(bpy.data.materials["GodHandSkin"])
    return obj


def pose_standin(curl):
    C = cfg()
    Hc, P = C["hand"], C["pose"]
    fcs, tc = finger_curls(curl, P)
    mb = _mb_clear()
    kz = Hc["knuckle_z_r"]
    pw, pl, pt = Hc["palm_w_r"], Hc["palm_len_r"], Hc["palm_thick_r"]

    # the palm: a slab with the heel swelling at the thumb's root and at the pinky's side
    _mb_ellipsoid(mb, (0, 0.05, kz - pl * 0.5 + 0.1), (pw * 0.46, pt * 0.42, pl * 0.42))
    _mb_ellipsoid(mb, (pw * 0.33, 0.0, kz - pl * 0.72), (pw * 0.2, pt * 0.5, pl * 0.26))      # thenar
    _mb_ellipsoid(mb, (-pw * 0.36, 0.02, kz - pl * 0.66), (pw * 0.15, pt * 0.46, pl * 0.26))  # hypothenar
    # the fingers
    sign = {"index": 1, "middle": 0.35, "ring": -0.35, "pinky": -1}
    for name in POSE_NAMES:
        f = Hc["fingers"][name]
        c = ease(fcs[name])
        splay = P["splay_open"] * sign[name] * (1 - c)
        flex = [P["mcp"] * c, P["pip"] * c, P["dip"] * c]
        pts = _finger_chain((f["x"], 0, kz), f["len"], splay, flex)
        r = f["rad"]
        rads = [r, r * 0.95, r * 0.86]
        for i in range(3):
            _mb_capsule(mb, pts[i], pts[i + 1], rads[i])
            _mb_ball(mb, pts[i], rads[i] * 1.14)          # knuckles
        _mb_ball(mb, pts[3], rads[2] * 0.98)
    # the thumb: three segments whose directions swing from the open to the fist pose
    T = Hc["thumb"]
    o, f_ = T["open_dirs"], T["fist_dirs"]
    p = Vector(T["base"])
    r = T["rad"]
    for i in range(3):
        d = _slerp_dir(o[i], f_[i], ease(tc))
        q = p + d * T["len"][i]
        _mb_capsule(mb, p, q, r * (1 - 0.1 * i))
        _mb_ball(mb, p, r * (1.12 - 0.08 * i))
        p = q
    _mb_ball(mb, p, r * 0.8)
    # wrist and forearm, down out of the frame
    A = Hc["forearm"]
    wz = kz - pl
    zs = [wz + 0.3, wz - 0.8, wz - 2.2, A["bottom_z_r"]]
    rs = [A["wrist_rad"] * 0.98, A["wrist_rad"], (A["wrist_rad"] + A["elbow_rad"]) / 2, A["elbow_rad"]]
    for i in range(3):
        _mb_capsule(mb, (0, 0.05, zs[i]), (0, 0.05, zs[i + 1]), (rs[i] + rs[i + 1]) / 2)
    _mb_ellipsoid(mb, (0, 0.05, wz - 0.1), (pw * 0.33, pt * 0.5, 0.5))   # the wrist, flattened
    return mb


# ---------------------------------------------------------------- a rigged hand (glb / fbx)
def load_rig():
    """Import the model named in the config and parent its armature to HandRoot."""
    C = cfg()
    path = os.path.join(HERE, C["model"]["path"])
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise ValueError("unsupported model: " + path)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    if not arm:
        raise RuntimeError("no armature in " + path)
    root = bpy.data.objects["HandRoot"]
    for o in [o for o in new if o.parent is None]:
        o.parent = root
        o.matrix_parent_inverse.identity()
    print("rig bones:", sorted(b.name for b in arm.data.bones))
    return arm


def _aim_bone(arm, pb, world_dir):
    """Rotate one pose bone about its head so it points along world_dir (minimal rotation, roll kept)."""
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    head = mw @ pb.head
    cur = (mw @ pb.tail - head).normalized()
    q = cur.rotation_difference(Vector(world_dir).normalized())
    Rw = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head)
    pb.matrix = mw.inverted() @ Rw @ mw @ pb.matrix
    bpy.context.view_layer.update()


def wrap_chain(start, lengths, centre, radius, forward, max_angle=math.pi, press_angle=0.0):
    """Joints of a chain of given segment lengths that leaves `start`, runs straight to the circle of
    `radius` around `centre` and wraps along it - a finger closing around a ball. The curl plane holds
    the start, the centre and the `forward` direction (where the finger heads first); past `max_angle`
    around the circle (measured from the start's direction) the chain continues straight."""
    S, Cc, f = Vector(start), Vector(centre), Vector(forward).normalized()
    dv = S - Cc
    d = dv.length
    e1 = dv / d
    e2 = (f - e1 * f.dot(e1)).normalized()
    if d > radius:
        a = math.acos(radius / d)
        tangent = math.sqrt(d * d - radius * radius)
    else:
        a, tangent, radius = 0.0, 0.0, d

    def on_circle(ang):
        return Cc + (e1 * math.cos(ang) + e2 * math.sin(ang)) * radius

    def along(ang):
        return (-e1 * math.sin(ang) + e2 * math.cos(ang)).normalized()
    P_t = on_circle(a)
    pts, left, ang = [S], tangent, a
    straight = None                                # (point, direction) once the wrap is capped
    for L in lengths:
        if straight is not None:
            pts.append(pts[-1] + straight * L)
        elif left >= L:
            left -= L
            pts.append(S + (P_t - S) * (1 - left / tangent))
        else:
            arc = (L - left) / radius
            left = 0.0
            if ang + arc <= max_angle:
                ang += arc
                pts.append(on_circle(ang))
            else:
                rest = (ang + arc - max_angle) * radius
                ang = max_angle
                # past the cap the digit no longer follows the circle: it presses into the ball
                # (press_angle toward the centre) or, at 0, continues along the tangent
                inward = -(e1 * math.cos(ang) + e2 * math.sin(ang))
                straight = (along(ang) * math.cos(press_angle) + inward * math.sin(press_angle)).normalized()
                pts.append(on_circle(ang) + straight * rest)
    return pts


def wrap_in_plane(start, lengths, centre, sphere_r, normal, forward, max_angle=math.pi, press_angle=0.0):
    """A finger curls in ITS OWN plane (through `start`, with `normal`): the wrap circle is where that
    plane cuts the sphere, so neighbouring fingers run side by side instead of converging. A plane
    that misses the sphere leaves the finger straight along `forward`."""
    S, Cc, n = Vector(start), Vector(centre), Vector(normal).normalized()
    off = (Cc - S).dot(n)                       # signed distance of the centre from the plane
    C_p = Cc - n * off                          # the centre projected into the plane
    rho2 = sphere_r * sphere_r - off * off
    f = Vector(forward)
    f_p = (f - n * f.dot(n)).normalized()
    if rho2 < 0.04:
        pts, p = [S], S
        for L in lengths:
            p = p + f_p * L
            pts.append(p)
        return pts
    return wrap_chain(S, lengths, C_p, math.sqrt(rho2), f_p, max_angle, press_angle)


def ensure_sun_ball():
    """A wire sphere of the sun's radius at the origin, for the viewport only (never rendered)."""
    sc = scene()
    ball = bpy.data.objects.get("SunBall")
    if ball is None:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=(0, 0, 0))
        ball = bpy.context.active_object
        ball.name = "SunBall"
        ball.display_type = "WIRE"
        ball.hide_render = True
        _ray_vis(ball, camera=False, light=False)
    return ball


def pose_rig(curl):
    """curl 0 = the rest pose (open hand), curl 1 = every finger wrapped around the sun; between
    them each bone turns from its open direction toward its wrapped one, fingers on the page's delays."""
    C = cfg()
    M, P = C["model"], C["pose"]
    G = P["grab"]
    fcs, tc = finger_curls(curl, P)
    arm = armature()
    _clear_pose(arm)
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    chains = {n: M["bones"][n] for n in POSE_NAMES + ["thumb"]}
    missing = [b for bones in chains.values() for b in bones if b not in arm.pose.bones]
    if missing:
        print("MISSING BONES:", missing, "- rig has:", sorted(b.name for b in arm.data.bones))
        return arm
    rest = {b: (mw @ arm.pose.bones[b].tail - mw @ arm.pose.bones[b].head).normalized()
            for bones in chains.values() for b in bones}
    centre = Vector((0.0, 0.0, 0.0))
    thumb_open = P.get("thumb_dirs", {}).get("open")
    for name, bones in chains.items():
        c = ease(tc if name == "thumb" else fcs[name])
        head0 = mw @ arm.pose.bones[bones[0]].head
        lengths = [(mw @ arm.pose.bones[b].tail - mw @ arm.pose.bones[b].head).length for b in bones]
        radius = G["radius"] + G["finger_r"][name] + G.get("joint_lift", 0.1)
        pts = wrap_in_plane(head0, lengths, centre, radius, Vector(G["plane_normal"][name]).normalized(),
                            G["forward"][name], math.radians(G["max_angle"][name]),
                            math.radians(G.get("press_angle", {}).get(name, 0.0)))
        wrapped = [(pts[i + 1] - pts[i]).normalized() for i in range(len(bones))]
        opened = [Vector(v).normalized() for v in thumb_open] if (name == "thumb" and thumb_open) else [rest[b] for b in bones]
        for b, d_open, d_wrap in zip(bones, opened, wrapped):
            _aim_bone(arm, arm.pose.bones[b], _slerp_dir(d_open, d_wrap, c))
    return arm


def grab_report():
    """How the posed hand sits on the sun: each fingertip's distance from the centre (1 = touching
    with no flesh) and the closest bone joint, so penetration shows up as a number."""
    arm = armature()
    mw = arm.matrix_world
    M = cfg()["model"]
    out = {}
    for n in POSE_NAMES + ["thumb"]:
        bones = M["bones"][n]
        tip = mw @ arm.pose.bones[bones[-1]].tail
        joints = [mw @ arm.pose.bones[b].head for b in bones] + [tip]
        out[n] = {"tip_r": round(tip.length, 2), "tip": tuple(round(v, 2) for v in tip),
                  "min_joint_r": round(min(j.length for j in joints), 2)}
    for k, v in out.items():
        print(f"  {k:7s} tip r={v['tip_r']} at {v['tip']}  min joint r={v['min_joint_r']}")
    return out


# ---------------------------------------------------------------- aligning a real rig to the sun
def armature():
    return next(o for o in scene().objects if o.type == "ARMATURE")


def _bone_head(arm, name):
    b = arm.data.bones.get(name)
    if b is None:
        raise KeyError(f"bone {name!r} not in rig; rig has {sorted(x.name for x in arm.data.bones)}")
    return arm.matrix_world @ b.head_local


def align_rig(arm=None):
    """Place the imported right hand in our frame: fingers up (+Z), thumb to the viewer's right (+X),
    palm toward the camera (-Y); the knuckle line at knuckle_z_r and the knuckle span at knuckle_span_r.
    The armature and its meshes are parented to HandRoot, whose matrix carries the whole transform."""
    C = cfg()
    M, Hc = C["model"], C["hand"]
    arm = arm or armature()
    meshes = [o for o in scene().objects if o.type == "MESH" and
              (o.parent == arm or any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers))]
    root = bpy.data.objects["HandRoot"]
    # everything back to plain object transforms first, so bone positions are measured in rest space
    for o in [arm] + meshes:
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    K = {n: _bone_head(arm, M["bones"][n][0]) for n in POSE_NAMES}
    W = _bone_head(arm, M["bones"]["hand"])
    kmean = sum(K.values(), Vector()) / 4
    finger_dir = (kmean - W).normalized()
    radial = K["index"] - K["pinky"]
    radial = (radial - finger_dir * radial.dot(finger_dir)).normalized()
    palm_n = radial.cross(finger_dir).normalized()          # a right hand: this points out of the palm
    global PALM_NORMAL_REST
    PALM_NORMAL_REST = tuple(palm_n)
    R = Matrix((radial, -palm_n, finger_dir)).to_4x4()      # rows: radial -> X, back of hand -> +Y, fingers -> Z
    s = M["knuckle_span_r"] / (K["index"] - K["pinky"]).length
    root.matrix_world = (Matrix.Rotation(math.radians(Hc.get("tilt_x_deg", 0.0)), 4, "X")      # lean over the sun
                         @ Matrix.Translation((0, Hc["palm_depth_r"], Hc["knuckle_z_r"])) @ Matrix.Scale(s, 4)
                         @ R @ Matrix.Translation(-kmean))
    for o in [arm] + meshes:
        o.parent = root
        o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    print(f"align: scale {s:.4f}, knuckle span {(K['index'] - K['pinky']).length:.4f} -> {M['knuckle_span_r']}, "
          f"wrist now at {tuple(round(v, 2) for v in (arm.matrix_world @ arm.data.bones[M['bones']['hand']].head_local))}")
    return s


def _clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)


def detect_axes(write=True):
    """Find which local axis folds a finger toward the camera and which splays it, by trying them.
    Writes bend_axis / bend_sign / splay_axis / splay_sign into the config when asked."""
    C = cfg()
    M = C["model"]
    arm = armature()
    bones = M["bones"]["middle"]
    tipb = arm.pose.bones[bones[2]]

    def tip():
        bpy.context.view_layer.update()
        return arm.matrix_world @ tipb.tail
    _clear_pose(arm)
    t0 = tip()
    scores = {}
    for ax in range(3):
        for sgn in (1, -1):
            _clear_pose(arm)
            for b in bones:
                e = [0.0, 0.0, 0.0]
                e[ax] = sgn * math.radians(35)
                arm.pose.bones[b].rotation_euler = e
            d = tip() - t0
            scores[(ax, sgn)] = d
    _clear_pose(arm)
    bend = max(scores, key=lambda k: -scores[k].y)                      # toward the camera (-Y)
    splay = max((k for k in scores if k[0] != bend[0]), key=lambda k: scores[k].x)   # toward the thumb (+X)
    names = "XYZ"
    print("flex candidates (axis, sign) -> tip motion:", {f"{names[a]}{'+' if s > 0 else '-'}": tuple(round(v, 2) for v in d) for (a, s), d in scores.items()})
    res = {"bend_axis": names[bend[0]], "bend_sign": bend[1], "splay_axis": names[splay[0]], "splay_sign": splay[1]}
    print("detected:", res)
    if write:
        C["model"].update(res)
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(C, fh, indent=2)
    return res


# ---------------------------------------------------------------- the palm's meat (a shape key)
PALM_NORMAL_REST = None     # set by align_rig: the palm's outward direction in the rig's rest space


def add_palm_meat(mesh=None, arm=None):
    """Swell the thenar and hypothenar eminences and thicken the palm a little, by pushing palm-side
    vertices along their normals, weighted by the MakeHuman deform groups. Non-destructive: shape key."""
    C = cfg()
    Pm = C["hand"].get("palm_meat", {})
    if not Pm or PALM_NORMAL_REST is None:
        print("palm meat: skipped (no config or align_rig not run)")
        return None
    arm = arm or armature()
    mesh = mesh or rig_mesh(arm)
    me = mesh.data
    scale = arm.matrix_world.to_scale().x or 1.0             # world units per mesh unit
    if me.shape_keys is None:
        mesh.shape_key_add(name="Basis", from_mix=False)
    old_key = me.shape_keys.key_blocks.get("GodHandMeat")
    if old_key:
        mesh.shape_key_remove(old_key)
    basis = me.shape_keys.key_blocks[0]
    key = mesh.shape_key_add(name="GodHandMeat", from_mix=False)
    key.value = 1.0
    gi = {g.name: g.index for g in mesh.vertex_groups}
    groups = {"thenar": {"finger1-1.R": 1.0, "metacarpal1.R": 0.35},
              "hypothenar": {"metacarpal4.R": 1.0, "metacarpal3.R": 0.3},
              "palm": {"metacarpal1.R": 1, "metacarpal2.R": 1, "metacarpal3.R": 1, "metacarpal4.R": 1, "wrist.R": 0.5}}
    pn = Vector(PALM_NORMAL_REST)
    moved = 0
    for v in me.vertices:
        facing = v.normal.dot(pn)
        if facing < 0.25:
            continue
        w = {g.group: g.weight for g in v.groups}
        push = 0.0
        for part, amount in Pm.items():
            ww = sum(w.get(gi[name], 0.0) * k for name, k in groups[part].items() if name in gi)
            push += amount * min(1.0, ww)
        if push <= 1e-4:
            continue
        d = push * (facing - 0.25) / 0.75 / scale
        key.data[v.index].co = basis.data[v.index].co + v.normal * d
        moved += 1
    print(f"palm meat: moved {moved} vertices")
    return key


# ---------------------------------------------------------------- the MPFB human: keep only the right arm
def rig_mesh(arm=None):
    arm = arm or armature()
    return next(o for o in scene().objects if o.type == "MESH" and
                any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers))


def prepare_mesh(mesh=None, arm=None):
    """Mask everything but the right forearm and hand, smooth it, subdivide it, give it the skin."""
    C = cfg()
    M = C["model"]
    arm = arm or armature()
    mesh = mesh or rig_mesh(arm)
    keep = set(M["bones"].get("keep_groups", []))
    idx = {g.index for g in mesh.vertex_groups if g.name in keep}
    vg = mesh.vertex_groups.get("GodHandKeep") or mesh.vertex_groups.new(name="GodHandKeep")
    inside, outside = [], []
    for v in mesh.data.vertices:
        w = sum(g.weight for g in v.groups if g.group in idx)
        (inside if w > M.get("keep_threshold", 0.3) else outside).append(v.index)
    vg.add(inside, 1.0, "REPLACE")
    if outside:
        vg.remove(outside)
    mask = mesh.modifiers.get("GodHandOnly")
    if not mask:
        mask = mesh.modifiers.new("GodHandOnly", "MASK")
        mask.vertex_group = "GodHandKeep"
        mask.threshold = 0.5
        mesh.modifiers.move(len(mesh.modifiers) - 1, 0)
    sub = mesh.modifiers.get("GodHandSubsurf")
    if not sub:
        sub = mesh.modifiers.new("GodHandSubsurf", "SUBSURF")
        sub.levels, sub.render_levels = 1, M.get("subsurf", 2)
    for p in mesh.data.polygons:
        p.use_smooth = True
    mesh.data.materials.clear()
    mesh.data.materials.append(bpy.data.materials["GodHandSkin"])
    print(f"prepare_mesh: {len(inside)} vertices kept of {len(mesh.data.vertices)}")
    return mesh


# ---------------------------------------------------------------- dispatch
def load_hand():
    """standin: metaballs. glb/fbx: import a file. mpfb: the human already in the scene (made live)."""
    kind = cfg()["model"]["kind"]
    if kind == "standin":
        return load_standin()
    arm = armature() if kind == "mpfb" else load_rig()
    prepare_mesh(arm=arm)
    align_rig(arm)
    return arm


def pose(curl):
    kind = cfg()["model"]["kind"]
    return pose_standin(curl) if kind == "standin" else pose_rig(curl)


# ---------------------------------------------------------------- rendering
def render_still(path, front=False, samples=None):
    sc = scene()
    hold = bpy.data.objects["SunPlaneHoldout"]
    hold.hide_render = not front
    mask = bpy.data.objects.get("FrontMask") or _front_mask(sc)
    mask.hide_render = not front
    keep = sc.cycles.samples if hasattr(sc, "cycles") else None
    if samples and keep is not None:
        sc.cycles.samples = samples
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    if samples and keep is not None:
        sc.cycles.samples = keep
    hold.hide_render = True
    mask.hide_render = True
    return path


def render_pose_tests(out=None, samples=None):
    C = cfg()
    out = out or os.path.join(ROOT, "assets", "hand")
    samples = samples or C["look"]["samples_preview"]
    done = []
    for name, curl, front in (("open", 0.0, False), ("half", 0.5, False), ("fist", 1.0, False), ("fist-front", 1.0, True)):
        pose(curl)
        done.append(render_still(os.path.join(out, f"pose-{name}.png"), front=front, samples=samples))
    return done


def render_sweep(out=None, levels=None):
    C = cfg()
    out = out or os.path.join(ROOT, C["render"]["out"])
    N = levels or C["render"]["levels"]
    sun = sun_pixels()
    meta = {"px_per_r": C["frame"]["px_per_r"], "w": scene().render.resolution_x, "h": scene().render.resolution_y,
            "sun": sun, "levels": N, "curl": [i / (N - 1) for i in range(N)], "model": C["model"]["kind"],
            "frames": []}
    for i in range(N):
        curl = i / (N - 1)
        pose(curl)
        b = render_still(os.path.join(out, "back", f"{i:02d}.png"), front=False)
        f = render_still(os.path.join(out, "front", f"{i:02d}.png"), front=True)
        meta["frames"].append({"i": i, "curl": curl, "back": os.path.relpath(b, out), "front": os.path.relpath(f, out)})
        print(f"sweep {i + 1}/{N} curl={curl:.3f}")
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    return meta


def save_blend(path=None):
    path = path or os.path.join(ROOT, "assets", "hand", "hand.blend")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    return path
