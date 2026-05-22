content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

# 1. Add _tlmOwnerUserToken variable declaration
old_var = "let _tlmOwnerName = '', _tlmOwnerEnName = '';"
new_var = "let _tlmOwnerName = '', _tlmOwnerEnName = '', _tlmOwnerUserToken = '';"
assert old_var in content, '_tlmOwnerName var not found'
content = content.replace(old_var, new_var, 1)

# 2. Store user_token in postMessage callback
old_cb = "    _tlmOwnerName = name; _tlmOwnerEnName = e.data.feishuOwner.en_name || ''; _tlmOwnerOpenId = open_id;"
new_cb = "    _tlmOwnerName = name; _tlmOwnerEnName = e.data.feishuOwner.en_name || ''; _tlmOwnerOpenId = open_id; _tlmOwnerUserToken = e.data.feishuOwner.user_token || '';"
assert old_cb in content, 'owner callback not found'
content = content.replace(old_cb, new_cb, 1)

# 3. Clear user_token in clearFeishuOwner
old_clear = "_tlmOwnerName = ''; _tlmOwnerEnName = ''; _tlmOwnerOpenId = '';"
new_clear = "_tlmOwnerName = ''; _tlmOwnerEnName = ''; _tlmOwnerOpenId = ''; _tlmOwnerUserToken = '';"
assert old_clear in content, 'clearFeishuOwner not found'
content = content.replace(old_clear, new_clear, 1)

# 4. Reset user_token in openAddTLMRecord
old_add = "_tlmOwnerOpenId = ''; _tlmOwnerName = ''; _tlmOwnerEnName = '';"
new_add = "_tlmOwnerOpenId = ''; _tlmOwnerName = ''; _tlmOwnerEnName = ''; _tlmOwnerUserToken = '';"
assert old_add in content, 'openAddTLMRecord reset not found'
content = content.replace(old_add, new_add, 1)

# 5. Reset user_token in openEditTLMRecord
old_edit = "_tlmOwnerOpenId = r.owner_open_id || ''; _tlmOwnerName = r.owner || ''; _tlmOwnerEnName = ''; _tlmOwnerUserToken = '';"
if old_edit not in content:
    old_edit = "_tlmOwnerOpenId = r.owner_open_id || ''; _tlmOwnerName = r.owner || ''; _tlmOwnerEnName = '';"
    new_edit = "_tlmOwnerOpenId = r.owner_open_id || ''; _tlmOwnerName = r.owner || ''; _tlmOwnerEnName = ''; _tlmOwnerUserToken = '';"
    assert old_edit in content, 'openEditTLMRecord not found'
    content = content.replace(old_edit, new_edit, 1)

# 6. Replace user_key with user_token in doCreateTLMRequirement payload
old_payload = "  if (_tlmOwnerOpenId)  payload.user_key  = _tlmOwnerOpenId;"
new_payload = "  if (_tlmOwnerUserToken) payload.user_token = _tlmOwnerUserToken;"
assert old_payload in content, 'doCreateTLMRequirement payload not found'
content = content.replace(old_payload, new_payload, 1)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done, lines:', len(content.splitlines()))
