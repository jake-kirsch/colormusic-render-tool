import math
import svgwrite

BASE_DIR = "D:\\music_project\\Conversion"

# Create a new SVG canvas
dwg = svgwrite.Drawing(f"{BASE_DIR}/website_files/colormusic-text-logo.svg", size=("300px", "200px"))
dwg.viewbox(minx=0, miny=0, width=300, height=200)

text_content = "color"
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

# Middle stroke
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="none",
    stroke="white",
    stroke_width=1,
    font_size=40,
    font_family="Arial"
))

# Inner fill
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="orange",
    font_size=40,
    font_family="Arial"
))

text_content = "music"
x, y = 100, 35

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

# Middle stroke
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="none",
    stroke="white",
    stroke_width=1,
    font_size=40,
    font_family="Arial"
))

# Inner fill
dwg.add(dwg.text(
    text_content,
    insert=(x, y),
    fill="grey",
    font_size=40,
    font_family="Arial"
))





dwg.save()
