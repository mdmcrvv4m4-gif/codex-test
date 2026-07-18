#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新绘制“随机森林失效模式识别的特征重要性”双子图。

优先使用 Matplotlib 输出 SVG/PDF/PNG/TIF；当前运行环境若缺少 Matplotlib/Pandas/
OpenPyXL/Pillow，则退化生成可编辑 SVG、简易矢量 PDF、预览 PNG/TIF 和数据 XLSX。
右图数值为根据原图坐标比例整理的近似值；若后续获得原始置换重要性输出，应直接替换。
"""
from __future__ import annotations

import csv
import os
import struct
import sys
import zlib
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output_rf_importance_cn"
IN_XLSX = BASE / "Origin_RF特征重要性_整理数据.xlsx"

LEFT_DATA = [
    ("严重损伤面积分数", "Severe damage area fraction", 0.1425485611),
    ("磨痕密度", "Wear mark density", 0.1370322704),
    ("磨损面积分数", "Wear area fraction", 0.1159490123),
    ("裂纹面积分数", "Crack area fraction", 0.0838688910),
    ("裂纹网络密度", "Crack network density", 0.0831369609),
    ("裂纹长度密度", "Crack length density", 0.0785489827),
    ("严重损伤最大\n连通域占比", "Severe damage connected area", 0.0765317082),
    ("纹理熵", "Entropy", 0.0588760339),
    ("灰度标准差", "Standard deviation", 0.0516281053),
    ("纹理粗糙度", "Texture roughness", 0.0454870053),
]
RIGHT_FALLBACK = [
    ("磨损面积分数", "Wear area fraction", 0.0800),
    ("磨痕密度", "Wear mark density", 0.0354),
    ("严重损伤面积分数", "Severe damage area fraction", 0.0349),
    ("相关性", "Correlation", 0.0151),
    ("裂纹面积分数", "Crack area fraction", 0.0126),
    ("峰度", "Kurtosis", 0.0074),
    ("灰度均值", "Mean", 0.0043),
    ("灰度标准差", "Standard deviation", 0.0029),
    ("磨损方向一致性", "Wear orientation consistency", 0.0003),
]
ZH_MAP_RIGHT = {e: c for c, e, _ in RIGHT_FALLBACK}
FONT_CANDIDATES = ["SimSun", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC"]


def read_right_data():
    if not IN_XLSX.exists():
        print(f"明确报错：输入 Excel 不存在：{IN_XLSX}；右图使用截图反读近似备用数据。")
        return RIGHT_FALLBACK
    try:
        import pandas as pd
        xl = pd.ExcelFile(IN_XLSX)
        required = ["左图_精确数据", "右图_截图反读近似", "Origin并排作图数据"]
        missing = [s for s in required if s not in xl.sheet_names]
        if missing:
            print(f"明确报错：输入 Excel 缺少工作表：{missing}；右图使用截图反读近似备用数据。")
            return RIGHT_FALLBACK
        df = pd.read_excel(IN_XLSX, sheet_name="右图_截图反读近似")
        cols = list(df.columns)
        name_col = next((c for c in cols if "中文" in str(c) or "特征" in str(c) or "Feature" in str(c)), cols[0])
        val_col = next((c for c in cols if "重要" in str(c) or "value" in str(c).lower() or "Macro" in str(c)), cols[-1])
        out = []
        for _, r in df.iterrows():
            name = str(r[name_col]).strip()
            val = float(r[val_col])
            cn = ZH_MAP_RIGHT.get(name, name)
            en = next((e for c, e, _ in RIGHT_FALLBACK if c == cn or e == name), name)
            out.append((cn, en, val))
        return sorted(out, key=lambda x: x[2], reverse=True)
    except Exception as exc:
        print(f"明确报错：读取右图工作表失败：{exc}；右图使用截图反读近似备用数据。")
        return RIGHT_FALLBACK


def write_xlsx(left, right, path):
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active; ws.title = "左图_不纯度重要性"
        for sheet, data in [(ws, left), (None, right)]:
            if sheet is None: sheet = wb.create_sheet("右图_置换重要性")
            sheet.append(["中文特征名称", "英文原始名称", "特征重要性数值", "排序"])
            for i, (cn, en, v) in enumerate(data, 1): sheet.append([cn.replace("\n", ""), en, v, i])
        wb.save(path); return
    except Exception as exc:
        print(f"明确报错：openpyxl 不可用，使用内置 XLSX 写入器：{exc}")
    # minimal XLSX with inline strings
    def sheet_xml(data):
        rows = [["中文特征名称", "英文原始名称", "特征重要性数值", "排序"]] + [[c.replace("\n", ""), e, v, i] for i,(c,e,v) in enumerate(data,1)]
        body=[]
        for r, row in enumerate(rows,1):
            cells=[]
            for j,val in enumerate(row,1):
                col=chr(64+j)
                if isinstance(val,(int,float)):
                    cells.append(f'<c r="{col}{r}"><v>{val}</v></c>')
                else:
                    cells.append(f'<c r="{col}{r}" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>')
            body.append(f'<row r="{r}">'+''.join(cells)+'</row>')
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(body)+'</sheetData></worksheet>'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>''')
        z.writestr('_rels/.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''')
        z.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>''')
        z.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="左图_不纯度重要性" sheetId="1" r:id="rId1"/><sheet name="右图_置换重要性" sheetId="2" r:id="rId2"/></sheets></workbook>''')
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml(left)); z.writestr('xl/worksheets/sheet2.xml', sheet_xml(right))


def write_csv(data, path):
    """写出 UTF-8-SIG CSV，便于 Excel 和 GitHub 文本差异查看。"""
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["中文特征名称", "英文原始名称", "特征重要性数值", "排序"])
        for i, (cn, en, v) in enumerate(data, 1):
            writer.writerow([cn.replace("\n", ""), en, v, i])


def choose_font():
    try:
        import matplotlib.font_manager as fm
        names = {f.name for f in fm.fontManager.ttflist}
        return next((f for f in FONT_CANDIDATES if f in names), "DejaVu Sans")
    except Exception:
        return "Noto Sans CJK SC"


def draw_with_matplotlib(left, right):
    import matplotlib
    matplotlib.rcParams['svg.fonttype'] = 'none'; matplotlib.rcParams['pdf.fonttype'] = 42; matplotlib.rcParams['ps.fonttype'] = 42
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator, FormatStrFormatter
    font = choose_font()
    plt.rcParams['font.sans-serif'] = [font, 'DejaVu Sans']; plt.rcParams['font.family'] = 'sans-serif'; plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1,2,figsize=(7.1,3.8), facecolor='white')
    specs=[(axes[0],left,'（a）随机森林不纯度重要性','随机森林特征重要性','#4C78A8',0.15,0.02),(axes[1],right,'（b）置换重要性','置换后 Macro-F1 下降量','#F58518',0.085,0.01)]
    for ax,data,title,xlab,color,xmax,step in specs:
        labels=[d[0] for d in data]; vals=[d[2] for d in data]; y=list(range(len(data)))
        ax.barh(y, vals, color=color, edgecolor='#444444', linewidth=0.4, height=0.62)
        ax.set_yticks(y, labels=labels, fontsize=8); ax.invert_yaxis(); ax.set_xlim(0,xmax)
        ax.xaxis.set_major_locator(MultipleLocator(step)); ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        ax.set_xlabel(xlab, fontsize=8.5); ax.set_title(title, fontsize=10, fontweight='bold', pad=8)
        for sp in ['top','right']: ax.spines[sp].set_visible(False)
        for sp in ['left','bottom']: ax.spines[sp].set_linewidth(0.8)
        ax.tick_params(axis='both', direction='out', width=0.8, length=3, labelsize=8)
        for lab in ax.get_xticklabels(): lab.set_fontfamily('Times New Roman')
        for yi,v in zip(y, vals):
            s = f'{v:.4f}' if (ax is axes[1] and v < 0.01) else f'{v:.3f}'
            ax.text(min(v + xmax*0.012, xmax*0.965), yi, s, va='center', ha='left', fontsize=7.5, fontfamily='Times New Roman')
    fig.subplots_adjust(left=0.18,right=0.985,bottom=0.18,top=0.88,wspace=0.62)
    stem=OUT/'图8_随机森林特征重要性_中文'
    fig.savefig(stem.with_suffix('.svg'), facecolor='white')
    fig.savefig(stem.with_suffix('.pdf'), facecolor='white')
    fig.savefig(stem.with_suffix('.png'), dpi=600, facecolor='white')
    fig.savefig(stem.with_suffix('.tif'), dpi=600, facecolor='white', pil_kwargs={'compression':'tiff_lzw'})


def write_svg(left, right, path):
    W,H=710,380; parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<rect width="100%" height="100%" fill="white"/>']
    def panel(x0,y0,w,h,data,title,xlab,color,xmax,step):
        parts.append(f'<text x="{x0+w/2}" y="28" text-anchor="middle" font-family="SimSun,Noto Sans CJK SC" font-size="14" font-weight="bold">{escape(title)}</text>')
        leftm=118; bot=42; top=16; plotx=x0+leftm; ploty=y0+top; plotw=w-leftm-18; ploth=h-top-bot; barh=16; gap=8
        parts.append(f'<path d="M {plotx} {ploty} V {ploty+ploth} H {plotx+plotw}" fill="none" stroke="#222" stroke-width="0.8"/>')
        for i,(cn,en,v) in enumerate(data):
            y=ploty+i*(ploth/len(data))+8; bw=plotw*v/xmax
            for k,line in enumerate(cn.split('\n')):
                parts.append(f'<text x="{plotx-8}" y="{y+barh/2-3+10*k}" text-anchor="end" font-family="SimSun,Noto Sans CJK SC" font-size="11">{escape(line)}</text>')
            parts.append(f'<rect x="{plotx}" y="{y}" width="{bw:.2f}" height="{barh}" fill="{color}" stroke="#444" stroke-width="0.4"/>')
            fmt=f'{v:.4f}' if (x0>300 and v<0.01) else f'{v:.3f}'
            parts.append(f'<text x="{min(plotx+bw+4, plotx+plotw-24):.2f}" y="{y+12}" font-family="Times New Roman" font-size="10">{fmt}</text>')
        n=int(xmax/step+0.5)
        for t in range(n+1):
            val=t*step; xx=plotx+plotw*val/xmax
            parts.append(f'<path d="M {xx:.2f} {ploty+ploth} v 4" stroke="#222" stroke-width="0.8"/>')
            parts.append(f'<text x="{xx:.2f}" y="{ploty+ploth+18}" text-anchor="middle" font-family="Times New Roman" font-size="10">{val:.2f}</text>')
        parts.append(f'<text x="{plotx+plotw/2}" y="{y0+h-5}" text-anchor="middle" font-family="SimSun,Noto Sans CJK SC" font-size="12">{escape(xlab)}</text>')
    panel(0,40,345,315,left,'（a）随机森林不纯度重要性','随机森林特征重要性','#4C78A8',0.15,0.02)
    panel(365,40,335,315,right,'（b）置换重要性','置换后 Macro-F1 下降量','#F58518',0.085,0.01)
    parts.append('</svg>'); path.write_text('\n'.join(parts), encoding='utf-8')


def write_min_png(path, w=4260, h=2280):
    raw = b''.join(b'\x00' + b'\xff\xff\xff'*w for _ in range(h))
    def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b''))

def write_min_tif(path, w=4260, h=2280):
    # white uncompressed RGB TIFF preview (large but lossless)
    img = b'\xff\xff\xff' * w * h
    entries=[]; data_offset=8+2+12*10+4; bits_off=data_offset; img_off=bits_off+6
    def ent(tag,typ,cnt,val): entries.append(struct.pack('<HHII',tag,typ,cnt,val))
    ent(256,4,1,w); ent(257,4,1,h); ent(258,3,3,bits_off); ent(259,3,1,1); ent(262,3,1,2); ent(273,4,1,img_off); ent(277,3,1,3); ent(278,4,1,h); ent(279,4,1,len(img)); ent(284,3,1,1)
    ifd=struct.pack('<H',len(entries))+b''.join(entries)+struct.pack('<I',0)+struct.pack('<HHH',8,8,8)
    path.write_bytes(b'II*\x00'+struct.pack('<I',8)+ifd+img)

def write_pdf_placeholder(path):
    path.write_bytes(b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 511 274]/Contents 4 0 R>>endobj\n4 0 obj<</Length 44>>stream\n1 1 1 rg 0 0 511 274 re f 0 0 0 RG 40 40 430 190 re S\nendstream endobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000205 00000 n \ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n299\n%%EOF')


def main():
    OUT.mkdir(exist_ok=True)
    left=sorted(LEFT_DATA, key=lambda x:x[2], reverse=True); right=read_right_data()
    assert len(left)==10 and len(right)==9 and left[0][2]==max(v for *_,v in left) and right[0][2]==max(v for *_,v in right)
    stem=OUT/'图8_随机森林特征重要性_中文'
    write_csv(left, OUT/'图8_左图_不纯度重要性.csv')
    write_csv(right, OUT/'图8_右图_置换重要性.csv')
    write_xlsx(left,right,stem.with_name(stem.name+'数据.xlsx'))
    try:
        draw_with_matplotlib(left,right)
    except Exception as exc:
        print(f"明确报错：Matplotlib 绘图环境不可用，已生成退化预览文件：{exc}")
        write_svg(left,right,stem.with_suffix('.svg')); write_pdf_placeholder(stem.with_suffix('.pdf')); write_min_png(stem.with_suffix('.png')); write_min_tif(stem.with_suffix('.tif'))
    expected=[stem.with_suffix(s) for s in ['.svg','.pdf','.png','.tif']]+[
        Path(__file__).resolve(),
        OUT/'图8_左图_不纯度重要性.csv',
        OUT/'图8_右图_置换重要性.csv',
        stem.with_name(stem.name+'数据.xlsx'),
    ]
    for p in expected:
        if not p.exists() or p.stat().st_size<=0: raise RuntimeError(f'输出文件缺失或为空：{p}')
        print(p.resolve())

if __name__ == '__main__':
    main()
