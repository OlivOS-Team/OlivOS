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

# 将免构建前端从零生成到 staticData.py。该文件不入 Git 跟踪，仅在打包/发布前生成，
# 供盘上无 static 目录的部署形态（pip/打包）回退；源码运行直接服务 OlivOS/webUI/static。

import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'OlivOS/webUI'
target = root / 'staticData.py'

HEADER = '''# -*- encoding: utf-8 -*-
r\'\'\'
_______________________    ________________
__  __ \\__  /____  _/_ |  / /_  __ \\_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \\
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\\____/ /_____/___/  _____/  \\____/ /____/

@File      :   OlivOS/webUI/staticData.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
\'\'\'

# 免构建前端的内嵌资源；由 script/embed_webui.py 生成，不入 Git 跟踪。

import base64
from pathlib import Path

'''

RELEASE_FUNC = '''


def releaseBase64Data(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in FILES.items():
        content = base64.b64decode(data)
        target = directory / name
        if not target.exists() or target.read_bytes() != content:
            target.write_bytes(content)
    return directory
'''

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

body = HEADER + '\n'.join(lines) + RELEASE_FUNC
with target.open('w', encoding='utf-8', newline='\n') as output:
    output.write(body)
print('WebUI assets embedded.')
