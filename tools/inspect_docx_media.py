from zipfile import ZipFile
from pathlib import Path
from PIL import Image
import io, os
for fn in [
'artifacts/国防教育概论_95式外形仿真训练模型机电光系统原理_书稿版.docx',
'artifacts/95式电磁激光仿真训练模型结构与原理说明_公式内容完善版.docx',
'artifacts/95式电磁激光仿真训练模型结构与原理说明_无乱码_原生公式版.docx']:
    print('\n===',fn,'===')
    with ZipFile(fn) as z:
        names=[n for n in z.namelist() if n.startswith('word/media/')]
        for n in names:
            data=z.read(n)
            try:
                im=Image.open(io.BytesIO(data))
                print(n, im.size, im.format, len(data))
            except Exception as e:
                print(n,'nonraster',len(data))
