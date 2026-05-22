content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

# 1. Merge 创建者 + 备注 into one row (creator on left, remark on right)
old_html = (
    '        <div class="form-group">\n'
    '          <label class="form-label">创建者</label>\n'
    '          <div style="display:flex;align-items:center;gap:8px">\n'
    '            <button type="button" id="buildCreatorAuthBtn" onclick="openBuildCreatorAuth()" style="flex-shrink:0;padding:6px 14px;border:1px solid #d0d3db;border-radius:6px;background:#fff;cursor:pointer;font-size:0.85rem;color:#555;display:flex;align-items:center;gap:6px"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2z" fill="#00D6B9" fill-opacity=".2"/><path d="M12 6a6 6 0 1 0 0 12A6 6 0 0 0 12 6z" fill="#00B39E"/><path d="M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" fill="#fff"/></svg> 飞书授权</button>\n'
    '            <span id="buildCreatorName" style="font-size:0.85rem;color:#333;font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span>\n'
    '            <button type="button" id="buildCreatorClearBtn" onclick="clearBuildCreator()" title="清除创建者" style="display:none;flex-shrink:0;width:22px;height:22px;border:none;background:none;cursor:pointer;color:#bbb;font-size:0.9rem;line-height:1;border-radius:50%;padding:0" onmouseover="this.style.color=\'#e05555\'" onmouseout="this.style.color=\'#bbb\'">✕</button>\n'
    '          </div>\n'
    '        </div>\n'
    '        <div class="form-group">\n'
    '          <label class="form-label">备注</label>\n'
    '          <input type="text" class="form-input" id="remark" placeholder="">\n'
    '        </div>'
)

new_html = (
    '        <div class="form-group">\n'
    '          <div style="display:flex;gap:16px;align-items:flex-end">\n'
    '            <div style="flex:0 0 auto">\n'
    '              <label class="form-label">创建者 <span style="color:#e05555;font-size:0.78rem">*</span></label>\n'
    '              <div style="display:flex;align-items:center;gap:6px">\n'
    '                <button type="button" id="buildCreatorAuthBtn" onclick="openBuildCreatorAuth()" style="flex-shrink:0;padding:6px 14px;border:1px solid #d0d3db;border-radius:6px;background:#fff;cursor:pointer;font-size:0.85rem;color:#555;display:flex;align-items:center;gap:6px"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2z" fill="#00D6B9" fill-opacity=".2"/><path d="M12 6a6 6 0 1 0 0 12A6 6 0 0 0 12 6z" fill="#00B39E"/><path d="M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" fill="#fff"/></svg> 飞书授权</button>\n'
    '                <span id="buildCreatorName" style="font-size:0.85rem;color:#333;font-weight:600;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis"></span>\n'
    '                <button type="button" id="buildCreatorClearBtn" onclick="clearBuildCreator()" title="清除创建者" style="display:none;flex-shrink:0;width:22px;height:22px;border:none;background:none;cursor:pointer;color:#bbb;font-size:0.9rem;line-height:1;border-radius:50%;padding:0" onmouseover="this.style.color=\'#e05555\'" onmouseout="this.style.color=\'#bbb\'">✕</button>\n'
    '              </div>\n'
    '            </div>\n'
    '            <div style="flex:1;min-width:0">\n'
    '              <label class="form-label">备注 <span style="color:#b0b4c4;font-weight:400">（选填）</span></label>\n'
    '              <input type="text" class="form-input" id="remark" placeholder="">\n'
    '            </div>\n'
    '          </div>\n'
    '        </div>'
)

assert old_html in content, 'creator+remark block not found'
content = content.replace(old_html, new_html)

# 2. Add creator validation in sendBuild
old_validate = "  if (!base) { showToast('请填写 Base 版本包', 'error'); return; }\n  if (!modules.length) { showToast('请至少添加一个模块', 'error'); return; }"
new_validate = (
    "  if (!base) { showToast('请填写 Base 版本包', 'error'); return; }\n"
    "  if (!modules.length) { showToast('请至少添加一个模块', 'error'); return; }\n"
    "  if (!_buildCreatorName) { showToast('请先完成创建者飞书授权', 'error'); return; }\n"
    "  const _hasEmptyModule = modules.some(m => !m.name || !m.branch || !m.commit_id);\n"
    "  if (_hasEmptyModule) { showToast('请填写完整的模块 Name / Branch / Commit ID', 'error'); return; }"
)

assert old_validate in content, 'sendBuild validate not found'
content = content.replace(old_validate, new_validate)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done, lines:', len(content.splitlines()))
