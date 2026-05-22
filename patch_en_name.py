content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

# 1. Add _tlmOwnerEnName variable declaration
old_var = "let _tlmOwnerName = '';"
new_var = "let _tlmOwnerName = '', _tlmOwnerEnName = '';"
assert old_var in content, '_tlmOwnerName var not found'
content = content.replace(old_var, new_var, 1)

# 2. Update message callback to also store en_name
old_cb = (
    "    _tlmOwnerName = name; _tlmOwnerOpenId = open_id;\n"
    "    document.getElementById('tlmOwnerName').textContent = name;"
)
new_cb = (
    "    _tlmOwnerName = name; _tlmOwnerEnName = e.data.feishuOwner.en_name || ''; _tlmOwnerOpenId = open_id;\n"
    "    document.getElementById('tlmOwnerName').textContent = name;"
)
assert old_cb in content, 'owner callback not found'
content = content.replace(old_cb, new_cb, 1)

# 3. Clear en_name in clearFeishuOwner
old_clear = "_tlmOwnerName = ''; _tlmOwnerOpenId = '';"
new_clear = "_tlmOwnerName = ''; _tlmOwnerEnName = ''; _tlmOwnerOpenId = '';"
assert old_clear in content, 'clearFeishuOwner not found'
content = content.replace(old_clear, new_clear, 1)

# 4. Reset en_name in openAddTLMRecord
old_add = "_tlmOwnerOpenId = ''; _tlmOwnerName = '';"
new_add = "_tlmOwnerOpenId = ''; _tlmOwnerName = ''; _tlmOwnerEnName = '';"
assert old_add in content, 'openAddTLMRecord reset not found'
content = content.replace(old_add, new_add, 1)

# 5. Restore en_name in openEditTLMRecord (use empty since it's not stored)
old_edit = "_tlmOwnerOpenId = r.owner_open_id || ''; _tlmOwnerName = r.owner || '';"
new_edit = "_tlmOwnerOpenId = r.owner_open_id || ''; _tlmOwnerName = r.owner || ''; _tlmOwnerEnName = '';"
assert old_edit in content, 'openEditTLMRecord not found'
content = content.replace(old_edit, new_edit, 1)

# 6. In openCreateTLMDialog: use en_name for PPM and FO fields
old_dialog = (
    "  document.getElementById('createTLMPpm').value  = _tlmOwnerName;\n"
    "  document.getElementById('createTLMFo').value   = _tlmOwnerName;"
)
new_dialog = (
    "  const _ownerUsername = _tlmOwnerEnName || _tlmOwnerName;\n"
    "  document.getElementById('createTLMPpm').value  = _ownerUsername;\n"
    "  document.getElementById('createTLMFo').value   = _ownerUsername;"
)
assert old_dialog in content, 'openCreateTLMDialog fields not found'
content = content.replace(old_dialog, new_dialog, 1)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done, lines:', len(content.splitlines()))
