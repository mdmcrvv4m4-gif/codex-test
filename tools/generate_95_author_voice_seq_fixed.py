from pathlib import Path

src = Path(__file__).with_name('generate_95_author_voice_seq.py')
code = src.read_text(encoding='utf-8')
code = code.replace("r._element.rPr.rFonts.set(qn('w:eastAsia'),'宋体')", "r.font.name='Noto Sans CJK SC'")
code = code.replace("r._element.rPr.rFonts.set(qn('w:eastAsia'),'黑体')", "r.font.name='Noto Sans CJK SC'")
exec(compile(code, str(src), 'exec'), {'__name__':'__main__','__file__':str(src)})
