content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

# 1. Widen grid columns: add a 5th column for the + button
old_grid = (
    '.mod-header { display: grid; grid-template-columns: 1fr 1.4fr 1.4fr 34px; gap: 8px; margin-bottom: 6px; font-size: 0.78rem; color: #9a9db0; padding: 0 2px; font-weight: 500; }\n'
    '.mod-row { display: grid; grid-template-columns: 1fr 1.4fr 1.4fr 34px; gap: 8px; margin-bottom: 8px; align-items: center; }'
)
new_grid = (
    '.mod-header { display: grid; grid-template-columns: 1fr 1.4fr 1.4fr 30px 30px; gap: 8px; margin-bottom: 6px; font-size: 0.78rem; color: #9a9db0; padding: 0 2px; font-weight: 500; }\n'
    '.mod-row { display: grid; grid-template-columns: 1fr 1.4fr 1.4fr 30px 30px; gap: 8px; margin-bottom: 8px; align-items: center; }'
)
assert old_grid in content, 'grid columns not found'
content = content.replace(old_grid, new_grid, 1)

# 2. Add CSS for btn-mod-add-inline (the + button inside rows)
old_add_css = '.btn-mod-add {\n  background: none;\n  border: 1px dashed #c0cce8;\n  border-radius: 6px;\n  color: #1557f5;\n  cursor: pointer;\n  padding: 6px 16px;\n  font-size: 0.84rem;\n  margin-top: 2px;\n  transition: background .15s, border-color .15s;\n}\n.btn-mod-add:hover { background: #f0f4ff; border-color: #1557f5; }'
new_add_css = (
    '.btn-mod-add {\n'
    '  background: none;\n'
    '  border: 1px dashed #c0cce8;\n'
    '  border-radius: 6px;\n'
    '  color: #1557f5;\n'
    '  cursor: pointer;\n'
    '  padding: 6px 16px;\n'
    '  font-size: 0.84rem;\n'
    '  margin-top: 2px;\n'
    '  transition: background .15s, border-color .15s;\n'
    '}\n'
    '.btn-mod-add:hover { background: #f0f4ff; border-color: #1557f5; }\n'
    '.btn-mod-add-inline {\n'
    '  width: 30px; height: 30px;\n'
    '  background: #f0f4ff; border: 1px solid #c0cce8;\n'
    '  border-radius: 5px; color: #1557f5;\n'
    '  cursor: pointer; display: flex; align-items: center; justify-content: center;\n'
    '  font-size: 1.1rem; font-weight: 600; transition: background .15s; flex-shrink: 0;\n'
    '}\n'
    '.btn-mod-add-inline:hover { background: #dde6ff; border-color: #1557f5; }'
)
assert old_add_css in content, 'btn-mod-add css not found'
content = content.replace(old_add_css, new_add_css, 1)

# 3. Add extra empty <span> to mod-header so columns align
old_header_html = '<div class="mod-header"><span>Module</span><span>Branch</span><span>Commit ID</span><span></span></div>'
new_header_html = '<div class="mod-header"><span>Module</span><span>Branch</span><span>Commit ID</span><span></span><span></span></div>'
assert old_header_html in content, 'mod-header not found'
content = content.replace(old_header_html, new_header_html, 1)

# 4. Remove the standalone "添加模块" button below moduleRows (build panel only)
old_standalone = (
    '          <div id="moduleRows"></div>\n'
    '          <button class="btn-mod-add" onclick="addModuleRow()">+ 添加模块</button>'
)
new_standalone = '          <div id="moduleRows"></div>'
assert old_standalone in content, 'standalone add-module btn not found'
content = content.replace(old_standalone, new_standalone, 1)

# 5. Update addModuleRow to include + button and use _refreshModuleAddBtns
old_func = (
    'function addModuleRow(name=\'\', branch=\'\', commit_id=\'\') {\n'
    '  const row = document.createElement(\'div\');\n'
    '  row.className = \'mod-row\';\n'
    '  row.innerHTML = `\n'
    '    <input type="text" class="form-input mod-name" placeholder="" value="${escHtml(name)}" autocomplete="off">\n'
    '    <input type="text" class="form-input mod-branch" placeholder="" value="${escHtml(branch)}" autocomplete="off">\n'
    '    <input type="text" class="form-input mod-commit" placeholder="" value="${escHtml(commit_id)}">\n'
    '    <button class="btn-mod-remove" onclick="this.closest(\'.mod-row\').remove()" title="删除">×</button>`;\n'
    '  document.getElementById(\'moduleRows\').appendChild(row);\n'
    '}'
)
new_func = (
    'function _refreshModuleAddBtns() {\n'
    '  const rows = document.querySelectorAll(\'#moduleRows .mod-row\');\n'
    '  rows.forEach((r, i) => {\n'
    '    const btn = r.querySelector(\'.btn-mod-add-inline\');\n'
    '    if (btn) btn.style.visibility = (i === rows.length - 1) ? \'visible\' : \'hidden\';\n'
    '  });\n'
    '}\n'
    '\n'
    'function addModuleRow(name=\'\', branch=\'\', commit_id=\'\') {\n'
    '  const row = document.createElement(\'div\');\n'
    '  row.className = \'mod-row\';\n'
    '  row.innerHTML = `\n'
    '    <input type="text" class="form-input mod-name" placeholder="" value="${escHtml(name)}" autocomplete="off">\n'
    '    <input type="text" class="form-input mod-branch" placeholder="" value="${escHtml(branch)}" autocomplete="off">\n'
    '    <input type="text" class="form-input mod-commit" placeholder="" value="${escHtml(commit_id)}">\n'
    '    <button class="btn-mod-remove" onclick="this.closest(\'.mod-row\').remove();_refreshModuleAddBtns();" title="删除">×</button>\n'
    '    <button class="btn-mod-add-inline" onclick="addModuleRow();_refreshModuleAddBtns();" title="添加模块">+</button>`;\n'
    '  document.getElementById(\'moduleRows\').appendChild(row);\n'
    '  _refreshModuleAddBtns();\n'
    '}'
)
assert old_func in content, 'addModuleRow function not found'
content = content.replace(old_func, new_func, 1)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done, lines:', len(content.splitlines()))
