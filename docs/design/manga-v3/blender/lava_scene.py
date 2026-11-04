"""Blood - the lava river, rendered in Blender as a seamless loop (scene "BloodLava").

The page draws the river as a flat ribbon in SCREEN space (course points as fractions of a
1920x1080 frame, half-width 7 px at the horizon growing to 27 px at the bottom). Here the same
ribbon is built on a 3D ground plane: a camera that reproduces the page's frame is placed above
the ground with its horizon at y = 0.78, every course point is projected down onto the ground
along the camera ray, and the ribbon's 3D width is chosen so it projects back to the page's
width. So the render lands exactly on the painted channel, but its crust, cracks and flow are
real ground textures that foreshorten toward the horizon.

Flow loop: the melt texture slides toward the viewer; a loop of N frames is made seamless by
cross-fading the pattern with itself one loop-length behind (frame N == frame 0 exactly).

Inside Blender:
    import lava_scene as ls
    ls.build(); ls.render_still()          # approval still (frame 0)
    ls.render_loop()                       # assets/lava/render/NN.png + meta.json
"""
import json
import math
import os

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCENE_NAME = "BloodLava"
CONFIG_PATH = os.path.join(HERE, "lava_config.json")

DEFAULT = {
    "frame": {"w": 1920, "h": 1080, "horizon": 0.78, "region": [0.40, 0.76, 0.70, 1.0], "vfov_deg": 32.0,
              "cam_height": 1.0},
    "course": [[0.638, 0.782], [0.575, 0.79], [0.512, 0.802], [0.488, 0.824], [0.502, 0.854],
               [0.54, 0.898], [0.566, 0.952], [0.552, 1.04]],
    "bank_px": {"base": 7.0, "grow": 20.0, "pow": 1.4},
    "look": {"crust": "#1a0504", "melt": "#c84818", "core": "#ffb054", "glow": "#6a1408",
             "emission": 9.0, "core_emission": 22.0, "crack_scale": 2.2, "crack_width": 0.28,
             "flow_scale": 1.6, "speed": 0.9, "samples": 64, "ground_glow": 0.08},
    "loop": {"frames": 48, "fps": 24},
}


def cfg():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(DEFAULT, f, indent=2)
    return json.loads(json.dumps(DEFAULT))


def hexcol(h, alpha=None):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    out = (lin(r), lin(g), lin(b))
    return out + (alpha,) if alpha is not None else out


def scene():
    return bpy.data.scenes.get(SCENE_NAME)


# ---------------------------------------------------------------- geometry
def camera_rays(C):
    """The camera that reproduces the page's frame: at height h, looking along +Y, pitched down so
    the horizon lands at frame.horizon. Returns (position, focal px, pitch) and a function mapping
    frame fractions (fx, fy) to the ground point hit by that pixel's ray."""
    F = C["frame"]
    W, H = F["w"], F["h"]
    f_px = (H / 2) / math.tan(math.radians(F["vfov_deg"]) / 2)
    # the horizon (ray parallel to the ground) sits (horizon - 0.5) * H below the frame centre
    pitch = math.atan((F["horizon"] - 0.5) * H / f_px)      # camera looks down by this angle
    h = F["cam_height"]
    cp, sp = math.cos(pitch), math.sin(pitch)

    def ground(fx, fy):
        # camera space: x right, y up, z forward (before pitch); pixel offsets from the centre
        dx = (fx - 0.5) * W
        dy = (0.5 - fy) * H
        # direction in camera space, then pitched down about X
        d = Vector((dx, dy, f_px)).normalized()
        d_w = Vector((d.x, d.z * cp + d.y * sp, d.y * cp - d.z * sp))   # world: x right, y forward, z up
        if d_w.z >= -1e-6:
            return None
        t = h / -d_w.z
        return Vector((d_w.x * t, d_w.y * t, 0.0))
    return (Vector((0, 0, h)), f_px, pitch), ground


def _spline(pts, n):
    """Catmull-Rom through the points (the page uses the same idea)."""
    out = []
    P = [pts[0]] + list(pts) + [pts[-1]]
    segs = len(pts) - 1
    for i in range(n):
        s = i / (n - 1) * segs
        k = min(segs - 1, int(s))
        t = s - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    return out


def build_river(C, ground, f_px, n=96):
    """The ribbon mesh on the ground, with UVs: u along the course (0 at the horizon end),
    v across (0..1). Width per point chosen so its projection is the page's bank width."""
    F, B = C["frame"], C["bank_px"]
    W, H = F["w"], F["h"]
    course2d = [Vector((x * W, y * H)) for x, y in C["course"]]
    P2 = _spline(course2d, n)
    cam_pos = Vector((0, 0, F["cam_height"]))
    verts, uvs, faces = [], [], []
    along = 0.0
    prev = None
    for k, p in enumerate(P2):
        u = k / (n - 1)
        g = ground(p.x / W, p.y / H)
        if g is None:
            g = ground(p.x / W, (F["horizon"] + 0.002))
        half_px = (B["base"] + B["grow"] * (u ** B["pow"])) * (W / 1920)
        depth = (g - cam_pos).length                       # distance from the camera
        half_w = half_px * depth / f_px                     # pixels -> ground units at that depth
        # the across direction on the ground: perpendicular to the course tangent
        nxt = ground(P2[min(n - 1, k + 1)].x / W, P2[min(n - 1, k + 1)].y / H) or g
        prv = ground(P2[max(0, k - 1)].x / W, P2[max(0, k - 1)].y / H) or g
        tan = (nxt - prv)
        tan.z = 0
        tan = tan.normalized() if tan.length > 1e-9 else Vector((0, -1, 0))
        side = Vector((-tan.y, tan.x, 0))
        if prev is not None:
            along += (g - prev).length
        prev = g
        for j, s in enumerate((-1.0, -0.5, 0.0, 0.5, 1.0)):
            verts.append(g + side * (half_w * s))
            uvs.append((along, (s + 1) / 2))
    mean_w = 2 * sum((B["base"] + B["grow"] * ((k / (n - 1)) ** B["pow"])) * (W / 1920) for k in range(n)) / n
    # ground units per pixel at mid-depth, to express the mean width in ground units
    mid = ground(C["course"][len(C["course"]) // 2][0], C["course"][len(C["course"]) // 2][1])
    mean_w_ground = mean_w * (mid - cam_pos).length / f_px
    uvs = [(u_al / mean_w_ground, v) for (u_al, v) in uvs]
    cols = 5
    for k in range(n - 1):
        for j in range(cols - 1):
            a = k * cols + j
            faces.append((a, a + 1, a + cols + 1, a + cols))
    me = bpy.data.meshes.new("LavaRiver")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uv.data[li].uv = uvs[vi]
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new("LavaRiver", me)
    obj["length"] = along
    return obj


# ---------------------------------------------------------------- material
def lava_material(C):
    L = C["look"]
    m = bpy.data.materials.get("LavaMelt")
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new("LavaMelt")
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    for n in list(nodes):
        nodes.remove(n)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    uv = nodes.new("ShaderNodeUVMap")
    uv.location = (-1400, 0)
    # two flow offsets (A and B, one loop apart), cross-faded: a seamless loop
    offA = nodes.new("ShaderNodeVectorMath")
    offA.name = "OffsetA"
    offA.operation = "ADD"
    offA.location = (-1150, 150)
    offB = nodes.new("ShaderNodeVectorMath")
    offB.name = "OffsetB"
    offB.operation = "ADD"
    offB.location = (-1150, -250)
    links.new(uv.outputs["UV"], offA.inputs[0])
    links.new(uv.outputs["UV"], offB.inputs[0])
    fade = nodes.new("ShaderNodeValue")
    fade.name = "Fade"
    fade.location = (-600, 400)
    fade.outputs[0].default_value = 0.0

    def melt_branch(vec_node, x0):
        # crust plates (voronoi edges = cracks) + hot flow streaks along u
        vor = nodes.new("ShaderNodeTexVoronoi")
        vor.location = (x0, 100)
        vor.feature = "DISTANCE_TO_EDGE"
        vor.inputs["Scale"].default_value = L["crack_scale"]
        links.new(vec_node.outputs[0], vor.inputs["Vector"])
        crack = nodes.new("ShaderNodeMapRange")
        crack.location = (x0 + 250, 100)
        crack.inputs["From Min"].default_value = 0.0
        crack.inputs["From Max"].default_value = L["crack_width"]
        crack.inputs["To Min"].default_value = 1.0
        crack.inputs["To Max"].default_value = 0.0
        links.new(vor.outputs["Distance"], crack.inputs["Value"])
        flow = nodes.new("ShaderNodeTexNoise")
        flow.location = (x0, -200)
        flow.inputs["Scale"].default_value = L["flow_scale"]
        flow.inputs["Detail"].default_value = 5.0
        flow.inputs["Roughness"].default_value = 0.55
        # stretch the flow along u (streaks)
        stretch = nodes.new("ShaderNodeVectorMath")
        stretch.location = (x0 - 200, -200)
        stretch.operation = "MULTIPLY"
        stretch.inputs[1].default_value = (0.35, 2.5, 1.0)
        links.new(vec_node.outputs[0], stretch.inputs[0])
        links.new(stretch.outputs[0], flow.inputs["Vector"])
        heat = nodes.new("ShaderNodeMath")
        heat.location = (x0 + 500, 0)
        heat.operation = "MAXIMUM"
        links.new(crack.outputs[0], heat.inputs[0])
        pw = nodes.new("ShaderNodeMath")
        pw.location = (x0 + 250, -200)
        pw.operation = "POWER"
        pw.inputs[1].default_value = L.get("flow_power", 3.0)
        links.new(flow.outputs["Fac"], pw.inputs[0])
        links.new(pw.outputs[0], heat.inputs[1])
        return heat
    hA = melt_branch(offA, -900)
    hB = melt_branch(offB, -900 - 0)
    hB.location = (-400, -500)
    mixh = nodes.new("ShaderNodeMix")
    mixh.location = (-100, 0)
    mixh.data_type = "FLOAT"
    links.new(fade.outputs[0], mixh.inputs["Factor"])
    links.new(hA.outputs[0], mixh.inputs[2])
    links.new(hB.outputs[0], mixh.inputs[3])
    # the channel is hottest in the middle: v = 0.5 -> 1, banks -> 0
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1150, -600)
    links.new(uv.outputs["UV"], sep.inputs[0])
    across = nodes.new("ShaderNodeMath")
    across.location = (-900, -600)
    across.operation = "SUBTRACT"
    across.inputs[1].default_value = 0.5
    links.new(sep.outputs["Y"], across.inputs[0])
    absn = nodes.new("ShaderNodeMath")
    absn.location = (-700, -600)
    absn.operation = "ABSOLUTE"
    links.new(across.outputs[0], absn.inputs[0])
    centre = nodes.new("ShaderNodeMapRange")
    centre.location = (-500, -600)
    centre.inputs["From Min"].default_value = 0.5
    centre.inputs["From Max"].default_value = L.get("centre_width", 0.12)
    centre.inputs["To Min"].default_value = 0.0
    centre.inputs["To Max"].default_value = 1.0
    links.new(absn.outputs[0], centre.inputs["Value"])
    heat = nodes.new("ShaderNodeMath")
    heat.location = (150, 0)
    heat.operation = "MULTIPLY"
    links.new(mixh.outputs[0], heat.inputs[0])
    links.new(centre.outputs[0], heat.inputs[1])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (350, 0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = hexcol(L["crust"], 1)
    e1 = ramp.color_ramp.elements.new(0.4)
    e1.color = hexcol(L["melt"], 1)
    e0 = ramp.color_ramp.elements.new(0.18)
    e0.color = hexcol("#4a0e08", 1)
    ramp.color_ramp.elements[-1].position = 1.0
    ramp.color_ramp.elements[-1].color = hexcol(L["core"], 1)
    links.new(heat.outputs[0], ramp.inputs["Fac"])
    em = nodes.new("ShaderNodeEmission")
    em.location = (650, 0)
    links.new(ramp.outputs["Color"], em.inputs["Color"])
    strength = nodes.new("ShaderNodeMapRange")
    strength.location = (350, -250)
    strength.inputs["From Min"].default_value = 0.0
    strength.inputs["From Max"].default_value = 1.0
    strength.inputs["To Min"].default_value = L.get("crust_emission", 0.3)
    strength.inputs["To Max"].default_value = L["core_emission"]
    links.new(heat.outputs[0], strength.inputs["Value"])
    links.new(strength.outputs[0], em.inputs["Strength"])
    links.new(em.outputs[0], out.inputs["Surface"])
    return m


def ground_material(C):
    """A faint warm glow on the ground beside the channel - most of the ground stays transparent."""
    m = bpy.data.materials.get("LavaGround")
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new("LavaGround")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs["Color"].default_value = hexcol("#3a0c08", 1)
    d.inputs["Roughness"].default_value = 1.0
    nt.links.new(d.outputs[0], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------- scene
def build():
    C = cfg()
    F, L = C["frame"], C["look"]
    old = scene()
    if old:
        bpy.data.scenes.remove(old)
    sc = bpy.data.scenes.new(SCENE_NAME)
    bpy.context.window.scene = sc
    col = sc.collection
    W, H = F["w"], F["h"]
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.use_persistent_data = True
    try:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "GPU"
        sc.cycles.samples = L["samples"]
        sc.cycles.use_denoising = True
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
        sc.cycles.max_bounces = 3
    except TypeError as e:
        print("cycles:", e)
    # only the river region is rendered
    x0, y0, x1, y1 = F["region"]
    sc.render.use_border = True
    sc.render.use_crop_to_border = True
    sc.render.border_min_x, sc.render.border_max_x = x0, x1
    sc.render.border_min_y, sc.render.border_max_y = 1 - y1, 1 - y0
    # world: black, no light but the melt
    w = bpy.data.worlds.get("LavaWorld") or bpy.data.worlds.new("LavaWorld")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0
    sc.world = w
    # camera
    (pos, f_px, pitch), ground = camera_rays(C)
    cam_d = bpy.data.cameras.new("LavaCam")
    cam_d.sensor_fit = "VERTICAL"
    cam_d.sensor_height = 36.0
    cam_d.lens = 36.0 * f_px / H
    cam = bpy.data.objects.new("LavaCam", cam_d)
    cam.location = pos
    cam.rotation_euler = (math.pi / 2 - pitch, 0, 0)      # looking along +Y, pitched down
    col.objects.link(cam)
    sc.camera = cam
    # ground (catches a little glow) and the river
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 150, -0.0005))
    g = bpy.context.active_object
    g.name = "LavaGroundPlane"
    g.data.materials.append(ground_material(C))
    g.is_holdout = L.get("ground_glow", 0) <= 0
    river = build_river(C, ground, f_px)
    col.objects.link(river)
    river.data.materials.append(lava_material(C))
    print(f"lava scene: f_px {f_px:.1f}, pitch {math.degrees(pitch):.2f} deg, river length {river['length']:.3f} ground units")
    return sc


def set_flow(frame_idx):
    """Flow offsets for a frame of the loop: pattern A at offset s*t, pattern B one loop behind,
    cross-fade weight t/T. Offsets slide along u toward the viewer (u grows toward the bottom)."""
    C = cfg()
    N = C["loop"]["frames"]
    T = N / C["loop"]["fps"]
    t = frame_idx / C["loop"]["fps"]
    speed = C["look"]["speed"]                                                     # channel widths per second
    m = bpy.data.materials["LavaMelt"].node_tree.nodes
    m["OffsetA"].inputs[1].default_value = (-speed * t, 0, 0)
    m["OffsetB"].inputs[1].default_value = (-speed * (t - T), 0, 0)
    m["Fade"].outputs[0].default_value = t / T


def render_still(path=None, samples=None):
    sc = scene()
    path = path or os.path.join(ROOT, "assets", "lava", "lava-still.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    set_flow(0)
    keep = sc.cycles.samples
    if samples:
        sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    sc.cycles.samples = keep
    return path


def render_loop(out=None):
    C = cfg()
    sc = scene()
    out = out or os.path.join(ROOT, "assets", "lava", "render")
    os.makedirs(out, exist_ok=True)
    N = C["loop"]["frames"]
    F = C["frame"]
    x0, y0, x1, y1 = F["region"]
    meta = {"frames": N, "fps": C["loop"]["fps"], "region": F["region"],
            "px": [round(x0 * F["w"]), round(y0 * F["h"]), round((x1 - x0) * F["w"]), round((y1 - y0) * F["h"])],
            "files": []}
    for i in range(N):
        set_flow(i)
        p = os.path.join(out, f"{i:02d}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True, scene=sc.name)
        meta["files"].append(os.path.basename(p))
        print(f"lava {i + 1}/{N}")
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    return meta
