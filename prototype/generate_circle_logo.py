import math
import svgwrite

BASE_DIR = "C:\\Users\\josep\\Desktop\\personal\\colormusic-render-tool\\app\\static\\assets"

factor = 1.3

SQUARE = 20 * factor
CIRCLE = 11.333 * factor

x_offset, y_offset = 100, 100
radius = 65

min_x = x_offset - radius - 20
min_y = y_offset - radius - 20
max_x = x_offset + radius + 20
max_y = y_offset + radius + 20
width = max_x - min_x
height = max_y - min_y

# Create a new SVG canvas
dwg = svgwrite.Drawing(f"{BASE_DIR}/colormusic-circle-logo.svg", size=(f"{width}px", f"{height}px"))
dwg.viewbox(minx=min_x, miny=min_y, width=width, height=height)

# dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="#f0f0f0"))

STROKE_WIDTH = 2 * factor  # svgwrite uses user units; 20 may be too thick depending on scale

# Pitch color mapping
PITCH_COLORS = {
    "A": "#fdbb13", 
    "B": "#A6CE39", "Cb": "#A6CE39", 
    "C": "#DA1E48", "B#": "#DA1E48", 
    "D": "#F58220",
    "E": "#F3DC0B", "Fb": "#F3DC0B",
    "F": "#AB218E", "E#": "#AB218E",
    "G": "#F04E23",
    "G#": "#0098DD", "Ab": "#0098DD", 
    "A#": "#823F98", "Bb": "#823F98",
    "C#": "#00A995", "Db": "#00A995", 
    "D#": "#3763AF", "Eb": "#3763AF",
    "F#": "#39B54A", "Gb": "#39B54A",
}

SQUARE_PITCHES = ["Ab", "G#", "Bb", "A#", "C", "B#", "D", "E", "Fb", "Gb", "F#"]

# SVG setup
group = dwg.g()  # create a group to hold all shapes



for pitch, angle in [
    ("Eb", 0), ("D", 30), ("Db", 60), ("C", 90), ("B", 120), ("Bb", 150),
    ("A", 180), ("Ab", 210), ("G", 240), ("Gb", 270), ("F", 300), ("E", 330)
]:
    color = PITCH_COLORS[pitch]
    angle_rad = math.radians(angle)
    x = radius * math.cos(angle_rad) + x_offset
    y = -radius * math.sin(angle_rad) + y_offset  # flip Y for SVG coord

    if pitch in SQUARE_PITCHES:
        width = SQUARE
        rect_x = x - width / 2
        rect_y = y - width / 2
        rect = dwg.rect(
            insert=(rect_x, rect_y),
            size=(width, width),
            fill=color,
            stroke="black",
            stroke_width=STROKE_WIDTH
        )
        # Apply rotation around center of rect
        rect.rotate(90 - angle, center=(x, y))
        group.add(rect)
    else:
        circle = dwg.circle(
            center=(x, y),
            r=CIRCLE,
            fill=color,
            stroke="black",
            stroke_width=STROKE_WIDTH
        )
        group.add(circle)

# Add group to SVG and save
dwg.add(group)

dwg.save()
