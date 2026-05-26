import re

filepath = r'D:/codex/blenderchaj/spline_object_generator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# ===== 1. 在 offset_distance 之后、linked_duplicate 之前插入分组偏移属性 =====
marker = '    linked_duplicate: bpy.props.BoolProperty('
assert marker in content, "marker not found!"

insert_props = '''
    # ---- 分组偏移（HEADTAIL 模式专用）----
    head_use_offset: bpy.props.BoolProperty(
        name="头部启用偏移",
        default=False,
        update=lambda self, context: _schedule_preview(context),
    )
    head_offset_axis: bpy.props.EnumProperty(
        name="头部偏移轴",
        items=[
            ('LOCX', "局部 X", "沿头部模型自身局部 X 轴偏移"),
            ('LOCY', "局部 Y", "沿头部模型自身局部 Y 轴偏移"),
            ('LOCZ', "局部 Z", "沿头部模型自身局部 Z 轴偏移"),
            ('NORMAL', "曲线法线", "沿曲线局部法线方向偏移"),
        ],
        default='LOCX',
        update=lambda self, context: _schedule_preview(context),
    )
    head_offset_distance: bpy.props.FloatProperty(
        name="头部偏移距离",
        default=1.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
    )
    tail_use_offset: bpy.props.BoolProperty(
        name="尾部启用偏移",
        default=False,
        update=lambda self, context: _schedule_preview(context),
    )
    tail_offset_axis: bpy.props.EnumProperty(
        name="尾部偏移轴",
        items=[
            ('LOCX', "局部 X", "沿尾部模型自身局部 X 轴偏移"),
            ('LOCY', "局部 Y", "沿尾部模型自身局部 Y 轴偏移"),
            ('LOCZ', "局部 Z", "沿尾部模型自身局部 Z 轴偏移"),
            ('NORMAL', "曲线法线", "沿曲线局部法线方向偏移"),
        ],
        default='LOCX',
        update=lambda self, context: _schedule_preview(context),
    )
    tail_offset_distance: bpy.props.FloatProperty(
        name="尾部偏移距离",
        default=1.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
    )
    loop_use_offset: bpy.props.BoolProperty(
        name="循环体启用偏移",
        default=False,
        update=lambda self, context: _schedule_preview(context),
    )
    loop_offset_axis: bpy.props.EnumProperty(
        name="循环体偏移轴",
        items=[
            ('LOCX', "局部 X", "沿循环体自身局部 X 轴偏移"),
            ('LOCY', "局部 Y", "沿循环体自身局部 Y 轴偏移"),
            ('LOCZ', "局部 Z", "沿循环体自身局部 Z 轴偏移"),
            ('NORMAL', "曲线法线", "沿曲线局部法线方向偏移"),
        ],
        default='LOCX',
        update=lambda self, context: _schedule_preview(context),
    )
    loop_offset_distance: bpy.props.FloatProperty(
        name="循环体偏移距离",
        default=1.0, soft_min=-10.0, soft_max=10.0,
        subtype='DISTANCE',
        update=lambda self, context: _schedule_preview(context),
    )
'''

# 在 linked_duplicate 行之前插入
idx = content.index(marker)
content = content[:idx] + insert_props + '\n' + content[idx:]

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print('Step 1 done: properties inserted')
