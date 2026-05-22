content = open('/opt/aes-version-manager/frontend/index.html', encoding='utf-8').read()

# 1. Style the name span as a pill, hidden by default
old_span = '<span id="buildCreatorName" style="font-size:0.85rem;color:#333;font-weight:600;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis"></span>'
new_span = '<span id="buildCreatorName" style="display:none;font-size:0.82rem;color:#1557f5;font-weight:600;white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis;background:#eef2ff;border:1px solid #c7d4ff;border-radius:999px;padding:2px 10px"></span>'
assert old_span in content, 'buildCreatorName span not found'
content = content.replace(old_span, new_span, 1)

# 2. When setting name, also show the span
old_set = (
    "    _buildCreatorName = name; _buildCreatorOpenId = open_id;\n"
    "    document.getElementById('buildCreatorName').textContent = name;"
)
new_set = (
    "    _buildCreatorName = name; _buildCreatorOpenId = open_id;\n"
    "    const _cnSpan = document.getElementById('buildCreatorName');\n"
    "    _cnSpan.textContent = name; _cnSpan.style.display = 'inline-block';"
)
assert old_set in content, 'buildCreatorName set block not found'
content = content.replace(old_set, new_set, 1)

# 3. When clearing, hide the span again
old_clear = (
    "  _buildCreatorName = ''; _buildCreatorOpenId = '';\n"
    "  document.getElementById('buildCreatorName').textContent = '';"
)
new_clear = (
    "  _buildCreatorName = ''; _buildCreatorOpenId = '';\n"
    "  const _cnSpan2 = document.getElementById('buildCreatorName');\n"
    "  _cnSpan2.textContent = ''; _cnSpan2.style.display = 'none';"
)
assert old_clear in content, 'buildCreatorName clear block not found'
content = content.replace(old_clear, new_clear, 1)

open('/opt/aes-version-manager/frontend/index.html', 'w', encoding='utf-8').write(content)
print('done, lines:', len(content.splitlines()))
