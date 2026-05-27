filepath = r'D:/codex/blenderchaj/spline_object_generator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到旧的偏移逻辑块
old_block = None
new_block = None

# 搜索偏移逻辑块的开始和结束
lines = content.split('\n')
in_offset = False
offset_start = None
offset_end = None

for i, line in enumerate(lines):
    if '# ② 偏移' in line or '② 偏移' in line:
        offset_start = i
        in_offset = True
    if in_offset and offset_end is None:
        # 偏移块结束于 new_obj.location 或缩放部分
        if 'new_obj.location' in line or '③ 缩放' in line or 'offset_vec = pt' in line:
            offset_end = i
            break

print(f"offset block: start={offset_start}, end={offset_end}")
if offset_start is not None:
    for i in range(offset_start, min(offset_start+30, len(lines)):
        print(f"  {i+1}: {repr(lines[i][:80])}")

# 现在构造新的偏移逻辑
new_logic = '''        # ② 偏移：根据模型类型使用对应的偏移设置
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
                offset_vec = final_quat @ local_vec
            else:
                up = Vector((0.0, 0.0, 1.0))
                if abs(tan.dot(up)) > 0.999:
                    up = Vector((0.0, 1.0, 0.0))
                offset_vec = up.cross(tan).normalized() * off_dist'''

if offset_start is not None and offset_end is not None:
    # 替换偏移逻辑块
    new_lines = lines[:offset_start]
    new_lines.append(new_logic)
    new_lines.extend(lines[offset_end:])
    new_content = '\n'.join(new_lines)
    
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    print('Step 2 done: _place_objects offset logic replaced')
else:
    print('ERROR: could not find offset block')
