"""Satisfying-Video: Ein Berliner rutscht in drei Weichheitsstufen durch einen Ring.

Aufruf (mit Blender als Python-Modul):
    python berliner.py --out <ordner> [--res 720] [--samples 20] [--frames a-b]

Szene: Kanalfarben Orange (Bahn) und Dunkelblau (Studio), weißer Ring, blaue Schüssel.
Level 1 HART: bleibt am Ring hängen und fällt runter.
Level 2 WEICH: quetscht sich mit Widerstand durch und plumpst in die Schüssel.
Level 3 PUDDING: flutscht durch, dehnt sich stark und platscht in die Schüssel.
"""

import argparse
import math
import sys

import bpy
from mathutils import Vector

FPS = 30
SEG = 120  # Frames pro Level (4 s)
LEVELS = ["hart", "weich", "pudding"]

ORANGE = (1.0, 0.33, 0.04, 1)
NAVY_FLOOR = (0.035, 0.06, 0.17, 1)
NAVY_WALL = (0.025, 0.045, 0.13, 1)
NAVY_BOWL = (0.02, 0.05, 0.22, 1)

# Geometrie der Bahn
THETA = math.radians(35)
D = Vector((math.cos(THETA), 0, -math.sin(THETA)))  # Richtung bergab
N = Vector((math.sin(THETA), 0, math.cos(THETA)))  # Normale der Bahn
A = Vector((-2.9, 0, 6.6))
RAMP_LEN = 3.7
HALF_H = 0.25  # halbe Höhe des Berliners
RADIUS = 0.45  # Radius des Berliners
S0 = 0.5
ACC = 1.6
GRAV = 6.0
T_RING = 0.38  # Flugzeit bis zum Ring
RING_INNER = 0.36
RING_MINOR = 0.07
BOWL_INNER_Z = 0.12

PARAMS = {
    "weich": dict(slow=0.40, wob_a=0.12, wob_w=14, wob_k=4.0, land_d=0.35, land_w=13, land_k=5.0, rest=1.0),
    "pudding": dict(slow=0.85, wob_a=0.28, wob_w=9, wob_k=2.5, land_d=0.60, land_w=8, land_k=2.2, rest=0.82),
}


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, color, rough=0.35, coat=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Specular IOR Level"].default_value = spec
    return m


def berliner_material():
    m = bpy.data.materials.new("Berliner")
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    p = nodes["Principled BSDF"]
    p.inputs["Roughness"].default_value = 0.75
    p.inputs["Subsurface Weight"].default_value = 0.15
    p.inputs["Subsurface Radius"].default_value = (0.4, 0.25, 0.1)

    tex = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tex.outputs["Object"], sep.inputs[0])

    # heller Ring um die Mitte, gebräunt oben und unten
    absz = nodes.new("ShaderNodeMath"); absz.operation = "ABSOLUTE"
    links.new(sep.outputs["Z"], absz.inputs[0])
    band = nodes.new("ShaderNodeMapRange")
    band.inputs["From Min"].default_value = 0.05
    band.inputs["From Max"].default_value = 0.15
    links.new(absz.outputs[0], band.inputs["Value"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.95, 0.80, 0.52, 1)
    ramp.color_ramp.elements[1].color = (0.62, 0.30, 0.08, 1)
    links.new(band.outputs[0], ramp.inputs[0])

    # Puderzucker oben
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18
    noise.inputs["Detail"].default_value = 6
    top = nodes.new("ShaderNodeMapRange")
    top.inputs["From Min"].default_value = 0.14
    top.inputs["From Max"].default_value = 0.24
    links.new(sep.outputs["Z"], top.inputs["Value"])
    mult = nodes.new("ShaderNodeMath"); mult.operation = "MULTIPLY"
    links.new(top.outputs[0], mult.inputs[0])
    links.new(noise.outputs["Fac"], mult.inputs[1])
    sugar = nodes.new("ShaderNodeMapRange")
    sugar.inputs["From Min"].default_value = 0.3
    sugar.inputs["From Max"].default_value = 0.5
    links.new(mult.outputs[0], sugar.inputs["Value"])
    mix = nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["B"].default_value = (0.97, 0.96, 0.94, 1)
    links.new(sugar.outputs[0], mix.inputs["Factor"])
    links.new(ramp.outputs["Color"], mix.inputs["A"])
    links.new(mix.outputs["Result"], p.inputs["Base Color"])
    return m


def add_box(name, center, size, rot_y, material):
    bpy.ops.mesh.primitive_cube_add(location=center, rotation=(0, rot_y, 0))
    o = bpy.context.object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bev = o.modifiers.new("bevel", "BEVEL")
    bev.width = 0.03
    bev.segments = 3
    o.data.materials.append(material)
    return o


def build_scene():
    sc = bpy.context.scene
    world = bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.035, 0.1, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35

    m_floor = mat("Floor", NAVY_FLOOR, rough=0.55)
    m_wall = mat("Wall", NAVY_WALL, rough=0.7)
    m_orange = mat("Orange", ORANGE, rough=0.22, coat=0.6)
    m_white = mat("Ceramic", (0.92, 0.92, 0.95, 1), rough=0.12, coat=0.8)
    m_bowl = mat("Bowl", NAVY_BOWL, rough=0.18, coat=0.8)
    m_leg = mat("Leg", (0.05, 0.08, 0.2, 1), rough=0.3)

    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    bpy.context.object.data.materials.append(m_floor)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 6, 0), rotation=(math.radians(90), 0, 0))
    bpy.context.object.data.materials.append(m_wall)

    # Bahn: Brett plus zwei Seitenleisten
    pitch = THETA  # Rotation um Y bringt x-Achse auf D
    mid = A + D * (RAMP_LEN / 2) - N * 0.075
    add_box("Ramp", mid, (RAMP_LEN + 0.4, 1.3, 0.15), pitch, m_orange)
    for side in (-1, 1):
        add_box(f"Rail{side}", mid + N * 0.15 + Vector((0, side * 0.62, 0)), (RAMP_LEN + 0.4, 0.08, 0.32), pitch, m_orange)
    for frac in (0.15, 0.7):
        top = A + D * (RAMP_LEN * frac) - N * 0.15
        h = top.z
        bpy.ops.mesh.primitive_cylinder_add(radius=0.07, depth=h, location=(top.x, 0, h / 2))
        bpy.context.object.data.materials.append(m_leg)

    # Ring, hängt an einer Stange von oben
    ring_pos, ring_tan = flight_point(T_RING)
    beta = math.atan2(ring_tan.x, ring_tan.z)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=RING_INNER + RING_MINOR, minor_radius=RING_MINOR,
        major_segments=96, minor_segments=24, location=ring_pos, rotation=(0, beta, 0))
    ring = bpy.context.object
    ring.name = "Ring"
    ring.data.materials.append(m_white)
    bpy.ops.object.shade_smooth()
    rod_bottom = ring_pos.z + RING_INNER + 2 * RING_MINOR
    bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=12, location=(ring_pos.x, 0, rod_bottom + 6))
    rod = bpy.context.object
    rod.data.materials.append(m_white)
    rod.parent = ring
    rod.matrix_parent_inverse = ring.matrix_world.inverted()

    # Schüssel an der Landestelle
    bowl_x = landing_x()
    verts = [(0.0, 0, 0.06), (0.55, 0, 0.06), (0.8, 0, 0.22), (0.95, 0, 0.62), (0.97, 0, 0.72)]
    me = bpy.data.meshes.new("BowlProfile")
    me.from_pydata(verts, [(i, i + 1) for i in range(len(verts) - 1)], [])
    bowl = bpy.data.objects.new("Bowl", me)
    sc.collection.objects.link(bowl)
    bowl.location = (bowl_x, 0, 0)
    scr = bowl.modifiers.new("screw", "SCREW")
    scr.axis = "Z"; scr.steps = 96; scr.render_steps = 96
    sol = bowl.modifiers.new("solid", "SOLIDIFY"); sol.thickness = 0.06
    sub = bowl.modifiers.new("sub", "SUBSURF"); sub.levels = 2; sub.render_levels = 2
    bowl.data.materials.append(m_bowl)
    for poly in bowl.data.polygons:
        poly.use_smooth = True

    # Berliner
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1)
    b = bpy.context.object
    b.name = "Berliner"
    for v in b.data.vertices:
        v.co.x *= RADIUS
        v.co.y *= RADIUS
        v.co.z *= HALF_H
    bpy.ops.object.shade_smooth()
    b.data.materials.append(berliner_material())

    # Licht
    def area(name, loc, power, size, target=(0, 0, 3.5)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        l = bpy.context.object
        l.name = name
        l.data.energy = power
        l.data.size = size
        direction = Vector(target) - Vector(loc)
        l.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    area("Key", (-6, -7, 10), 1300, 6)
    area("Fill", (6, -6, 3), 350, 5)
    area("Rim", (3, -1, 10), 700, 5)

    # Kamera hochkant
    bpy.ops.object.camera_add(location=(-4.6, -9.6, 6.4))
    cam = bpy.context.object
    cam.data.lens = 34
    cam.data.sensor_fit = "AUTO"
    direction = Vector((-0.2, 0, 3.75)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    return b, ring


# ---------- Bewegung ----------

def ramp_point(s):
    return A + D * s + N * HALF_H


def slide_time():
    return math.sqrt(2 * (RAMP_LEN - S0) / ACC)


def flight_point(t):
    v0 = ACC * slide_time()
    p0 = ramp_point(RAMP_LEN)
    vel = D * v0
    p = p0 + vel * t + Vector((0, 0, -0.5 * GRAV * t * t))
    tan = Vector((vel.x, 0, vel.z - GRAV * t)).normalized()
    return p, tan


def landing_t():
    target = BOWL_INNER_Z + HALF_H
    t = 0.0
    while flight_point(t)[0].z > target:
        t += 1 / 1000
    return t


def landing_x():
    return flight_point(landing_t())[0].x


def pitch_of(tan):
    return math.atan2(-tan.z, tan.x)


def bump(u, L):
    if abs(u) >= L:
        return 0.0
    return math.cos(math.pi * u / (2 * L)) ** 2


def soft_states(level):
    """Zustand pro Frame: (Position, Neigung, sx, sy, sz)."""
    pr = PARAMS[level]
    ring_pos, ring_tan = flight_point(T_RING)
    L = RADIUS + RING_MINOR + 0.05
    s_cross = (RING_INNER - 0.02) / RADIUS
    t_slide = slide_time()
    t_land = landing_t()
    dt = 1 / 240
    hold = 8 / FPS
    states = []
    t = 0.0
    tau = 0.0  # Flugzeit mit Zeitdehnung am Ring
    exit_tau = None
    land_t = None
    for f in range(SEG):
        target = f / FPS
        while t < target:
            t += dt
            if t > hold + t_slide and tau < t_land:
                p, tan = flight_point(tau)
                u = (p - ring_pos).dot(ring_tan)
                rate = 1 - (1 - pr["slow"]) * bump(u, L)
                tau = min(t_land, tau + dt * rate)
                if exit_tau is None and u > L:
                    exit_tau = tau
                if tau >= t_land and land_t is None:
                    land_t = t
        ts = target - hold
        if ts <= 0:
            pos, pitch, sx, sy, sz = ramp_point(S0), THETA, 1, 1, 1
        elif ts <= t_slide:
            pos, pitch, sx, sy, sz = ramp_point(S0 + 0.5 * ACC * ts * ts), THETA, 1, 1, 1
        elif land_t is None or target < land_t:
            pos, tan = flight_point(tau)
            pitch = pitch_of(tan)
            u = (pos - ring_pos).dot(ring_tan)
            cross = 1 - (1 - s_cross) * bump(u, L)
            if exit_tau is not None and tau > exit_tau:
                e = tau - exit_tau
                cross *= 1 + pr["wob_a"] * math.exp(-pr["wob_k"] * e) * math.sin(pr["wob_w"] * e)
            sx, sy, sz = 1 / cross ** 2, cross, cross
        else:
            e = target - land_t
            pos, tan = flight_point(t_land)
            settle = min(1.0, e / 0.12)
            pitch = pitch_of(tan) * (1 - settle)
            sz = pr["rest"] + (1 - pr["land_d"] - pr["rest"]) * math.exp(-pr["land_k"] * e) * math.cos(pr["land_w"] * e)
            sz = max(0.3, sz)
            sx = sy = 1 / math.sqrt(sz)
            pos = Vector((pos.x, 0, BOWL_INNER_Z + HALF_H * sz))
        states.append((pos.copy(), pitch, sx, sy, sz))
    return states


def hard_states():
    ring_pos, ring_tan = flight_point(T_RING)
    contact = -(RADIUS + RING_MINOR)
    t_slide = slide_time()
    hold = 8 / FPS
    dt = 1 / 240
    states = []
    phase = "ramp"
    t = 0.0
    tau = 0.0
    pos = ramp_point(S0)
    vz = 0.0
    pitch = THETA
    spin = 0.0
    squash_t = None
    bounces = 0
    rest_pitch = None
    for f in range(SEG):
        target = f / FPS
        while t < target:
            t += dt
            ts = t - hold
            if phase == "ramp":
                if ts > t_slide:
                    phase = "flight"
                else:
                    pos = ramp_point(S0 + 0.5 * ACC * max(0, ts) ** 2)
            if phase == "flight":
                tau += dt
                p, tan = flight_point(tau)
                if (p - ring_pos).dot(ring_tan) >= contact:
                    phase = "fall"
                    vz = 0.0
                    spin = -2.5
                    squash_t = t
                else:
                    pos, pitch = p, pitch_of(tan)
            elif phase == "fall":
                vz -= GRAV * dt
                pos = pos + Vector((-0.25 * dt, 0, vz * dt))
                pitch += spin * dt
                if pos.z <= HALF_H and vz < 0:
                    pos.z = HALF_H
                    bounces += 1
                    vz = -vz * 0.35
                    spin *= 0.3
                    squash_t = t
                    if rest_pitch is None:
                        rest_pitch = round(pitch / math.pi) * math.pi
                    if bounces >= 3 or vz < 0.4:
                        phase = "rest"
                        vz = 0
                if rest_pitch is not None:
                    pitch += (rest_pitch - pitch) * min(1, dt * 12)
            elif phase == "rest":
                pitch += (rest_pitch - pitch) * min(1, dt * 12)
        sz = 1.0
        if squash_t is not None:
            e = target - squash_t
            if e >= 0:
                sz = 1 - 0.07 * math.exp(-9 * e) * math.cos(30 * e)
        states.append((pos.copy(), pitch, 1 / math.sqrt(sz), 1 / math.sqrt(sz), sz))
    return states


def animate(b, ring):
    sc = bpy.context.scene
    sc.frame_start = 1
    sc.frame_end = SEG * len(LEVELS)
    ring_rest = ring.rotation_euler.copy()
    for li, level in enumerate(LEVELS):
        states = hard_states() if level == "hart" else soft_states(level)
        hit = None
        for f, (pos, pitch, sx, sy, sz) in enumerate(states):
            frame = li * SEG + f + 1
            b.location = pos
            b.rotation_euler = (0, pitch, 0)
            b.scale = (sx, sy, sz)
            b.keyframe_insert("location", frame=frame)
            b.keyframe_insert("rotation_euler", frame=frame)
            b.keyframe_insert("scale", frame=frame)
            ring_pos, ring_tan = flight_point(T_RING)
            near = (pos - ring_pos).length < RADIUS + RING_INNER
            if hit is None and near:
                hit = f
            amp = {"hart": 0.12, "weich": 0.05, "pudding": 0.02}[level]
            wig = 0.0
            if hit is not None:
                e = (f - hit) / FPS
                wig = amp * math.exp(-3 * e) * math.sin(11 * e)
            ring.rotation_euler = (ring_rest.x + wig, ring_rest.y, ring_rest.z)
            ring.keyframe_insert("rotation_euler", frame=frame)
    for o in (b, ring):
        if o.animation_data and o.animation_data.action:
            for layer in getattr(o.animation_data.action, "layers", []):
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        for fc in bag.fcurves:
                            for kp in fc.keyframe_points:
                                kp.interpolation = "LINEAR"


def setup_render(res, samples, out):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 16 / 9)
    sc.render.fps = FPS
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = out.rstrip("/") + "/f_"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "Medium High Contrast"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", type=int, default=720)
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--frames", default=None, help="z. B. 1-360 oder 40,150,300")
    a = ap.parse_args(argv)
    clear_scene()
    b, ring = build_scene()
    animate(b, ring)
    setup_render(a.res, a.samples, a.out)
    sc = bpy.context.scene
    if a.frames and "-" in a.frames:
        lo, hi = map(int, a.frames.split("-"))
        sc.frame_start, sc.frame_end = lo, hi
        bpy.ops.render.render(animation=True)
    elif a.frames:
        for fr in map(int, a.frames.split(",")):
            sc.frame_set(fr)
            sc.render.filepath = a.out.rstrip("/") + f"/f_{fr:04d}"
            bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
