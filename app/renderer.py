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

SQUARE_PITCHES = ["Ab", "G#", 
                  "Bb", "A#", 
                  "C", "B#", 
                  "D", 
                  "E", "Fb", 
                  "Gb", "F#", ]

tk = verovio.toolkit()


# ====== Processing Functions ======
def parse_mei(file_path):
    """Parse MEI file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "xml")


def label_notes(soup):
    """Label MEI notes with pitch and duration to preserve info during SVG rendering"""
    # Get the key signature per staff
    keysigs_by_staff_num = {}
    keysigs_by_measure = {}

    for keysig in soup.find_all("keySig"):
        sig = keysig.get("sig")
        mode = keysig.get("mode", "major")

        staffdef = keysig.find_parent("staffDef")

        # Because of You good example changing
        if staffdef:
            staff_num = staffdef.get("n")
            clef = staffdef.find("clef")

            clef_shape = clef.get("shape")
            
            keysigs_by_staff_num[staff_num] = {"sig": sig, "mode": mode, }
        else:
            scoredef = keysig.find_parent("scoreDef")

            next_measure = scoredef.find_next("measure")

            measure_num = int(next_measure.get("n"))

            keysigs_by_measure[measure_num] = {"sig": sig, "mode": mode, }
    
    if not keysigs_by_staff_num:
        # Different format for tracking
        for staffdef in soup.find_all("staffDef"):
            sig = staffdef.get("keysig")
            staff_num = staffdef.get("n")
            clef_shape = staffdef.get("clef.shape")

            if sig and staff_num:
                keysigs_by_staff_num[staff_num] = {"sig": sig, }

    ties = {}
    for tie in soup.find_all("tie"):
        startId = tie.get("startid").replace("#", "")
        endid = tie.get("endid").replace("#", "")

        ties[endid] = startId

    accid_tracker = {}
    for note in soup.find_all("note"):
        note_id = note.get("xml:id")

        tied_note_id = ties.get(note_id)
        
        # Check if note is part of a tie, if it is then persist with label of leading note
        if tied_note_id:
            tied_note = soup.find("note", attrs={"xml:id": tied_note_id})
            label = tied_note.get("label")
            note["label"] = label
        else:
            pname = note.get("pname")
            dur = note.get("dur")
            octave = note.get("oct")

            measure = note.find_parent("measure")
            measure_num = int(measure.get("n"))

            if keysigs_by_measure and measure_num < min(keysigs_by_measure.keys()):
                staff = note.find_parent("staff")
                staff_num = staff.get("n")

                sig = keysigs_by_staff_num[staff_num]["sig"]
                mode = keysigs_by_staff_num[staff_num]["mode"]
            else:
                # Determine sig based on measure position
                if len(keysigs_by_measure) == 1:
                    sig = list(keysigs_by_measure.values())[0]["sig"]
                    mode = list(keysigs_by_measure.values())[0]["mode"]
                else:
                    sorted_keysigs_by_measure = sorted(keysigs_by_measure)

                    for i in range(len(sorted_keysigs_by_measure) - 1):
                        if sorted_keysigs_by_measure[i] <= measure_num < sorted_keysigs_by_measure[i+1]:
                            sig = keysigs_by_measure[sorted_keysigs_by_measure[i]]["sig"]
                            mode = keysigs_by_measure[sorted_keysigs_by_measure[i]]["mode"]
            
            accid_tag = note.find("accid")

            element_name = ""
            accid_val = ""
            if accid_tag:
                # Attempt to get accid value
                for _element_name in [
                    "accid.ges",
                    "accid",
                ]:
                    accid_val = accid_tag.get(_element_name)

                    if accid_val:
                        element_name = _element_name
                        break
            else:
                for _element_name in [
                    "accid.ges",
                    "accid",
                ]:
                    accid_val = note.get(_element_name)

                    if accid_val:
                        element_name = _element_name
                        break
            
            accid_tracker_key = ":::".join([str(measure_num), pname.upper(), octave, ])
            if element_name == "accid":  # Visible-only
                # If accid_val is set need to propagate this through for a given note in the same measure in the same octave
                accid_tracker[accid_tracker_key] = accid_val
            elif not accid_val:
                accid_val = accid_tracker.get(accid_tracker_key, accid_val)
            
            if accid_val == "s":
                # Sharp
                accid = "#"
            elif accid_val == "f":
                # Flat
                accid = "b"
            elif accid_val == "n":
                # If natural skip adding accid
                accid = ""
            else:
                if sig == "0":
                    # 0 - No sharps or flats
                    # C Major -> C - D - E - F - G - A - B - (C)
                    # A Minor -> A - B - C - D - E - F - G - (A)
                    accid = ""
                elif sig == "1s" and  pname.upper() == "F":
                    # 1s - 1 sharp
                    # G Major -> G - A - B - C - D - E - F♯ - (G)
                    # E Minor -> E - F♯ - G - A - B - C - D - (E)
                    accid = "#"
                elif sig == "2s" and pname.upper() in ["C", "F", ]:
                    # 2s - 2 sharps
                    # D Major -> D – E – F♯ – G – A – B – C♯ – (D)
                    # B Minor -> B – C♯ – D – E – F♯ – G – A – (B)
                    accid = "#"
                elif sig == "3s" and pname.upper() in ["C", "F", "G", ]:
                    # 3s - 3 sharps
                    # A Major -> A - B - C♯ - D - E - F♯ - G♯ - (A)
                    # F# Minor -> F♯ - G♯ - A - B - C♯ - D - E - (F♯)
                    accid = "#"
                elif sig == "4s" and pname.upper() in ["C", "D", "F", "G", ]:
                    # 4s - 4 sharps
                    # E Major -> E – F♯ – G♯ – A – B – C♯ – D♯ – (E)
                    # C# Minor -> C♯ – D♯ – E – F♯ – G♯ – A – B – (C♯)
                    accid = "#"
                elif sig == "1f" and  pname.upper() == "B":
                    # 1f - 1 flat
                    # F Major -> F - G - A - B♭ - C - D - E - (F)
                    # D Minor -> D - E - F - G - A - B♭ - C - (D)
                    accid = "b"
                elif sig == "4f" and  pname.upper() in ["A", "B", "D", "E", ]:
                    # 4f - 4 flats
                    # A♭ Major -> A♭ – B♭ – C – D♭ – E♭ – F – G – (A♭)
                    # F Minor -> F – G – A♭ – B♭ – C – D♭ – E♭ – (F)
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


def add_logo_and_title(soup, page_num, page_title):
    """Create and Add ColorMusic Logo and Song Title"""
    svg = soup.find("svg")
    group = soup.new_tag("g", id="logo-group")
    x_offset, y_offset = 100, 100
    radius = 65

    for pitch, angle in [
        ("Eb", 0),
        ("D", 30),
        ("Db", 60),
        ("C", 90),
        ("B", 120),
        ("Bb", 150),
        ("A", 180),
        ("Ab", 210),
        ("G", 240),
        ("Gb", 270),
        ("F", 300),
        ("E", 330),
    ]:
        if pitch in SQUARE_PITCHES:
            width = 15
            x = (radius * math.cos(math.radians(angle))) + x_offset - (width / 2)
            y = -(radius * math.sin(math.radians(angle))) + y_offset - (width / 2)
            cx, cy = x + width / 2, y + width / 2
            shape = soup.new_tag(
                "rect",
                x=x,
                y=y,
                width=width,
                height=width,
                fill=PITCH_COLORS[pitch],
                stroke="black",
                stroke_width=STROKE_WIDTH,
                transform=f"rotate({90 - angle} {cx} {cy})",
            )
        else:
            shape = soup.new_tag(
                "circle",
                cx=(radius * math.cos(math.radians(angle))) + x_offset,
                cy=-(radius * math.sin(math.radians(angle))) + y_offset,
                r="8.5",
                fill=PITCH_COLORS[pitch],
                stroke="black",
                stroke_width=STROKE_WIDTH,
            )
        group.append(shape)

    # Text
    color = soup.new_tag("text", x="55", y="105", fill="#FDB813", **{"font-size": "20"})
    color.string = "color"
    music = soup.new_tag(
        "text", x="97.5", y="105", fill="#939598", **{"font-size": "20"}
    )
    music.string = "music"
    group.append(color)
    group.append(music)

    link = soup.new_tag(
        "a",
        href="https://www.mycolormusic.com/",
        target="_blank",
        **{"xmlns:xlink": "http://www.w3.org/1999/xlink"},
    )
    link.append(group)
    svg.insert(0, link)

    title_group = soup.new_tag("g", id="song-title-group")
    title = soup.new_tag("text", x="210", y="105", fill="Black", **{"font-size": "30"})
    title.string = f"{page_title} - Page {page_num}"
    title_group.append(title)
    svg.insert(0, title_group)


def render_color_music(mei_file_path, title):
    """Render MEI to ColorMusic"""
    # Clear out existing SVGs
    for f in os.listdir(BASE_DIR):
        if f.endswith(".svg"):
            os.remove(os.path.join(BASE_DIR, f))

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
        tk.renderToSVGFile(
            os.path.join(BASE_DIR, f"{filename}-{page}-original.svg"), page
        )

        add_symbols_to_defs(svg.find("defs"))
        shift_svg_content(svg)

        for note in svg.find_all(class_="note"):
            render_note_to_colormusic(note, note.find_parent("g", class_="chord"))
            reorder_note(note)

        add_logo_and_title(svg, page, title)

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
