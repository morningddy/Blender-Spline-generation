filepath = r'D:/codex/blenderchaj/spline_object_generator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 偏移逻辑块在 679-696 行（1-indexed），即 678-695（0-indexed）
# 替换为新的分组偏移逻辑
new_offset_block = '''        # ② 偏移：根据模型类型使用对应的偏移设置
        offset_vec = Vector((0, 0, 0))
        # 判断当前模型类型
        is_head = (has_headtail and i == 0 and props.head_object is not None)
        is_tail = (has_headtail and i == len(points) - 1 and props.tail_object is not None)
        is_loop = not (is_head or is_tail)

        # 选择合适的偏移参数
        use_off = False
        off_axis = 'LOCX'
        off_dist = 0.0

        if is_head and props.head_use_offset:
            use_off = True
            off_axis = props.head_offset_axis
            off_dist = props.head_offset_distance
        elif is_tail and props.tail_use_offset:
            use_off = True
            off_axis = props.tail_offset_axis
            off_dist = props.tail_offset_distance
        elif is_loop and props.loop_use_offset:
            use_off = True
            off_axis = props.loop_offset_axis
            off_dist = props.loop_offset_distance
        elif not has_headtail and props.use_offset:
            use_off = True
            off_axis = props.offset_axis
            off_dist = props.offset_distance

        if use_off and off_dist != 0.0:
            if off_axis in ('LOCX', 'LOCY', 'LOCZ'):
                local_vec = Vector((0, 0, 0))
                if off_axis == 'LOCX':
                    local_vec = Vector((off_dist, 0.0, 0.0))
                elif off_axis == 'LOCY':
                    local_vec = Vector((0.0, off_dist, 0.0))
                else:
                    local_vec = Vector((0.0, 0.0, off_dist))
                # 局部向量通过最终旋转转换到世界空间
                offset_vec = final_quat @ local_vec
            else:
                up = Vector((0.0, 0.0, 1.0))
                if abs(tan.dot(up)) > 0.999:
                    up = Vector((0.0, 1.0, 0.0))
                offset_vec = up.cross(tan).normalized() * off_dist
'''

# 找到偏移块的起止行（0-indexed）
start = None
end = None
for i, line in enumerate(lines):
    if '# ② 偏移' in line or '② 偏移' in line:
        start = i
    if start is not None and end is None:
        if 'new_obj.location' in line or '③ 缩放' in line:
            end = i
            break

print(f"Offset block: start={start}, end={end}")
assert start is not None, "Could not find offset block start!"
assert end is not None, "Could not find offset block end!"

# 替换
new_lines = lines[:start] + [new_offset_block] + lines[end:]
new_content = ''.join(new_lines)

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content)

print('Step 2 done: _place_objects offset logic replaced')

# 验证
import ast
try:
    ast.parse(new_content)
    print('AST check: PASSED')
except SyntaxError as e:
    print(f'AST check FAILED: {e}')
