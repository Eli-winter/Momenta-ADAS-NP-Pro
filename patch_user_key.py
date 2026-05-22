content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

old = ("  const payload = { work_item_name: name };\n"
       "  if (foInput)  payload.fo_roles  = foInput.split(',').map(s => s.trim()).filter(Boolean);\n"
       "  if (ppmInput) payload.ppm_roles = ppmInput.split(',').map(s => s.trim()).filter(Boolean);")

new = ("  const payload = { work_item_name: name };\n"
       "  if (foInput)          payload.fo_roles  = foInput.split(',').map(s => s.trim()).filter(Boolean);\n"
       "  if (ppmInput)         payload.ppm_roles = ppmInput.split(',').map(s => s.trim()).filter(Boolean);\n"
       "  if (_tlmOwnerOpenId)  payload.user_key  = _tlmOwnerOpenId;")

assert old in content, 'payload block not found'
content = content.replace(old, new)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done')
