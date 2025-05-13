# Standard Libraries
import math
import os

# Third-party Libraries
from bs4 import BeautifulSoup
import verovio

# Constants
BASE_DIR = "app/static/rendered_svgs"
STROKE_WIDTH = 20

# Pitch color mapping
PITCH_COLORS = {
    "A": "#fdbb13", "B": "#A6CE39", "C": "#DA1E48", "D": "#F58220",
    "E": "#F3DC0B", "F": "#AB218E", "G": "#F04E23",
    "G#": "#0098DD", "Ab": "#0098DD", "A#": "#823F98", "Bb": "#823F98",
    "C#": "#00A995", "Db": "#00A995", "D#": "#3763AF", "Eb": "#3763AF",
    "F#": "#39B54A", "Gb": "#39B54A"
}

SQUARE_PITCHES = ["Ab", "G#", "Bb", "A#", "C", "D", "E", "Gb", "F#"]

# Test selection
# TESTS = [
#     {"song": "Sight Reading Practice - Evan Ramsey", "mei_filename": "SightReadingPractice"}, # 0
#     {"song": "Shake It Off - Taylor Swift", "mei_filename": "ShakeItOff"}, # 1
#     {"song": "Can you feel the love tonight? - Elton John", "mei_filename": "CanYouFeelTheLoveTonight"}, # 2
#     {"song": "Moonlight Sonata - Beethoven", "mei_filename": "MoonlightSonata"}, # 3
#     {"song": "Mad World - Gary Jules", "mei_filename": "MadWorld"}, # 4
#     {"song": "Creep - Radiohead", "mei_filename": "Creep"}, # 5
#     {"song": "Because of You - Kelly Clarkson", "mei_filename": "BecauseOfYou"}, # 6
# ]
# TEST_NO = 6
# SONG = TESTS[TEST_NO]["song"]
# FILENAME = TESTS[TEST_NO]["mei_filename"]

# ORIGINAL_FILE = os.path.join(BASE_DIR, f"{FILENAME}.mei")
# MODIFIED_FILE = os.path.join(BASE_DIR, f"{FILENAME}-mod.mei")

SONG = "TBD"

tk = verovio.toolkit()


# ====== Processing Functions ======

def parse_mei(file_path):
    """Parse MEI file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "xml")


def label_notes(soup):
    """Label MEI notes with pitch and duration to preserve info during SVG rendering"""
    for note in soup.find_all("note"):
        pname = note.get("pname")
        dur = note.get("dur")

        accid_tag = note.find("accid")
        accid_val = accid_tag.get("accid.ges") if accid_tag else None

        if accid_val == "s":
            accid = "#"
        elif accid_val == "f":
            accid = "b"
        else:
            accid = ""

        if dur is None:
            chord = note.find_parent("chord")

            dur = chord.get("dur")

        if pname:
            note["label"] = f"{pname.upper()}{accid}:{dur}"
    return soup


def reorder_note(note):
    """Reorder notehead and stem so notehead is in front"""
    notehead = note.find("g", class_="notehead")
    stem = note.find("g", class_="stem")
    if notehead and stem and notehead.previous_sibling != stem:
        stem.extract()
        note.insert(note.contents.index(notehead), stem)


def render_note_to_colormusic(note, chord):
    """Render note to ColorMusic-style"""
    # Get the pitch and dur value (e.g., 'C', '4')
    pitch, dur = note.find("title", class_="labelAttr").text.split(":")
    
    notehead = note.find("g", class_="notehead")
    stem = note.find("g", class_="stem")

    # Best attempt using chord
    if chord and not stem:
        stem = chord.find("g", class_="stem")

    stem_direction = "no-stem"
    if stem:
        stem_path = stem.find("path")

        d = stem_path["d"]
        tokens = d.replace("M", "").replace("L", "").split()
        x1, y1, x2, y2 = map(float, tokens)

        # Determine direction and side
        stem_direction = "up" if y2 < y1 else "down"
    
    if pitch in SQUARE_PITCHES:
        # Find the <use> tag that contains the x and y position
        notehead_use = notehead.find("use")

        try:
            dur = int(dur)
        except:
            dur = None

        notehead_style = "open" if dur and int(dur) <= 2 else "filled"

        if stem_direction == "up":
            notehead_use["xlink:href"] = f"#{pitch}-{notehead_style}-stem-up"
        elif stem_direction == "down":
            notehead_use["xlink:href"] = f"#{pitch}-{notehead_style}-stem-down"
        else:
            notehead_use["xlink:href"] = f"#{pitch}-{notehead_style}-no-stem"
    else:
        notehead["fill"] = PITCH_COLORS[pitch]
        notehead["stroke"] = "Black"
        notehead["stroke-width"] = f"{STROKE_WIDTH}"


def add_symbols_to_defs(defs):
    """Add symbols to defs for Square Pitches - open/filled/stem up/stem down/no stem"""
    # Define base widths for squares, these will be scaled up horizontally depending on stem
    outer_base_width = 240
    inner_base_width = 100

    # Stem Down
    for square_pitch in SQUARE_PITCHES:
        open_symbol_markup = f"""
            <symbol id="{square_pitch}-open-stem-down" overflow="inherit" viewBox="0 0 1000 1000">
                <rect height="{outer_base_width}" width="{outer_base_width * 1.25}" fill="{PITCH_COLORS[square_pitch]}" transform="translate(0, -120)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
                <rect height="{inner_base_width}" width="{inner_base_width * 1.25}" fill="White" transform="translate(85, -50)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
            </symbol>
        """

        filled_symbol_markup = f"""
            <symbol id="{square_pitch}-filled-stem-down" overflow="inherit" viewBox="0 0 1000 1000">
            <rect height="{outer_base_width}" width="{outer_base_width * 1.25}" fill="{PITCH_COLORS[square_pitch]}" transform="translate(10, -120)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
            </symbol>
        """

        # Parse the symbols and append it to <defs>
        open_symbol_soup = BeautifulSoup(open_symbol_markup, "xml").symbol
        filled_symbol_soup = BeautifulSoup(filled_symbol_markup, "xml").symbol

        defs.append(open_symbol_soup)
        defs.append(filled_symbol_soup)

    # Stem Up
    for square_pitch in SQUARE_PITCHES:
        open_symbol_markup = f"""
            <symbol id="{square_pitch}-open-stem-up" overflow="inherit" viewBox="0 0 1000 1000">
                <rect height="{outer_base_width}" width="{outer_base_width * 1.25}" fill="{PITCH_COLORS[square_pitch]}" transform="translate(5, -120)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
                <rect height="{inner_base_width}" width="{inner_base_width * 1.25}" fill="White" transform="translate(95, -50)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
            </symbol>
        """

        filled_symbol_markup = f"""
            <symbol id="{square_pitch}-filled-stem-up" overflow="inherit" viewBox="0 0 1000 1000">
            <rect height="{outer_base_width}" width="{outer_base_width * 1.25}" fill="{PITCH_COLORS[square_pitch]}" transform="translate(5, -120)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
            </symbol>
        """

        # Parse the symbols and append it to <defs>
        open_symbol_soup = BeautifulSoup(open_symbol_markup, "xml").symbol
        filled_symbol_soup = BeautifulSoup(filled_symbol_markup, "xml").symbol

        defs.append(open_symbol_soup)
        defs.append(filled_symbol_soup)

    # No Stem
    for square_pitch in SQUARE_PITCHES:
        open_symbol_markup = f"""
            <symbol id="{square_pitch}-open-no-stem" overflow="inherit" viewBox="0 0 1000 1000">
                <rect height="{outer_base_width}" width="{outer_base_width * 1.65}" fill="{PITCH_COLORS[square_pitch]}" transform="translate(0, -120)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
                <rect height="{inner_base_width}" width="{inner_base_width * 1.65}" fill="White" transform="translate(115, -50)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
            </symbol>
        """

        filled_symbol_markup = f"""
            <symbol id="{square_pitch}-filled-no-stem" overflow="inherit" viewBox="0 0 1000 1000">
            <rect height="{outer_base_width}" width="{outer_base_width * 1.25}" fill="{PITCH_COLORS[square_pitch]}" transform="translate(10, -120)" stroke="Black" stroke-width="{STROKE_WIDTH}"/>
            </symbol>
        """

        # Parse the symbols and append it to <defs>
        open_symbol_soup = BeautifulSoup(open_symbol_markup, "xml").symbol
        filled_symbol_soup = BeautifulSoup(filled_symbol_markup, "xml").symbol

        defs.append(open_symbol_soup)
        defs.append(filled_symbol_soup)


def shift_svg_content(soup):
    """Shift SVG contents for Logo/Title Header"""
    svg = soup.find("svg")
    shift_group = soup.new_tag("g", transform="translate(0, 50)")
    for child in list(svg.contents):
        if child.name:
            shift_group.append(child.extract())
    svg.append(shift_group)
    if svg.has_attr("height"):
        svg["height"] = str(int(svg["height"].replace("px", "")) + 180)


def add_logo_and_title(soup, page_num):
    """Create and Add ColorMusic Logo and Song Title"""
    svg = soup.find("svg")
    group = soup.new_tag("g", id="logo-group")
    x_offset, y_offset = 100, 100
    radius = 65

    for pitch, angle in [
        ("Eb", 0), ("D", 30), ("Db", 60), ("C", 90), ("B", 120), ("Bb", 150),
        ("A", 180), ("Ab", 210), ("G", 240), ("Gb", 270), ("F", 300), ("E", 330)
    ]:
        if pitch in SQUARE_PITCHES:
            width = 15
            x = (radius * math.cos(math.radians(angle))) + x_offset - (width / 2)
            y = -(radius * math.sin(math.radians(angle))) + y_offset - (width / 2)
            cx, cy = x + width / 2, y + width / 2
            shape = soup.new_tag("rect", x=x, y=y, width=width, height=width,
                                 fill=PITCH_COLORS[pitch], stroke="black",
                                 stroke_width=STROKE_WIDTH,
                                 transform=f"rotate({90 - angle} {cx} {cy})")
        else:
            shape = soup.new_tag("circle",
                                 cx=(radius * math.cos(math.radians(angle))) + x_offset,
                                 cy=-(radius * math.sin(math.radians(angle))) + y_offset,
                                 r="8.5", fill=PITCH_COLORS[pitch],
                                 stroke="black", stroke_width=STROKE_WIDTH)
        group.append(shape)

    # Text
    color = soup.new_tag("text", x="55", y="105", fill="#FDB813", **{"font-size": "20"})
    color.string = "color"
    music = soup.new_tag("text", x="97.5", y="105", fill="#939598", **{"font-size": "20"})
    music.string = "music"
    group.append(color)
    group.append(music)

    link = soup.new_tag("a", href="https://www.mycolormusic.com/", target="_blank",
                        **{"xmlns:xlink": "http://www.w3.org/1999/xlink"})
    link.append(group)
    svg.insert(0, link)

    title_group = soup.new_tag("g", id="song-title-group")
    title = soup.new_tag("text", x="210", y="105", fill="Black", **{"font-size": "30"})
    title.string = f"{SONG} - Page {page_num}"
    title_group.append(title)
    svg.insert(0, title_group)


def render_color_music(mei_file_path):
    """Render MEI to ColorMusic"""
    # Label notes in MEI
    soup = parse_mei(mei_file_path)
    labeled_soup = label_notes(soup)

    filename = mei_file_path.split("/")[-1].split(".mei")[0]
    modified_mei_file_path = os.path.join(BASE_DIR, f"{filename}-mod.mei")

    with open(modified_mei_file_path, "w", encoding="utf-8") as f:
        f.write(str(labeled_soup))

    with open(modified_mei_file_path, "r", encoding="utf-8") as f:
        mei_data = f.read()

    tk.loadData(mei_data)

    svg_files = []
    for page in range(1, tk.getPageCount() + 1):
        svg = BeautifulSoup(tk.renderToSVG(page), "xml")
        tk.renderToSVGFile(os.path.join(BASE_DIR, f"{filename}-{page}-original.svg"), page)

        add_symbols_to_defs(svg.find("defs"))
        shift_svg_content(svg)

        for note in svg.find_all(class_="note"):
            render_note_to_colormusic(note, note.find_parent("g", class_="chord"))
            reorder_note(note)

        add_logo_and_title(svg, page)

        # Footer
        footer = svg.new_tag("comment")
        footer.string = """
            Generated and modified using the following libraries:
            - BeautifulSoup: For parsing and manipulating the SVG.
            - Verovio: For rendering MEI files to SVG. Visit Verovio at https://www.verovio.org
        """
        svg.find("svg").append(footer)

        svg_file = os.path.join(BASE_DIR, f"{filename}-{page}-colormusic.svg")
        with open(svg_file, "w", encoding="utf-8") as out:
            out.write(str(svg))

        svg_files.append(svg_file)

    print("Rendered SVG paths:")
    for path in svg_files:
        print("  →", path, "Exists?", os.path.exists(path))

    return svg_files



# def render_color_music(mei_file_path):
#     """
#     Placeholder function to simulate MEI -> SVG rendering.
#     Replace this with your actual rendering logic.
#     """
#     import shutil
#     import os
#     from pathlib import Path

#     output_dir = "app/static/rendered_svgs"
#     os.makedirs(output_dir, exist_ok=True)

#     dummy_1_svg_path = os.path.join(output_dir, "example_1.svg")
#     with open(dummy_1_svg_path, "w") as f:
#         f.write("""<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100'>
#         <rect width='200' height='100' fill='lightblue'/>
#         <text x='10' y='50' font-size='20'>ColorMusic Output</text>
#         </svg>""")

#     dummy_2_svg_path = os.path.join(output_dir, "example_2.svg")
#     with open(dummy_2_svg_path, "w") as f:
#         f.write("""<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100'>
#         <rect width='200' height='100' fill='lightgreen'/>
#         <text x='10' y='50' font-size='20'>ColorMusic Output</text>
#         </svg>""")

#     return [dummy_1_svg_path, dummy_2_svg_path]