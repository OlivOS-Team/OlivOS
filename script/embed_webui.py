# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   script/embed_webui.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

# 将免构建前端写入 staticData.py；发布前运行一次，无需修改 spec。

import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'OlivOS/webUI'
target = root / 'staticData.py'
text = target.read_text(encoding='utf-8')
start = text.index('FILES = {')
end = text.index('\n\n\ndef releaseBase64Data', start)
lines = ['FILES = {']
for name in ('index.html', 'app.js', 'theme.js', 'style.css', 'logo.png'):
    source = root / 'static' / name
    # 文本统一为 LF，避免 Git 的自动换行转换导致不同平台生成不同资源。
    data = source.read_bytes() if source.suffix == '.png' else source.read_text(encoding='utf-8').encode('utf-8')
    encoded = base64.b64encode(data).decode('ascii')
    lines.append(f'    {name!r}: (')
    lines.extend(f'        {encoded[i:i + 100]!r}' for i in range(0, len(encoded), 100))
    lines.append('    ),')
lines.append('}')
with target.open('w', encoding='utf-8', newline='\n') as output:
    output.write(text[:start] + '\n'.join(lines) + text[end:])
print('WebUI assets embedded.')
