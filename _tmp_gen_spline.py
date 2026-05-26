import os

filepath = r'D:/codex/blenderchaj/spline_object_generator.py'

lines = []
A = lines.append

A('bl_info = {')
A('    "name": "样条线生成器",')
A('    "author": "Your Name",')
A('    "version": (1, 5, 0),')
A('    "blender": (4, 0, 0),')
A('    "location": "View3D > Sidebar > 样条线生成",')
A('    "description": "沿样条线实时生成物体，支持缩放、间距、旋转与首尾模型，可绑定曲线实时跟随",')
A('    "category": "Object",')
A('}')
A('')
A('import bpy')
A('import math')
A('import random')
A('import hashlib')
A('from mathutils import Vector, Matrix, Quaternion')
A('')
A('')
A('# ---------------------------------------------------------------------------')
A('# 全局状态')
A('# ---------------------------------------------------------------------------')
A('_preview_timer = None')
A('_is_updating = False')
A('_bind_timer_active = False')
A('_last_curve_state = {}')
A('')
A('')

# ---------------------------------------------------------------------------
# PropertyGroups（按依赖顺序）
# ---------------------------------------------------------------------------
class SplineSourceItem(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(
        name="源物体",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
        update=lambda self, context: _schedule_preview(context),
    )


class GeneratedObjectItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()


class SplineGenProperties(bpy.types.PropertyGroup):
    target_curve: bpy.props.PointerProperty(
        name="目标曲线",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CURVE',
        update=lambda self, context: _on_curve_changed(context),
    )
    mode: bpy.props.EnumProperty(
        name="模式",
        items=[
            ('SINGLE', "单一物体", "只复制选中的一个物体"),
            ('MULTI',  "多个物体", "按顺序或随机使用多个源物体"),
        ],
        default='SINGLE',
        update=lambda self, context: _schedule_preview(context),
    )
    source_object: bpy.props.PointerProperty(
        name="源物体",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
        update=lambda self, context: _schedule_preview(context),
    )
    source_objects: bpy.props.CollectionProperty(type=SplineSourceItem)
    source_object_index: bpy.props.IntProperty(default=-1)
    multi_mode: bpy.props.EnumProperty(
        name="排列方式",
        items=[
            ('CYCLIC',  "循环",     "按顺序循环使用多个源物体"),
            ('RANDOM',  "随机",     "每次随机选择一个源物体"),
            ('HEADTAIL', "首尾模型", "头尾使用指定模型，中间循环"),
        ],
        default='CYCLIC',
        update=lambda self, context: _schedule_preview(context),
    )
    head_object: bpy.props.PointerProperty(
        name="头部模型",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
        update=lambda self, context: _schedule_preview(context),
    )
    tail_object: bpy.props.PointerProperty(
        name="尾部模型",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
        update=lambda self, context: _schedule_preview(context),
    )
    head_offset: bpy.props.FloatProperty(
        name="头部偏移",
        default=0.0, min=0.0, max=0.99,
        subtype='FACTOR',
        description="头部模型沿曲线向下的偏移比例（0=曲线起点）",
        update=lambda self, context: _schedule_preview(context),
    )
    tail_offset: bpy.props.FloatProperty(
        name="尾部偏移",
        default=0.0, min=0.0, max=0.99,
        subtype='FACTOR',
        description="尾部模型沿曲线向上的偏移比例（0=曲线终点）",
        update=lambda self, context: _schedule_preview(context),
    )
    count: bpy.props.IntProperty(
        name="数量",
        default=10, min=1, max=50000,
        update=lambda self, context: _schedule_preview(context),
    )
    spacing: bpy.props.FloatProperty(
        name="间距",
        default=0.0, min=0.0, max=10000.0, subtype='DISTANCE',
        description="物体之间的间隔（0 = 沿曲线均匀分布）",
        update=lambda self, context: _schedule_preview(context),
    )
    offset_start: bpy.props.FloatProperty(
        name="头部偏移",
        default=0.0, min=0.0, max=0.99,
        subtype='FACTOR',
        description="跳过曲线起始段的百分比",
        update=lambda self, context: _schedule_preview(context),
    )
    offset_end: bpy.props.FloatProperty(
        name="尾部偏移",
        default=0.0, min=0.0, max=0.99,
        subtype='FACTOR',
        description="跳过曲线结束段的百分比",
        update=lambda self, context: _schedule_preview(context),
    )
    follow_curve: bpy.props.BoolProperty(
        name="跟随曲线方向",
        default=True,
        update=lambda self, context: _schedule_preview(context),
    )
    random_rotation: bpy.props.FloatProperty(
        name="随机旋转",
        default=0.0, min=0.0, max=180.0, subtype='ANGLE',
        update=lambda self, context: _schedule_preview(context),
    )
    base_scale: bpy.props.FloatProperty(
        name="基础缩放",
        default=1.0, min=0.001, max=100.0,
        update=lambda self, context: _schedule_preview(context),
    )
    use_random_scale: bpy.props.BoolProperty(
        name="随机缩放",
        default=False,
        update=lambda self, context: _schedule_preview(context),
    )
    scale_min: bpy.props.FloatProperty(
        name="最小缩放",
        default=0.5, min=0.001, max=100.0,
        update=lambda self, context: _schedule_preview(context),
    )
    scale_max: bpy.props.FloatProperty(
        name="最大缩放",
        default=1.5, min=0.001, max=100.0,
        update=lambda self, context: _schedule_preview(context),
    )
    uniform_scale: bpy.props.BoolProperty(
        name="等比缩放",
        default=True,
        update=lambda self, context: _schedule_preview(context),
    )
    use_offset: bpy.props.BoolProperty(
        name="启用偏移",
        default=False,
        update=lambda self, context: _schedule_preview(context),
        description="将生成的物体沿指定方向偏移，不贴在曲线上",
    )
    offset_axis: bpy.props.EnumProperty(
        name="偏移轴",
        items=[
            ('LOCX', "局部 X", "沿物体自身局部 X 轴偏移（切线方向）"),
            ('LOCY', "局部 Y", "沿物体自身局部 Y 轴偏移（曲线右方）"),
            ('LOCZ', "局部 Z", "沿物体自身局部 Z 轴偏移（物体上方）"),
            ('NORMAL', "曲线法线", "沿曲线局部法线方向偏移"),
        ],
        default='LOCX',
        update=lambda self, context: _schedule_preview(context),
    )
    offset_distance: bpy.props.FloatProperty(
        name="偏移距离",
        default=1.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="偏移距离，正/负值控制方向",
    )
    linked_duplicate: bpy.props.BoolProperty(
        name="关联复制",
        default=True,
        update=lambda self, context: _schedule_preview(context),
    )
    auto_update: bpy.props.BoolProperty(
        name="实时预览",
        default=True,
        update=lambda self, context: _schedule_preview(context),
    )
    bind_to_curve: bpy.props.BoolProperty(
        name="绑定曲线",
        default=False,
        update=lambda self, context: _on_bind_toggle(context),
    )
    generated_objects: bpy.props.CollectionProperty(type=GeneratedObjectItem)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _get_curve_state_hash(curve_obj):
    try:
        data = curve_obj.data
        h = hashlib.md5()
        for spline in data.splines:
            h.update(spline.type.encode())
            if spline.type == 'BEZIER':
                for bp in spline.bezier_points:
                    for c in (bp.co, bp.handle_left, bp.handle_right):
                        h.update(f"{c.x:.4f},{c.y:.4f},{c.z:.4f}".encode())
            else:
                for p in spline.points:
                    h.update(f"{p.co.x:.4f},{p.co.y:.4f},{p.co.z:.4f},{p.co.w:.4f}".encode())
        h.update(f"resolu:{data.resolution_u}".encode())
        return h.hexdigest()
    except Exception:
        return None


def _sample_point_at_fraction(curve_obj, frac):
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(eval_obj)
    if len(mesh.edges) == 0 or len(mesh.vertices) == 0:
        bpy.data.meshes.remove(mesh)
        return None, None
    edge_map = {e.vertices[0]: e.vertices[1] for e in mesh.edges}
    if not edge_map:
        bpy.data.meshes.remove(mesh)
        return None, None
    start_v = list(edge_map.keys())[0]
    path_verts = [start_v]
    visited = {start_v}
    while start_v in edge_map:
        nxt = edge_map[start_v]
        if nxt in visited:
            break
        visited.add(nxt)
        path_verts.append(nxt)
        start_v = nxt
    lengths = []
    total = 0.0
    for i in range(len(path_verts) - 1):
        a = mesh.vertices[path_verts[i]].co
        b = mesh.vertices[path_verts[i + 1]].co
        L = (b - a).length
        lengths.append(L)
        total += L
    if total < 0.0001:
        bpy.data.meshes.remove(mesh)
        return None, None
    target_dist = frac * total
    d = 0.0
    pt_world = None
    tan_world = None
    mat = curve_obj.matrix_world
    mat3 = mat.to_3x3()
    for i in range(len(path_verts) - 1):
        a = mesh.vertices[path_verts[i]].co
        b = mesh.vertices[path_verts[i + 1]].co
        L = lengths[i]
        if d + L >= target_dist and L > 0.0001:
            t = (target_dist - d) / L
            pt = a.lerp(b, t)
            tan = (b - a).normalized()
            pt_world = mat @ pt
            tan_world = (mat3 @ tan).normalized()
            break
        d += L
    if pt_world is None:
        pt = mesh.vertices[path_verts[-1]].co
        pt_world = mat @ pt
        if len(path_verts) >= 2:
            a = mesh.vertices[path_verts[-2]].co
            b = mesh.vertices[path_verts[-1]].co
            tan_world = ((mat3 @ (b - a).normalized()).normalized())
        else:
            tan_world = Vector((1, 0, 0))
    bpy.data.meshes.remove(mesh)
    return pt_world, tan_world


def sample_curve(curve_obj, count, offset_start=0.0, offset_end=0.0):
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(eval_obj)
    if len(mesh.edges) == 0 or len(mesh.vertices) == 0:
        bpy.data.meshes.remove(mesh)
        return [], []
    edge_map = {e.vertices[0]: e.vertices[1] for e in mesh.edges}
    if not edge_map:
        bpy.data.meshes.remove(mesh)
        return [], []
    start_v = list(edge_map.keys())[0]
    path_verts = [start_v]
    visited = {start_v}
    while start_v in edge_map:
        nxt = edge_map[start_v]
        if nxt in visited:
            break
        visited.add(nxt)
        path_verts.append(nxt)
        start_v = nxt
    lengths = []
    total = 0.0
    for i in range(len(path_verts) - 1):
        a = mesh.vertices[path_verts[i]].co
        b = mesh.vertices[path_verts[i + 1]].co
        L = (b - a).length
        lengths.append(L)
        total += L
    if total < 0.0001:
        bpy.data.meshes.remove(mesh)
        return [], []
    s = total * offset_start
    e = total * (1.0 - offset_end)
    if e <= s:
        bpy.data.meshes.remove(mesh)
        return [], []
    points_world = []
    tangents_world = []
    mat = curve_obj.matrix_world
    mat3 = mat.to_3x3()
    def point_at(dist):
        d = 0.0
        for i in range(len(path_verts) - 1):
            a = mesh.vertices[path_verts[i]].co.copy()
            b = mesh.vertices[path_verts[i + 1]].co.copy()
            L = lengths[i]
            if d + L >= dist and L > 0.0001:
                t = (dist - d) / L
                pt = a.lerp(b, t)
                tan = (b - a).normalized()
                return pt, tan
            d += L
        pt = mesh.vertices[path_verts[-1]].co.copy()
        if len(path_verts) >= 2:
            a = mesh.vertices[path_verts[-2]].co
            b = mesh.vertices[path_verts[-1]].co
            tan = (b - a).normalized()
        else:
            tan = Vector((1, 0, 0))
        return pt, tan
    for i in range(count):
        t = i / max(count - 1, 1)
        dist = s + (e - s) * t
        pt, tan = point_at(dist)
        points_world.append(mat @ pt)
        tangents_world.append((mat3 @ tan).normalized())
    bpy.data.meshes.remove(mesh)
    return points_world, tangents_world


def sample_curve_by_distance(curve_obj, spacing, max_count,
                             offset_start=0.0, offset_end=0.0):
    if spacing <= 0.0001:
        return sample_curve(curve_obj, max_count, offset_start, offset_end)
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(eval_obj)
    if len(mesh.edges) == 0 or len(mesh.vertices) == 0:
        bpy.data.meshes.remove(mesh)
        return [], []
    edge_data = []
    total_length = 0.0
    for edge in mesh.edges:
        a = mesh.vertices[edge.vertices[0]].co.copy()
        b = mesh.vertices[edge.vertices[1]].co.copy()
        length = (b - a).length
        edge_data.append((a, b, length))
        total_length += length
    if total_length < 0.0001:
        bpy.data.meshes.remove(mesh)
        return [], []
    start_dist = total_length * offset_start
    end_dist = total_length * (1.0 - offset_end)
    if end_dist <= start_dist:
        bpy.data.meshes.remove(mesh)
        return [], []
    points_world = []
    tangents_world = []
    mat = curve_obj.matrix_world
    mat3 = mat.to_3x3()
    current_target = start_dist
    accumulated = 0.0
    for a, b, length in edge_data:
        if length < 0.0001:
            accumulated += length
            continue
        while (accumulated + length >= current_target
               and current_target <= end_dist
               and len(points_world) < max_count):
            local_t = (current_target - accumulated) / length
            pt = a.lerp(b, local_t)
            tan = (b - a).normalized()
            points_world.append(mat @ pt)
            tangents_world.append((mat3 @ tan).normalized())
            current_target += spacing
        accumulated += length
        if current_target > end_dist or len(points_world) >= max_count:
            break
    bpy.data.meshes.remove(mesh)
    return points_world, tangents_world


# ---------------------------------------------------------------------------
# 实时预览去抖
# ---------------------------------------------------------------------------
def _schedule_preview(context):
    global _preview_timer
    props = context.scene.spline_gen if hasattr(context.scene, 'spline_gen') else None
    if props is None or not props.auto_update:
        return
    if _preview_timer is not None:
        try:
            bpy.app.timers.unregister(_preview_timer)
        except ValueError:
            pass
    _preview_timer = bpy.app.timers.register(_do_preview, first_interval=0.15)


def _do_preview():
    global _preview_timer
    _preview_timer = None
    try:
        _generate_direct()
    except Exception:
        pass
    return None


def _on_curve_changed(context):
    global _last_curve_state
    _last_curve_state.clear()
    _schedule_preview(context)


def _on_bind_toggle(context):
    props = context.scene.spline_gen
    global _bind_timer_active
    if props.bind_to_curve:
        _last_curve_state.clear()
        _bind_timer_active = True
    else:
        _bind_timer_active = False


# ---------------------------------------------------------------------------
# 曲线绑定：timer 轮询
# ---------------------------------------------------------------------------
def _bind_timer_callback():
    global _last_curve_state, _is_updating, _bind_timer_active
    if not _bind_timer_active:
        return 0.1
    if _is_updating:
        return 0.1
    for scene in bpy.data.scenes:
        if not hasattr(scene, 'spline_gen'):
            continue
        props = scene.spline_gen
        if not props.bind_to_curve or props.target_curve is None:
            continue
        curve = props.target_curve
        if curve.type != 'CURVE':
            continue
        new_hash = _get_curve_state_hash(curve)
        obj_id = curve.as_pointer()
        old_hash = _last_curve_state.get(obj_id)
        if new_hash is not None and new_hash != old_hash:
            _last_curve_state[obj_id] = new_hash
            def _delayed_gen():
                try:
                    _generate_direct()
                except Exception:
                    pass
                return None
            bpy.app.timers.register(_delayed_gen, first_interval=0.05)
        _last_curve_state = {k: v for k, v in _last_curve_state.items()
                                 if bpy.data.objects.get(str(k)) is not None}
    return 0.1


# ---------------------------------------------------------------------------
# 直接生成
# ---------------------------------------------------------------------------
def _collect_source(props):
    if props.mode == 'SINGLE':
        obj = props.source_object
        if obj is None:
            return None
        return ([obj], False)
    src_list = [item.object for item in props.source_objects if item.object is not None]
    if not src_list:
        return None
    has_headtail = props.multi_mode == 'HEADTAIL'
    return (src_list, has_headtail)


def _clear_generated(props):
    global _is_updating
    _is_updating = True
    try:
        to_remove = [item.name for item in props.generated_objects]
        for name in to_remove:
            obj = bpy.data.objects.get(name)
            if obj is not None:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh and mesh.users == 0:
                    try:
                        if hasattr(mesh, 'type') and mesh.type == 'MESH':
                            bpy.data.meshes.remove(mesh)
                    except Exception:
                        pass
        props.generated_objects.clear()
    finally:
        _is_updating = False


def _generate_direct():
    global _is_updating
    if _is_updating:
        return
    for scene in bpy.data.scenes:
        if not hasattr(scene, 'spline_gen'):
            continue
        props = scene.spline_gen
        curve = props.target_curve
        if curve is None or curve.type != 'CURVE':
            continue
        result = _collect_source(props)
        if result is None:
            continue
        source_list, has_headtail = result
        offset_start = props.offset_start
        offset_end = props.offset_end
        if has_headtail:
            offset_start = props.head_offset
            offset_end = props.tail_offset
        points, tangents = sample_curve_by_distance(
            curve, props.spacing, props.count,
            offset_start, offset_end,
        )
        if not points:
            continue
        if has_headtail:
            if props.head_object is not None and points:
                pt, tan = _sample_point_at_fraction(curve, props.head_offset)
                if pt is not None:
                    points[0] = pt
                    tangents[0] = tan
            if props.tail_object is not None and points:
                tail_frac = max(props.head_offset + 0.001, 1.0 - props.tail_offset)
                pt, tan = _sample_point_at_fraction(curve, tail_frac)
                if pt is not None and len(points) > 1:
                    points[-1] = pt
                    tangents[-1] = tan
        _is_updating = True
        try:
            _clear_generated(props)
            _place_objects(props, source_list, points, tangents, has_headtail)
        finally:
            _is_updating = False
        break


def _place_objects(props, source_list, points, tangents, has_headtail=False):
    scene = bpy.context.scene
    generated = []

    for i, (pt, tan) in enumerate(zip(points, tangents)):
        if has_headtail:
            use_src = source_list[i % len(source_list)]
            if i == 0 and props.head_object is not None:
                use_src = props.head_object
            elif i == len(points) - 1 and props.tail_object is not None:
                use_src = props.tail_object
        else:
            if props.multi_mode == 'RANDOM':
                use_src = random.choice(source_list)
            else:
                use_src = source_list[i % len(source_list)]

        if props.linked_duplicate:
            new_obj = use_src.copy()
            new_obj.data = use_src.data
        else:
            new_obj = use_src.copy()
            new_obj.data = use_src.data.copy()

        # ① 先计算最终旋转四元数
        if props.follow_curve:
            # 沿切线方向，处理与 Z 轴平行的退化情况
            if abs(tan.z) > 0.9999:
                final_quat = tan.to_track_quat('X', 'Y')
            else:
                final_quat = tan.to_track_quat('X', 'Z')
        else:
            final_quat = use_src.rotation_quaternion.copy()

        if props.random_rotation > 0:
            rand_q = _random_rotation(math.radians(props.random_rotation))
            final_quat = final_quat @ rand_q

        # ② 偏移：沿局部轴或曲线法线
        offset_vec = Vector((0, 0, 0))
        if props.use_offset and props.offset_distance != 0.0:
            if props.offset_axis in ('LOCX', 'LOCY', 'LOCZ'):
                local_vec = Vector((0, 0, 0))
                if props.offset_axis == 'LOCX':
                    local_vec = Vector((props.offset_distance, 0.0, 0.0))
                elif props.offset_axis == 'LOCY':
                    local_vec = Vector((0.0, props.offset_distance, 0.0))
                else:
                    local_vec = Vector((0.0, 0.0, props.offset_distance))
                # 局部向量通过最终旋转转换到世界空间
                offset_vec = final_quat @ local_vec
            else:
                up = Vector((0.0, 0.0, 1.0))
                if abs(tan.dot(up)) > 0.999:
                    up = Vector((0.0, 1.0, 0.0))
                offset_vec = up.cross(tan).normalized() * props.offset_distance

        new_obj.location = pt + offset_vec
        new_obj.rotation_euler = final_quat.to_euler()

        scene.collection.objects.link(new_obj)
        generated.append(new_obj)

        # ③ 缩放
        bs = props.base_scale
        if props.use_random_scale:
            if props.uniform_scale:
                s = bs * random.uniform(props.scale_min, props.scale_max)
                new_obj.scale = (s, s, s)
            else:
                new_obj.scale = (
                    bs * random.uniform(props.scale_min, props.scale_max),
                    bs * random.uniform(props.scale_min, props.scale_max),
                    bs * random.uniform(props.scale_min, props.scale_max),
                )
        else:
            new_obj.scale = (bs, bs, bs)

    props.generated_objects.clear()
    for obj in generated:
        item = props.generated_objects.add()
        item.name = obj.name


def _random_rotation(max_angle_rad):
    axis = Vector((
        random.uniform(-1, 1),
        random.uniform(-1, 1),
        random.uniform(-1, 1),
    ))
    axis.normalize()
    angle = random.uniform(0, max_angle_rad)
    return Quaternion(axis, angle)



# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------
class SPLINE_OT_generate(bpy.types.Operator):
    bl_idname = "spline.generate"
    bl_label = "生成"
    bl_options = {'REGISTER', 'UNDO'}

    _report = True

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        global _is_updating
        if _is_updating:
            return {'CANCELLED'}

        props = context.scene.spline_gen
        curve = props.target_curve
        if curve is None or curve.type != 'CURVE':
            self.report({'ERROR'}, "请先设置目标曲线！")
            return {'CANCELLED'}

        result = _collect_source(props)
        if result is None:
            self.report({'ERROR'}, "请在面板中设置源物体！")
            return {'CANCELLED'}
        source_list, has_headtail = result

        offset_start = props.offset_start
        offset_end = props.offset_end
        if has_headtail:
            offset_start = props.head_offset
            offset_end = props.tail_offset

        points, tangents = sample_curve_by_distance(
            curve, props.spacing, props.count,
            offset_start, offset_end,
        )

        if not points:
            self.report({'ERROR'}, "无法从曲线采样到有效点，请检查曲线是否正常")
            return {'CANCELLED'}

        if has_headtail:
            if props.head_object is not None and points:
                pt, tan = _sample_point_at_fraction(curve, props.head_offset)
                if pt is not None:
                    points[0] = pt
                    tangents[0] = tan
            if props.tail_object is not None and len(points) > 1:
                tail_frac = max(props.head_offset + 0.001, 1.0 - props.tail_offset)
                pt, tan = _sample_point_at_fraction(curve, tail_frac)
                if pt is not None:
                    points[-1] = pt
                    tangents[-1] = tan

        _is_updating = True
        try:
            _clear_generated(props)
            _place_objects(props, source_list, points, tangents, has_headtail)
        finally:
            _is_updating = False

        if self._report:
            self.report({'INFO'}, f"已生成 {len(points)} 个物体")
        return {'FINISHED'}

    def invoke(self, context, event):
        self._report = False
        return self.execute(context)


class SPLINE_OT_clear(bpy.types.Operator):
    bl_idname = "spline.clear"
    bl_label = "清除"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.spline_gen
        _clear_generated(props)
        self.report({'INFO'}, "已清除生成物")
        return {'FINISHED'}


class SPLINE_OT_add_source_object(bpy.types.Operator):
    bl_idname = "spline.add_source_object"
    bl_label = "添加源物体"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        props = context.scene.spline_gen
        added = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                exists = any(item.object == obj for item in props.source_objects)
                if not exists:
                    item = props.source_objects.add()
                    item.object = obj
                    added += 1
        if added == 0:
            props.source_objects.add()
        if props.auto_update:
            try:
                bpy.ops.spline.generate('INVOKE_DEFAULT')
            except RuntimeError:
                pass
        return {'FINISHED'}


class SPLINE_OT_remove_source_object(bpy.types.Operator):
    bl_idname = "spline.remove_source_object"
    bl_label = "移除源物体"
    bl_options = {'INTERNAL', 'UNDO'}

    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        props = context.scene.spline_gen
        idx = self.index
        if 0 <= idx < len(props.source_objects):
            props.source_objects.remove(idx)
            if props.source_object_index >= len(props.source_objects):
                props.source_object_index = max(0, len(props.source_objects) - 1)
            if props.auto_update:
                try:
                    bpy.ops.spline.generate('INVOKE_DEFAULT')
                except RuntimeError:
                    pass
        return {'FINISHED'}



# ---------------------------------------------------------------------------
# UI Panel
# ---------------------------------------------------------------------------
class SPLINE_PT_generator_panel(bpy.types.Panel):
    bl_label = "样条线生成"
    bl_idname = "SPLINE_PT_generator_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "样条线生成"

    def draw(self, context):
        layout = self.layout
        props = context.scene.spline_gen

        row = layout.row(align=True)
        row.prop(props, "auto_update", toggle=True, icon='FILE_REFRESH')
        row.prop(props, "bind_to_curve", toggle=True, icon='CON_SPLINEIK')
        if not props.auto_update:
            layout.operator("spline.generate", text="生成")

        box = layout.box()
        box.label(text="目标曲线", icon='CURVE_BEZCURVE')
        box.prop(props, "target_curve", text="")

        box1 = layout.box()
        box1.label(text="模式", icon='OBJECT_DATA')
        box1.prop(props, "mode", text="")

        if props.mode == 'SINGLE':
            box1.prop(props, "source_object", text="源物体")
        else:
            box1.prop(props, "multi_mode", text="")
            if props.multi_mode == 'HEADTAIL':
                col = box1.column(align=True)
                col.prop(props, "head_object", text="头部模型")
                col.prop(props, "tail_object", text="尾部模型")
                col.separator()
                col.label(text="首尾偏移（沿曲线比例）:", icon='CON_SPLINEIK')
                col.prop(props, "head_offset", slider=True)
                col.prop(props, "tail_offset", slider=True)
                box1.label(text="提示：下方列表为中间的循环物体", icon='INFO')

            box1.label(text="循环物体列表:")
            col = box1.column(align=True)
            for i, item in enumerate(props.source_objects):
                row = col.row(align=True)
                row.prop(item, "object", text="")
                op = row.operator("spline.remove_source_object", text="", icon='X')
                op.index = i

            row = box1.row(align=True)
            row.operator("spline.add_source_object", text="添加", icon='ADD')
            if len(props.source_objects) > 0:
                row.operator("spline.remove_source_object", text="移除选中").index = props.source_object_index

        box2 = layout.box()
        box2.label(text="分布设置", icon='MOD_ARRAY')
        col = box2.column(align=True)
        col.prop(props, "count")
        col.prop(props, "spacing")
        if not (props.mode == 'MULTI' and props.multi_mode == 'HEADTAIL'):
            col.separator()
            col.prop(props, "offset_start")
            col.prop(props, "offset_end")

        box_offset = layout.box()
        box_offset.label(text="偏移", icon='CON_LOCLIKE')
        col = box_offset.column(align=True)
        col.prop(props, "use_offset", toggle=True)
        if props.use_offset:
            col.prop(props, "offset_axis", text="")
            col.prop(props, "offset_distance")

        box3 = layout.box()
        box3.label(text="旋转", icon='ORIENTATION_GIMBAL')
        box3.prop(props, "follow_curve")
        box3.prop(props, "random_rotation")

        box4 = layout.box()
        box4.label(text="缩放", icon='FULLSCREEN_ENTER')
        box4.prop(props, "base_scale")
        box4.prop(props, "use_random_scale")
        if props.use_random_scale:
            col = box4.column(align=True)
            col.prop(props, "scale_min")
            col.prop(props, "scale_max")
            box4.prop(props, "uniform_scale")

        box5 = layout.box()
        box5.label(text="克隆", icon='DUPLICATE')
        box5.prop(props, "linked_duplicate")

        layout.separator()
        layout.operator("spline.clear", icon='TRASH')


def draw_menu(self, context):
    self.layout.separator()
    self.layout.operator("spline.generate")
    self.layout.operator("spline.clear")



# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
classes = [
    SplineSourceItem,
    GeneratedObjectItem,
    SplineGenProperties,
    SPLINE_OT_generate,
    SPLINE_OT_clear,
    SPLINE_OT_add_source_object,
    SPLINE_OT_remove_source_object,
    SPLINE_PT_generator_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.spline_gen = bpy.props.PointerProperty(type=SplineGenProperties)
    bpy.types.VIEW3D_MT_object.append(draw_menu)

    global _bind_timer_active
    _bind_timer_active = False
    bpy.app.timers.register(_bind_timer_callback, first_interval=0.2)


def unregister():
    global _bind_timer_active
    _bind_timer_active = False

    global _preview_timer, _last_curve_state
    if _preview_timer is not None:
        try:
            bpy.app.timers.unregister(_preview_timer)
        except ValueError:
            pass
        _preview_timer = None
    _last_curve_state.clear()

    bpy.types.VIEW3D_MT_object.remove(draw_menu)
    del bpy.types.Scene.spline_gen

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

