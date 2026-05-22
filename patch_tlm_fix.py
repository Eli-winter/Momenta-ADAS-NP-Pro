content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

# 1. Fix openCreateTLMDialog: require auth, fix field mapping
old = '''function openCreateTLMDialog() {
  const desc  = document.getElementById('tlmFieldDesc').value.trim();
  document.getElementById('createTLMName').value = desc;
  document.getElementById('createTLMFo').value   = _tlmOwnerName || '';
  const st = document.getElementById('createTLMStatus');
  st.style.display = 'none'; st.textContent = '';
  document.getElementById('createTLMConfirmBtn').disabled = false;
  document.getElementById('createTLMCancelBtn').disabled  = false;
  document.getElementById('createTLMDialog').classList.add('open');
}'''

new = '''function openCreateTLMDialog() {
  if (!_tlmOwnerName) {
    showToast('请先完成需求Owner飞书授权', 'error');
    return;
  }
  const desc = document.getElementById('tlmFieldDesc').value.trim();
  document.getElementById('createTLMName').value = desc;
  document.getElementById('createTLMPpm').value  = _tlmOwnerName;
  document.getElementById('createTLMFo').value   = _tlmOwnerName;
  const st = document.getElementById('createTLMStatus');
  st.style.display = 'none'; st.textContent = '';
  document.getElementById('createTLMConfirmBtn').disabled = false;
  document.getElementById('createTLMCancelBtn').disabled  = false;
  document.getElementById('createTLMDialog').classList.add('open');
}'''

assert old in content, 'openCreateTLMDialog not found'
content = content.replace(old, new)

# 2. Fix payload: send ppm_roles from PPM field
old2 = "  const payload = { work_item_name: name };\n  if (foInput) payload.fo_roles = foInput.split(',').map(s => s.trim()).filter(Boolean);"
new2 = ("  const ppmInput = document.getElementById('createTLMPpm').value.trim();\n"
        "  const payload = { work_item_name: name };\n"
        "  if (foInput)  payload.fo_roles  = foInput.split(',').map(s => s.trim()).filter(Boolean);\n"
        "  if (ppmInput) payload.ppm_roles = ppmInput.split(',').map(s => s.trim()).filter(Boolean);")

assert old2 in content, 'payload block not found'
content = content.replace(old2, new2)

# 3. Add PPM field to dialog HTML before FO field
old3 = ('    <div class="form-group">\n'
        '      <label class="form-label">FO角色 <span style="color:#b0b4c4;font-weight:400">（飞书用户名，可改）</span></label>\n'
        '      <input class="form-input" type="text" id="createTLMFo" placeholder="如：eli.mao">\n'
        '    </div>')

new3 = ('    <div class="form-group">\n'
        '      <label class="form-label">PPM角色 <span style="color:#b0b4c4;font-weight:400">（自动同步自需求Owner）</span></label>\n'
        '      <input class="form-input" type="text" id="createTLMPpm" readonly style="background:#f5f7fa;color:#555;cursor:default">\n'
        '    </div>\n'
        '    <div class="form-group">\n'
        '      <label class="form-label">FO角色 <span style="color:#b0b4c4;font-weight:400">（必填，飞书用户名）</span></label>\n'
        '      <input class="form-input" type="text" id="createTLMFo" placeholder="如：eli.mao">\n'
        '    </div>')

assert old3 in content, 'dialog form not found'
content = content.replace(old3, new3)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done, lines:', len(content.splitlines()))
