import math
import svgwrite

BASE_DIR = "D:\\music_project\\Conversion"

# Create a new SVG canvas
dwg = svgwrite.Drawing(f"{BASE_DIR}/website_files/colormusic-tool-text.svg", size=("300px", "200px"))
dwg.viewbox(minx=0, miny=0, width=300, height=200)

text_content = "notation"
x, y = 10, 35

# Outer stroke (widest)
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="none",
    stroke="black",
    stroke_width=4,
    font_size=40,
    font_family="Arial"
))

# Inner fill
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="white",
    stroke="white",
    stroke_width=1,
    font_size=40,
    font_family="Arial"
))

text_content = "tool"
x, y = 158, 35

# Outer stroke (widest)
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="none",
    stroke="black",
    stroke_width=4,
    font_size=40,
    font_family="Arial"
))

# Inner fill
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="white",
    stroke="white",
    stroke_width=1,
    font_size=40,
    font_family="Arial"
))

dwg.save()
