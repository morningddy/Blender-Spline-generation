filepath = r'D:/codex/blenderchaj/spline_object_generator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到 UI 中偏移面板的代码块
old_ui = '''        box_offset = layout.box()
        box_offset.label(text="偏移", icon='CON_LOCLIKE')
        col = box_offset.column(align=True)
        col.prop(props, "use_offset", toggle=True)
        if props.use_offset:
            col.prop(props, "offset_axis", text="")
            col.prop(props, "offset_distance")'''

new_ui = '''        # ---- 偏移面板 ----
        box_offset = layout.box()
        box_offset.label(text="偏移", icon='CON_LOCLIKE')

        if props.mode == 'MULTI' and props.multi_mode == 'HEADTAIL':
            # HEADTAIL 模式：显示三组独立偏移控制
            col = box_offset.column(align=True)
            col.label(text="头部模型偏移:", icon='CON_SPLINEIK')
            col.prop(props, "head_use_offset", toggle=True)
            if props.head_use_offset:
                col.prop(props, "head_offset_axis", text="")
                col.prop(props, "head_offset_distance")

            col = box_offset.column(align=True)
            col.label(text="尾部模型偏移:", icon='CON_SPLINEIK')
            col.prop(props, "tail_use_offset", toggle=True)
            if props.tail_use_offset:
                col.prop(props, "tail_offset_axis", text="")
                col.prop(props, "tail_offset_distance")

            col = box_offset.column(align=True)
            col.label(text="循环体偏移:", icon='CON_SPLINEIK')
            col.prop(props, "loop_use_offset", toggle=True)
            if props.loop_use_offset:
                col.prop(props, "loop_offset_axis", text="")
                col.prop(props, "loop_offset_distance")
        else:
            # 非 HEADTAIL 模式：显示全局偏移控制
            col = box_offset.column(align=True)
            col.prop(props, "use_offset", toggle=True)
            if props.use_offset:
                col.prop(props, "offset_axis", text="")
                col.prop(props, "offset_distance")'''

if old_ui in content:
    content = content.replace(old_ui, new_ui)
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print('Step 3 done: UI panel updated')
else:
    print('ERROR: could not find old UI block')
    # 调试：搜索附近内容
    idx = content.find('box_offset = layout.box()')
    if idx >= 0:
        print(f'Found box_offset at char {idx}')
        print(repr(content[idx:idx+200]))
    else:
        print('box_offset block not found at all')

    # 也尝试搜索中文版本
    idx2 = content.find('偏移", icon')
    if idx2 >= 0:
        print(f'Found 「偏移」at char {idx2}')
        print(repr(content[idx2:idx2+200]))
