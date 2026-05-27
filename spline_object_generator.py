bl_info = {
    "name": "样条线生成器",
    "author": "Your Name",
    "version": (1, 12, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > 样条线生成",
    "description": "沿样条线实时生成物体，支持多段样条线分段处理，支持缩放、间距、旋转与首尾模型，头部/尾部/基础缩放均支持三轴独立控制，可绑定曲线实时跟随",
    "category": "Object",
}

import bpy
import math
import random
import hashlib
from mathutils import Vector, Matrix, Quaternion, Euler


# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
_preview_timer = None
_is_updating = False
_bind_timer_active = False
_last_curve_state = {}


class SplineSourceItem(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(
        name="源物体",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
        update=lambda self, context: _schedule_preview(context),
    )


class GeneratedObjectItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()


class SplineTargetItem(bpy.types.PropertyGroup):
    curve: bpy.props.PointerProperty(
        name="曲线",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CURVE',
        update=lambda self, context: _on_curve_changed(context),
    )


class SplineGenProperties(bpy.types.PropertyGroup):
    target_curves: bpy.props.CollectionProperty(type=SplineTargetItem)
    target_curve_index: bpy.props.IntProperty(default=-1)

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
    head_rotation: bpy.props.FloatVectorProperty(
        name="头部旋转",
        default=(0.0, 0.0, 0.0),
        subtype='EULER',
        description="头部模型的固定旋转（欧拉角）",
        update=lambda self, context: _schedule_preview(context),
    )
    head_scale: bpy.props.FloatVectorProperty(
        name="头部缩放",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.001, max=100.0,
        subtype='XYZ',
        description="头部模型的固定缩放（X, Y, Z 独立）",
        update=lambda self, context: _schedule_preview(context),
    )
    tail_offset: bpy.props.FloatProperty(
        name="尾部偏移",
        default=0.0, min=0.0, max=0.99,
        subtype='FACTOR',
        description="尾部模型沿曲线向上的偏移比例（0=曲线终点）",
        update=lambda self, context: _schedule_preview(context),
    )
    tail_rotation: bpy.props.FloatVectorProperty(
        name="尾部旋转",
        default=(0.0, 0.0, 0.0),
        subtype='EULER',
        description="尾部模型的固定旋转（欧拉角）",
        update=lambda self, context: _schedule_preview(context),
    )
    tail_scale: bpy.props.FloatVectorProperty(
        name="尾部缩放",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.001, max=100.0,
        subtype='XYZ',
        description="尾部模型的固定缩放（X, Y, Z 独立）",
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
    base_scale: bpy.props.FloatVectorProperty(
        name="基础缩放",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.001, max=100.0,
        subtype='XYZ',
        description="循环体的基础缩放（X, Y, Z 独立）",
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
    offset_x: bpy.props.FloatProperty(
        name="X",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="沿物体局部 X 轴偏移",
    )
    offset_y: bpy.props.FloatProperty(
        name="Y",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="沿物体局部 Y 轴偏移",
    )
    offset_z: bpy.props.FloatProperty(
        name="Z",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="沿物体局部 Z 轴偏移",
    )

    # ---- 分组偏移（HEADTAIL 模式专用）----
    head_use_offset: bpy.props.BoolProperty(
        name="头部启用偏移",
        default=False,
        update=lambda self, context: _schedule_preview(context),
    )
    head_offset_x: bpy.props.FloatProperty(
        name="X",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="头部模型局部 X 轴偏移",
    )
    head_offset_y: bpy.props.FloatProperty(
        name="Y",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="头部模型局部 Y 轴偏移",
    )
    head_offset_z: bpy.props.FloatProperty(
        name="Z",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="头部模型局部 Z 轴偏移",
    )
    tail_use_offset: bpy.props.BoolProperty(
        name="尾部启用偏移",
        default=False,
        update=lambda self, context: _schedule_preview(context),
    )
    tail_offset_x: bpy.props.FloatProperty(
        name="X",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="尾部模型局部 X 轴偏移",
    )
    tail_offset_y: bpy.props.FloatProperty(
        name="Y",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="尾部模型局部 Y 轴偏移",
    )
    tail_offset_z: bpy.props.FloatProperty(
        name="Z",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="尾部模型局部 Z 轴偏移",
    )
    loop_use_offset: bpy.props.BoolProperty(
        name="循环体启用偏移",
        default=False,
        update=lambda self, context: _schedule_preview(context),
    )
    loop_offset_x: bpy.props.FloatProperty(
        name="X",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="循环体局部 X 轴偏移",
    )
    loop_offset_y: bpy.props.FloatProperty(
        name="Y",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="循环体局部 Y 轴偏移",
    )
    loop_offset_z: bpy.props.FloatProperty(
        name="Z",
        default=0.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
        description="循环体局部 Z 轴偏移",
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

def _get_all_chains(mesh):
    """从曲线转换的网格中提取所有断开的顶点链，每条链对应一个样条线。
    返回链列表，每条链是沿样条线顺序排列的顶点索引列表。
    """
    if len(mesh.edges) == 0:
        return []

    # 构建邻接表
    adj = {}
    for e in mesh.edges:
        a, b = e.vertices[0], e.vertices[1]
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    if not adj:
        return []

    visited = set()
    chains = []

    # 第一遍：处理开放链（存在度为 1 的端点）
    for v in list(adj.keys()):
        if v in visited:
            continue
        if len(adj[v]) != 1:
            continue
        chain = []
        current = v
        prev = None
        while current not in visited:
            chain.append(current)
            visited.add(current)
            nxts = [n for n in adj[current] if n != prev]
            if not nxts:
                break
            prev, current = current, nxts[0]
        if chain:
            chains.append(chain)

    # 第二遍：处理闭合环（剩余未访问的顶点，度均为 2）
    for v in list(adj.keys()):
        if v in visited:
            continue
        chain = []
        current = v
        prev = None
        while current not in visited:
            chain.append(current)
            visited.add(current)
            nxts = [n for n in adj[current] if n != prev]
            if not nxts:
                break
            prev, current = current, nxts[0]
        if chain:
            chains.append(chain)

    return chains


def _sample_chain(mesh, chain, mat, mat3):
    """对一条链预处理 edge_data 和 lengths，返回 (edge_data, lengths, total_length)。"""
    if len(chain) < 2:
        return None
    edge_data = []
    lengths = []
    total = 0.0
    for i in range(len(chain) - 1):
        a = mesh.vertices[chain[i]].co.copy()
        b = mesh.vertices[chain[i + 1]].co.copy()
        L = (b - a).length
        edge_data.append((a, b))
        lengths.append(L)
        total += L
    if total < 0.0001:
        return None
    return (edge_data, lengths, total)


def _sample_point_on_chain(edge_data, lengths, total_length, dist_on_chain, mat, mat3):
    """在一条链上按距离 dist_on_chain 采样点和切线，返回 (pt_world, tan_world)。"""
    dd = 0.0
    for j in range(len(edge_data)):
        a, b = edge_data[j]
        L = lengths[j]
        if dd + L >= dist_on_chain and L > 0.0001:
            t = (dist_on_chain - dd) / L
            pt = a.lerp(b, t)
            tan = (b - a).normalized()
            return mat @ pt, (mat3 @ tan).normalized()
        dd += L
    # 落在链末尾之后：返回末端点
    a, b = edge_data[-1]
    return mat @ b, (mat3 @ (b - a).normalized()).normalized()


def sample_curve_by_distance(curve_obj, spacing, max_count,
                             offset_start=0.0, offset_end=0.0):
    """对曲线对象的每条样条线独立按距离采样，分段处理。
    每条样条线都应用相同的 spacing/count 参数。
    返回列表，每个元素是单条链的 (points, tangents)。
    """
    if spacing <= 0.0001:
        return sample_curve(curve_obj, max_count, offset_start, offset_end)

    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(eval_obj)
    mat = curve_obj.matrix_world
    mat3 = mat.to_3x3()

    chains = _get_all_chains(mesh)
    if not chains:
        bpy.data.meshes.remove(mesh)
        return []

    results = []

    for chain in chains:
        result = _sample_chain(mesh, chain, mat, mat3)
        if result is None:
            continue
        edge_data, lengths, total_length = result

        start_dist = total_length * offset_start
        end_dist = total_length * (1.0 - offset_end)
        if end_dist <= start_dist:
            continue

        pts = []
        tans = []
        current_dist = start_dist
        count_this_chain = 0

        while current_dist <= end_dist and count_this_chain < max_count:
            dd = 0.0
            placed = False
            for j in range(len(edge_data)):
                a, b = edge_data[j]
                L = lengths[j]
                if L < 0.0001:
                    dd += L
                    continue
                if dd + L >= current_dist:
                    t = (current_dist - dd) / L
                    pt = a.lerp(b, t)
                    tan = (b - a).normalized()
                    pts.append(mat @ pt)
                    tans.append((mat3 @ tan).normalized())
                    count_this_chain += 1
                    placed = True
                    break
                dd += L

            if not placed:
                break

            current_dist += spacing

        results.append((pts, tans))

    bpy.data.meshes.remove(mesh)
    return results


def sample_curve_headtail_by_distance(curve_obj, spacing, max_count,
                                     head_offset=0.0, tail_offset=0.0):
    """HEADTAIL 模式专用：头尾固定，只调整中间循环体间距。
    头部始终在 head_offset 位置，尾部始终在 (1.0-tail_offset) 位置，
    中间循环体按 spacing 间距放置。
    """
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(eval_obj)
    mat = curve_obj.matrix_world
    mat3 = mat.to_3x3()

    chains = _get_all_chains(mesh)
    if not chains:
        bpy.data.meshes.remove(mesh)
        return []

    results = []

    for chain in chains:
        result = _sample_chain(mesh, chain, mat, mat3)
        if result is None:
            continue
        edge_data, lengths, total_length = result

        # 头尾固定位置
        head_dist = total_length * head_offset
        tail_dist = total_length * (1.0 - tail_offset)
        if tail_dist <= head_dist:
            continue

        pts = []
        tans = []

        # 头部固定
        pt_world, tan_world = _sample_point_on_chain(edge_data, lengths, total_length, head_dist, mat, mat3)
        if pt_world is not None:
            pts.append(pt_world)
            tans.append(tan_world)

        # 中间循环体按间距放置
        if spacing > 0.0001:
            current_dist = head_dist + spacing
            count_loop = 0
            # max_count 只表示循环体数量（头尾额外固定放置）
            while current_dist < tail_dist and count_loop < max_count:
                pt_world, tan_world = _sample_point_on_chain(edge_data, lengths, total_length, current_dist, mat, mat3)
                if pt_world is not None:
                    pts.append(pt_world)
                    tans.append(tan_world)
                    count_loop += 1
                current_dist += spacing

        # 尾部固定
        pt_world, tan_world = _sample_point_on_chain(edge_data, lengths, total_length, tail_dist, mat, mat3)
        if pt_world is not None:
            # 避免与头部重合
            if len(pts) == 0 or (pt_world - pts[-1]).length > 0.0001:
                pts.append(pt_world)
                tans.append(tan_world)

        results.append((pts, tans))

    bpy.data.meshes.remove(mesh)
    return results


def sample_curve(curve_obj, count, offset_start=0.0, offset_end=0.0):
    """对曲线对象的每条样条线独立均匀采样 count 个点，分段处理。
    每条样条线采样 count 个点（不是总共 count 个）。
    返回列表，每个元素是单条链的 (points, tangents)。
    """
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(eval_obj)
    mat = curve_obj.matrix_world
    mat3 = mat.to_3x3()

    chains = _get_all_chains(mesh)
    if not chains:
        bpy.data.meshes.remove(mesh)
        return []

    results = []

    for chain in chains:
        result = _sample_chain(mesh, chain, mat, mat3)
        if result is None:
            continue
        edge_data, lengths, total_length = result

        s = total_length * offset_start
        e = total_length * (1.0 - offset_end)
        if e <= s:
            continue

        pts = []
        tans = []
        for i in range(count):
            t_frac = i / max(count - 1, 1)
            target_dist = s + (e - s) * t_frac
            pt_world, tan_world = _sample_point_on_chain(
                edge_data, lengths, total_length, target_dist, mat, mat3
            )
            pts.append(pt_world)
            tans.append(tan_world)

        results.append((pts, tans))

    bpy.data.meshes.remove(mesh)
    return results


def _sample_point_at_fraction(curve_obj, frac):
    """在曲线上按百分比 frac（0~1，跨所有样条线合并长度）采样点和切线。
    用于首尾模型定位。
    """
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(eval_obj)

    chains = _get_all_chains(mesh)
    if not chains:
        bpy.data.meshes.remove(mesh)
        return None, None

    # 计算每条链的长度，以及所有链的总长度
    chain_data = []  # 每个元素: (edge_data, lengths, total_length)
    total_all = 0.0
    mat = curve_obj.matrix_world
    mat3 = mat.to_3x3()

    for chain in chains:
        result = _sample_chain(mesh, chain, mat, mat3)
        if result is None:
            continue
        edge_data, lengths, total = result
        chain_data.append((edge_data, lengths, total))
        total_all += total

    if total_all < 0.0001:
        bpy.data.meshes.remove(mesh)
        return None, None

    target_dist = frac * total_all
    accumulated = 0.0

    for edge_data, lengths, chain_total in chain_data:
        if accumulated + chain_total >= target_dist or edge_data == chain_data[-1][0]:
            local_d = target_dist - accumulated
            pt_world, tan_world = _sample_point_on_chain(
                edge_data, lengths, chain_total, local_d, mat, mat3
            )
            bpy.data.meshes.remove(mesh)
            return pt_world, tan_world
        accumulated += chain_total

    # 超出范围：返回最后一个链的末端点
    if chain_data:
        edge_data, lengths, chain_total = chain_data[-1]
        pt_world, tan_world = _sample_point_on_chain(
            edge_data, lengths, chain_total, chain_total, mat, mat3
        )
        bpy.data.meshes.remove(mesh)
        return pt_world, tan_world

    bpy.data.meshes.remove(mesh)
    return None, None


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
        # 同时检测物体的位置/旋转/缩放变化
        loc = curve_obj.location
        rot = curve_obj.rotation_euler
        scl = curve_obj.scale
        h.update(f"loc:{loc.x:.4f},{loc.y:.4f},{loc.z:.4f}".encode())
        h.update(f"rot:{rot.x:.4f},{rot.y:.4f},{rot.z:.4f}".encode())
        h.update(f"scl:{scl.x:.4f},{scl.y:.4f},{scl.z:.4f}".encode())
        return h.hexdigest()
    except Exception:
        return None


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
    changed = False
    for scene in bpy.data.scenes:
        if not hasattr(scene, 'spline_gen'):
            continue
        props = scene.spline_gen
        if not props.bind_to_curve:
            continue
        for item in props.target_curves:
            curve = item.curve
            if curve is None or curve.type != 'CURVE':
                continue
            new_hash = _get_curve_state_hash(curve)
            obj_id = curve.as_pointer()
            old_hash = _last_curve_state.get(obj_id)
            if new_hash is not None and new_hash != old_hash:
                _last_curve_state[obj_id] = new_hash
                changed = True
    if changed:
        def _delayed_gen():
            try:
                _generate_direct()
            except Exception:
                pass
            return None
        bpy.app.timers.register(_delayed_gen, first_interval=0.05)
    # 清理已不存在对象的哈希
    existing_ids = {obj.as_pointer() for obj in bpy.data.objects}
    _last_curve_state = {k: v for k, v in _last_curve_state.items() if k in existing_ids}
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
        curves = [item.curve for item in props.target_curves
                  if item.curve is not None and item.curve.type == 'CURVE']
        if not curves:
            continue
        result = _collect_source(props)
        if result is None:
            continue
        source_list, has_headtail = result

        _is_updating = True
        try:
            _clear_generated(props)
            total_count = 0
            for curve in curves:
                if has_headtail:
                    chain_results = sample_curve_headtail_by_distance(
                        curve, props.spacing, props.count,
                        props.head_offset, props.tail_offset,
                    )
                else:
                    offset_start = props.offset_start
                    offset_end = props.offset_end
                    chain_results = sample_curve_by_distance(
                        curve, props.spacing, props.count,
                        offset_start, offset_end,
                    )
                for pts, tans in chain_results:
                    if not pts:
                        continue
                    _place_objects(props, source_list, pts, tans, has_headtail)
                    total_count += len(pts)
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
            if abs(tan.z) > 0.9999:
                final_quat = tan.to_track_quat('X', 'Y')
            else:
                final_quat = tan.to_track_quat('X', 'Z')
        else:
            final_quat = use_src.rotation_quaternion.copy()

        is_head = (has_headtail and i == 0 and props.head_object is not None)
        is_tail = (has_headtail and i == len(points) - 1 and props.tail_object is not None)

        if is_head:
            # 头部模型：应用固定旋转，不参与随机旋转
            head_euler = Euler(props.head_rotation)
            final_quat = final_quat @ head_euler.to_quaternion()
        elif is_tail:
            # 尾部模型：应用固定旋转，不参与随机旋转
            tail_euler = Euler(props.tail_rotation)
            final_quat = final_quat @ tail_euler.to_quaternion()
        elif props.random_rotation > 0:
            rand_q = _random_rotation(math.radians(props.random_rotation))
            final_quat = final_quat @ rand_q

        # ② 偏移：根据模型类型使用对应的偏移设置
        offset_vec = Vector((0, 0, 0))
        is_head = (has_headtail and i == 0 and props.head_object is not None)
        is_tail = (has_headtail and i == len(points) - 1 and props.tail_object is not None)
        is_loop = not (is_head or is_tail)

        use_off = False
        off_x, off_y, off_z = 0.0, 0.0, 0.0

        if is_head and props.head_use_offset:
            use_off = True
            off_x = props.head_offset_x
            off_y = props.head_offset_y
            off_z = props.head_offset_z
        elif is_tail and props.tail_use_offset:
            use_off = True
            off_x = props.tail_offset_x
            off_y = props.tail_offset_y
            off_z = props.tail_offset_z
        elif is_loop and props.loop_use_offset:
            use_off = True
            off_x = props.loop_offset_x
            off_y = props.loop_offset_y
            off_z = props.loop_offset_z
        elif not has_headtail and props.use_offset:
            use_off = True
            off_x = props.offset_x
            off_y = props.offset_y
            off_z = props.offset_z

        if use_off and (off_x != 0.0 or off_y != 0.0 or off_z != 0.0):
            local_vec = Vector((off_x, off_y, off_z))
            offset_vec = final_quat @ local_vec

        new_obj.location = pt + offset_vec
        new_obj.rotation_euler = final_quat.to_euler()

        scene.collection.objects.link(new_obj)
        generated.append(new_obj)

        # ③ 缩放
        is_head = (has_headtail and i == 0 and props.head_object is not None)
        is_tail = (has_headtail and i == len(points) - 1 and props.tail_object is not None)

        if is_head:
            # 头部模型：使用独立三轴缩放，不参与随机缩放
            new_obj.scale = props.head_scale[:]
        elif is_tail:
            # 尾部模型：使用独立三轴缩放，不参与随机缩放
            new_obj.scale = props.tail_scale[:]
        else:
            # 循环体：使用基础三轴缩放，可叠加随机缩放
            bs = props.base_scale
            if props.use_random_scale:
                if props.uniform_scale:
                    r = random.uniform(props.scale_min, props.scale_max)
                    new_obj.scale = (bs[0] * r, bs[1] * r, bs[2] * r)
                else:
                    new_obj.scale = (
                        bs[0] * random.uniform(props.scale_min, props.scale_max),
                        bs[1] * random.uniform(props.scale_min, props.scale_max),
                        bs[2] * random.uniform(props.scale_min, props.scale_max),
                    )
            else:
                new_obj.scale = bs[:]

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
        curves = [item.curve for item in props.target_curves
                  if item.curve is not None and item.curve.type == 'CURVE']
        if not curves:
            self.report({'ERROR'}, "请先设置目标曲线！")
            return {'CANCELLED'}

        result = _collect_source(props)
        if result is None:
            self.report({'ERROR'}, "请在面板中设置源物体！")
            return {'CANCELLED'}
        source_list, has_headtail = result

        _is_updating = True
        try:
            _clear_generated(props)
            total_count = 0
            for curve in curves:
                if has_headtail:
                    chain_results = sample_curve_headtail_by_distance(
                        curve, props.spacing, props.count,
                        props.head_offset, props.tail_offset,
                    )
                else:
                    offset_start = props.offset_start
                    offset_end = props.offset_end
                    chain_results = sample_curve_by_distance(
                        curve, props.spacing, props.count,
                        offset_start, offset_end,
                    )

                for pts, tans in chain_results:
                    if not pts:
                        continue
                    _place_objects(props, source_list, pts, tans, has_headtail)
                    total_count += len(pts)
        finally:
            _is_updating = False

        if self._report:
            self.report({'INFO'}, f"已生成 {total_count} 个物体")
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


class SPLINE_OT_add_target_curve(bpy.types.Operator):
    bl_idname = "spline.add_target_curve"
    bl_label = "添加目标曲线"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        props = context.scene.spline_gen
        added = 0
        for obj in context.selected_objects:
            if obj.type == 'CURVE':
                exists = any(item.curve == obj for item in props.target_curves)
                if not exists:
                    item = props.target_curves.add()
                    item.curve = obj
                    added += 1
        if added == 0:
            props.target_curves.add()
        _schedule_preview(context)
        return {'FINISHED'}


class SPLINE_OT_remove_target_curve(bpy.types.Operator):
    bl_idname = "spline.remove_target_curve"
    bl_label = "移除目标曲线"
    bl_options = {'INTERNAL', 'UNDO'}

    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        props = context.scene.spline_gen
        idx = self.index
        if 0 <= idx < len(props.target_curves):
            props.target_curves.remove(idx)
            if props.target_curve_index >= len(props.target_curves):
                props.target_curve_index = max(0, len(props.target_curves) - 1)
            _schedule_preview(context)
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
        col = box.column(align=True)
        for i, item in enumerate(props.target_curves):
            row = col.row(align=True)
            row.prop(item, "curve", text="")
            op = row.operator("spline.remove_target_curve", text="", icon='X')
            op.index = i
        row = box.row(align=True)
        row.operator("spline.add_target_curve", text="添加", icon='ADD')
        if len(props.target_curves) > 0:
            row.operator("spline.remove_target_curve", text="移除选中").index = props.target_curve_index

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
                col.prop(props, "head_rotation", text="头部旋转")
                col.prop(props, "head_scale", text="头部缩放")
                col.separator()
                col.prop(props, "tail_object", text="尾部模型")
                col.prop(props, "tail_rotation", text="尾部旋转")
                col.prop(props, "tail_scale", text="尾部缩放")
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

        # ---- 偏移面板 ----
        box_offset = layout.box()
        box_offset.label(text="偏移", icon='CON_LOCLIKE')

        if props.mode == 'MULTI' and props.multi_mode == 'HEADTAIL':
            col = box_offset.column(align=True)
            col.label(text="头部模型偏移:", icon='CON_SPLINEIK')
            col.prop(props, "head_use_offset", toggle=True)
            if props.head_use_offset:
                col.prop(props, "head_offset_x")
                col.prop(props, "head_offset_y")
                col.prop(props, "head_offset_z")

            col = box_offset.column(align=True)
            col.label(text="尾部模型偏移:", icon='CON_SPLINEIK')
            col.prop(props, "tail_use_offset", toggle=True)
            if props.tail_use_offset:
                col.prop(props, "tail_offset_x")
                col.prop(props, "tail_offset_y")
                col.prop(props, "tail_offset_z")

            col = box_offset.column(align=True)
            col.label(text="循环体偏移:", icon='CON_SPLINEIK')
            col.prop(props, "loop_use_offset", toggle=True)
            if props.loop_use_offset:
                col.prop(props, "loop_offset_x")
                col.prop(props, "loop_offset_y")
                col.prop(props, "loop_offset_z")
        else:
            col = box_offset.column(align=True)
            col.prop(props, "use_offset", toggle=True)
            if props.use_offset:
                col.prop(props, "offset_x")
                col.prop(props, "offset_y")
                col.prop(props, "offset_z")

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
    SplineTargetItem,
    SplineGenProperties,
    SPLINE_OT_generate,
    SPLINE_OT_clear,
    SPLINE_OT_add_source_object,
    SPLINE_OT_remove_source_object,
    SPLINE_OT_add_target_curve,
    SPLINE_OT_remove_target_curve,
    SPLINE_PT_generator_panel,
]


def _migrate_scale_props():
    """修复从 FloatProperty 迁移到 FloatVectorProperty 后的数据问题。
    旧版本保存的单值会被映射到向量第一个分量，YZ 分量可能变成 0，
    导致模型消失或显示异常。
    """
    for scene in bpy.data.scenes:
        if not hasattr(scene, 'spline_gen'):
            continue
        props = scene.spline_gen
        for attr_name in ('head_scale', 'tail_scale', 'base_scale'):
            try:
                val = getattr(props, attr_name)
                # 如果 Y 或 Z 分量接近 0（违反 min=0.001），说明是旧数据迁移
                if val[1] < 0.0001 or val[2] < 0.0001:
                    # 将 X 的值同步到 YZ，保持用户旧设置的等比缩放
                    x = max(val[0], 0.001)
                    setattr(props, attr_name, (x, x, x))
            except Exception:
                pass


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.spline_gen = bpy.props.PointerProperty(type=SplineGenProperties)

    # 修复旧版本数据迁移导致的缩放值异常（延迟到注册完成后执行）
    def _delayed_migrate():
        try:
            _migrate_scale_props()
        except Exception:
            pass
        return None
    bpy.app.timers.register(_delayed_migrate, first_interval=0.1)

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
