content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

# Also hide × when only one row remains; refresh after remove
old_refresh = (
    'function _refreshModuleAddBtns() {\n'
    '  const rows = document.querySelectorAll(\'#moduleRows .mod-row\');\n'
    '  rows.forEach((r, i) => {\n'
    '    const btn = r.querySelector(\'.btn-mod-add-inline\');\n'
    '    if (btn) btn.style.visibility = (i === rows.length - 1) ? \'visible\' : \'hidden\';\n'
    '  });\n'
    '}'
)
new_refresh = (
    'function _refreshModuleAddBtns() {\n'
    '  const rows = document.querySelectorAll(\'#moduleRows .mod-row\');\n'
    '  const last = rows.length - 1;\n'
    '  rows.forEach((r, i) => {\n'
    '    const addBtn = r.querySelector(\'.btn-mod-add-inline\');\n'
    '    const rmBtn  = r.querySelector(\'.btn-mod-remove\');\n'
    '    if (addBtn) addBtn.style.visibility = (i === last) ? \'visible\' : \'hidden\';\n'
    '    if (rmBtn)  rmBtn.style.visibility  = (rows.length > 1) ? \'visible\' : \'hidden\';\n'
    '  });\n'
    '}'
)
assert old_refresh in content, '_refreshModuleAddBtns not found'
content = content.replace(old_refresh, new_refresh, 1)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done, lines:', len(content.splitlines()))
