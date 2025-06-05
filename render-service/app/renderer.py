# Standard Libraries
import io
import math
import os

# Third-party Libraries
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import verovio

# Constants
BASE_DIR = "app-frontend/static/rendered_svgs"
STROKE_WIDTH = 20

# Chromatic Scale (Flat Variant)
CHROMATIC_SCALE = ["C", "Df", "D", "Ef", "E", "F", "Gf", "G", "Af", "A", "Bf", "B", ]
CHROMATIC_SCALE_NOTE_COUNT = len(CHROMATIC_SCALE)

# Pitch color mapping (exhaustive list containing both flat and sharp variants)
PITCH_COLORS = {
    "A": "#fdbb13", 
    "B": "#A6CE39", "Cf": "#A6CE39", 
    "C": "#DA1E48", "Bs": "#DA1E48", 
    "D": "#F58220",
    "E": "#F3DC0B", "Ff": "#F3DC0B",
    "F": "#AB218E", "Es": "#AB218E",
    "G": "#F04E23",
    "Gs": "#0098DD", "Af": "#0098DD", 
    "As": "#823F98", "Bf": "#823F98",
    "Cs": "#00A995", "Df": "#00A995", 
    "Ds": "#3763AF", "Ef": "#3763AF",
    "Fs": "#39B54A", "Gf": "#39B54A",
}

# Pitches that are Squares in ColorMusic (exhaustive list containing both flat and sharp variants)
SQUARE_PITCHES = ["Af", "Gs", 
                  "Bf", "As", 
                  "C", "Bs", 
                  "D", 
                  "E", "Ff", 
                  "Gf", "Fs", ]

tk = verovio.toolkit()


# ====== Processing Functions ======
def parse_mei(mei_data):
    return BeautifulSoup(mei_data, "xml")


def simplify_pitch(note_label):
    """Determine simplified pitch based on note label.  In cases of double sharps, flats, etc."""
    pitch_idx = CHROMATIC_SCALE.index(note_label[0])
    
    for accid in note_label[1:]:
        if accid == "f":
            pitch_idx -= 1
        elif accid == "s":
            pitch_idx += 1

        # Reset pitch_idx
        if pitch_idx >= CHROMATIC_SCALE_NOTE_COUNT:
            pitch_idx = pitch_idx - CHROMATIC_SCALE_NOTE_COUNT

    return CHROMATIC_SCALE[pitch_idx]


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
        
        # Get duration
        dur = note.get("dur")
        if dur is None:
            chord = note.find_parent("chord")

            dur = chord.get("dur")
        
        # Get tied note
        tied_note_id = ties.get(note_id)
        
        # Check if note is part of a tie, if it is then persist with label of leading note
        if tied_note_id:
            tied_note = soup.find("note", attrs={"xml:id": tied_note_id})
            # f"{pname.upper()}{accid}:{dur}"
            # Split out duration, use note and accid from tied start note
            prefix_label = tied_note.get("label").split(":")[0]
            
            note["label"] = f"{prefix_label}:{dur}"
        else:
            pname = note.get("pname")
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
                accid = "s"
            elif accid_val == "ss":
                # Double Sharp
                accid = "ss"
            elif accid_val == "f":
                # Flat
                accid = "f"
            elif accid_val == "ff":
                # Double Flat
                accid = "ff"
            elif accid_val == "n":
                # If natural skip adding accid
                accid = ""
            else:
                if sig and sig not in ["0", "1s", "2s", "3s", "4s", "5s", "6s", "7s",
                                       "1f", "2f", "3f", "4f", "5f", "6f", "7f", ]:
                    raise ValueError(f"Unhandled key signature: {sig}!")

                if sig == "0":
                    # 0 - No sharps or flats
                    # C Major -> C - D - E - F - G - A - B - (C)
                    # A Minor -> A - B - C - D - E - F - G - (A)
                    accid = ""
                elif sig == "1s" and  pname.upper() == "F":
                    # 1s - 1 sharp
                    # G Major -> G - A - B - C - D - E - F♯ - (G)
                    # E Minor -> E - F♯ - G - A - B - C - D - (E)
                    accid = "s"
                elif sig == "2s" and pname.upper() in ["C", "F", ]:
                    # 2s - 2 sharps
                    # D Major -> D – E – F♯ – G – A – B – C♯ – (D)
                    # B Minor -> B – C♯ – D – E – F♯ – G – A – (B)
                    accid = "s"
                elif sig == "3s" and pname.upper() in ["C", "F", "G", ]:
                    # 3s - 3 sharps
                    # A Major -> A - B - C♯ - D - E - F♯ - G♯ - (A)
                    # F# Minor -> F♯ - G♯ - A - B - C♯ - D - E - (F♯)
                    accid = "s"
                elif sig == "4s" and pname.upper() in ["C", "D", "F", "G", ]:
                    # 4s - 4 sharps
                    # E Major -> E – F♯ – G♯ – A – B – C♯ – D♯ – (E)
                    # C# Minor -> C♯ – D♯ – E – F♯ – G♯ – A – B – (C♯)
                    accid = "s"
                elif sig == "5s" and pname.upper() in ["A", "C", "D", "F", "G", ]:
                    # 5 sharps
                    # B Major -> B – C♯ – D♯ – E – F♯ – G♯ – A♯ – (B)
                    # G♯ Minor -> G♯ – A♯ – B – C♯ – D♯ – E – F♯ – (G♯)
                    accid = "s"
                elif sig == "6s" and pname.upper() in ["A", "C", "D", "E", "F", "G", ]:
                    # 6 sharps
                    # F♯ Major -> F♯ – G♯ – A♯ – B – C♯ – D♯ – E♯ – (F♯)
                    # D♯ Minor -> D♯ – E♯ – F♯ – G♯ – A♯ – B – C♯ – (D♯)
                    accid = "s"
                elif sig == "7s" and pname.upper() in ["A", "B", "C", "D", "E", "F", "G", ]:
                    # 7 sharps
                    # C♯ Major -> C♯ – D♯ – E♯ – F♯ – G♯ – A♯ – B♯ – (C♯)
                    # A♯ Minor -> A♯ – B♯ – C♯ – D♯ – E♯ – F♯ – G♯ – (A♯)
                    accid = "s"
                elif sig == "1f" and pname.upper() == "B":
                    # 1f - 1 flat
                    # F Major -> F - G - A - B♭ - C - D - E - (F)
                    # D Minor -> D - E - F - G - A - B♭ - C - (D)
                    accid = "f"
                elif sig == "2f" and pname.upper() in ["B", "E", ]:
                    # 2f - 2 flats
                    # B♭ Major -> B♭ – C – D – E♭ – F – G – A – (B♭)
                    # G Minor -> G – A – B♭ – C – D – E♭ – F – (G)
                    accid = "f"
                elif sig == "3f" and pname.upper() in ["A", "B", "E", ]:
                    # 3f - 3 flats
                    # E♭ Major -> E♭ – F – G – A♭ – B♭ – C – D – (E♭)
                    # C Minor -> C – D – E♭ – F – G – A♭ – B♭ – (C)
                    accid = "f"
                elif sig == "4f" and pname.upper() in ["A", "B", "D", "E", ]:
                    # 4f - 4 flats
                    # A♭ Major -> A♭ – B♭ – C – D♭ – E♭ – F – G – (A♭)
                    # F Minor -> F – G – A♭ – B♭ – C – D♭ – E♭ – (F)
                    accid = "f"
                elif sig == "5f" and pname.upper() in ["A", "B", "D", "E", "G", ]:
                    # 5 flats
                    # D♭ Major -> D♭ – E♭ – F – G♭ – A♭ – B♭ – C – (D♭)
                    # B♭ Minor -> B♭ – C – D♭ – E♭ – F – G♭ – A♭ – (B♭)
                    accid = "f"
                elif sig == "6f" and pname.upper() in ["A", "B", "C", "D", "E", "G", ]:
                    # 6 flats
                    # G♭ Major -> G♭ – A♭ – B♭ – C♭ – D♭ – E♭ – F – (G♭)
                    # E♭ Minor -> E♭ – F – G♭ – A♭ – B♭ – C♭ – D♭ – (E♭)
                    accid = "f"
                elif sig == "7f" and pname.upper() in ["A", "B", "C", "D", "E", "F", "G", ]:
                    # 7 flats
                    # C♭ Major -> C♭ – D♭ – E♭ – F♭ – G♭ – A♭ – B♭ – (C♭)
                    # A♭ Minor -> A♭ – B♭ – C♭ – D♭ – E♭ – F♭ – G♭ – (A♭)
                    accid = "f"
                else:    
                    accid = ""
            
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
    note_label, dur = note.find("title", class_="labelAttr").text.split(":")

    pitch = simplify_pitch(note_label)
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
    shift_group = soup.new_tag("g", transform="translate(0, 40)")
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
    x_offset, y_offset = 25, 25
    shape_opacity = 1.0
    shape_stroke_width = 0.2

    radius = 15
    ratio = radius / 65

    print(f"Ratio: {ratio}")

    shape_scale = 1.4
    square_width = 15 * ratio * shape_scale
    circle_radis = 8.5 * ratio * shape_scale
    
    for pitch, angle in [
        ("Ef", 0),
        ("D", 30),
        ("Df", 60),
        ("C", 90),
        ("B", 120),
        ("Bf", 150),
        ("A", 180),
        ("Af", 210),
        ("G", 240),
        ("Gf", 270),
        ("F", 300),
        ("E", 330),
    ]:
        if pitch in SQUARE_PITCHES:
            x = (radius * math.cos(math.radians(angle))) + x_offset - (square_width / 2)
            y = -(radius * math.sin(math.radians(angle))) + y_offset - (square_width / 2)
            cx, cy = x + square_width / 2, y + square_width / 2
            shape = soup.new_tag(
                "rect",
                x=x,
                y=y,
                width=square_width,
                height=square_width,
                fill=PITCH_COLORS[pitch],
                transform=f"rotate({90 - angle} {cx} {cy})",
                style=f"stroke:black; stroke-width:{shape_stroke_width}; opacity:{shape_opacity}",
            )
        else:
            shape = soup.new_tag(
                "circle",
                cx=(radius * math.cos(math.radians(angle))) + x_offset,
                cy=-(radius * math.sin(math.radians(angle))) + y_offset,
                r=circle_radis,
                fill=PITCH_COLORS[pitch],
                style=f"stroke:black; stroke-width:{shape_stroke_width}; opacity:{shape_opacity}",
            )
        group.append(shape)

    # # Text
    # color = soup.new_tag("text", x="55", y="35", fill="#FDB813", **{"font-size": "20"})
    # color.string = "color"
    # music = soup.new_tag(
    #     "text", x="97.5", y="35", fill="#939598", **{"font-size": "20"}
    # )
    # music.string = "music"
    # group.append(color)
    # group.append(music)

    link = soup.new_tag(
        "a",
        href="https://www.mycolormusic.com/",
        target="_blank",
        **{"xmlns:xlink": "http://www.w3.org/1999/xlink"},
    )
    link.append(group)

    if page_num == 1:
        svg.insert(0, link)

    title_group = soup.new_tag("g", id="song-title-group")
    title = soup.new_tag(
        "text",
        x="98%", # Near the right edge
        y="15",
        fill="Black",
        **{"font-size": "10", "text-anchor": "end"}  # Align text to the right
    )
    title.string = f"{page_title} - Page {page_num}"
    title_group.append(title)
    svg.insert(0, title_group)


def extract_score_title(soup):
    mei_head = soup.find("meiHead")
    
    song_name = None
    composers_str = None
    if mei_head:
        file_desc = mei_head.find("fileDesc")

        if file_desc:
            title_statement = file_desc.find("titleStmt")

            if title_statement:
                title = title_statement.find("title")

                if title:
                    song_name = title.get_text(strip=True)
            
                resp_statement = title_statement.find("respStmt")

                if resp_statement:
                    composers = [tag.get_text(strip=True) for tag in resp_statement.find_all("persName")]
                    composers_str = ", ".join(composers)

    score_title = None
    if song_name and composers_str:
        score_title = f"{song_name} - {composers_str}"
    elif song_name:
        score_title = song_name
    elif composers:
        score_title = composers_str

    return score_title


def render(filename, mei_data, title, bucket, session_id):
    """Render MEI to ColorMusic"""
    
    # Label notes in MEI
    soup = parse_mei(mei_data)
    mei_data = str(label_notes(soup))

    score_title = extract_score_title(soup)

    # User provided title overrides score title pulled from MEI
    if not title and score_title:
        title = score_title

    if not title:
        title = "Unknown"

    filename = filename.rsplit(".", 1)[0]
    # filename = mei_filename.split(".mei")[0]
    # modified_mei_filename = f"{filename}-mod.mei"

    # blob = bucket.blob(f"{session_id}/{modified_mei_filename}")
    # blob.upload_from_string(str(labeled_soup))

    # mei_data = blob.download_as_text(encoding="utf-8")
    
    tk.setOptions({
        "pageWidth": 2159,    # 210 mm * 10
        "pageHeight": 2794,   # 297 mm * 10
        "scale": 40,          # default is 40, adjust if needed (higher = bigger)
        "adjustPageHeight": True,  # Automatically adjust page height to content
        "svgViewBox": True,
    })

    tk.loadData(mei_data)

    svg_filenames = []
    svg_html_parts = []
    for page in range(1, tk.getPageCount() + 1):
        svg = BeautifulSoup(tk.renderToSVG(page), "xml")
        
        # Load original for reference
        blob = bucket.blob(f"{session_id}/{filename}-{page}-original.svg")
        blob.upload_from_string(tk.renderToSVG(page))

        add_symbols_to_defs(svg.find("defs"))
        # shift_svg_content(svg)

        for note in svg.find_all(class_="note"):
            render_note_to_colormusic(note, note.find_parent("g", class_="chord"))
            reorder_note(note)

        # Adjust opacity for visible accids
        for accid in svg.find_all(class_="accid"):
            accid["opacity"] = 0.5

        add_logo_and_title(svg, page, title)

        # Footer
        footer = svg.new_tag("comment")
        footer.string = """
            Generated and modified using the following libraries:
            - BeautifulSoup: For parsing and manipulating the SVG.
            - Verovio: For rendering MEI files to SVG. Visit Verovio at https://www.verovio.org
        """
        svg.find("svg").append(footer)
        
        svg_filename = f"{filename}-{page}-colormusic.svg"
        blob = bucket.blob(f"{session_id}/{svg_filename}")
        blob.upload_from_string(str(svg))
        svg_html_parts.append(f"<div style='page-break-after: always'>{str(svg)}</div>")
        
        svg_filenames.append(svg_filename)

    print("Rendered SVG filenames:")
    for svg_filename in svg_filenames:
        print(svg_filename)

    # Generate PDF and upload to bucket
    html_content = f"""
    <html>
      <head>
        <style>
          @page {{ size: Letter; margin: 0 }}
          body {{ margin: 0 }}
        </style>
      </head>
      <body>
        {''.join(svg_html_parts)}
      </body>
    </html>
    """

    pdf_io = io.BytesIO()

    # Generate PDF using Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="load")

        pdf_bytes = page.pdf(format="Letter", print_background=True)
        browser.close()

    # Write to in-memory buffer
    pdf_io.write(pdf_bytes)
    pdf_io.seek(0)  # Reset to start of buffer

    # Upload to GCS
    pdf_filename = f"{filename}-colormusic.pdf"
    blob = bucket.blob(f"{session_id}/{pdf_filename}")

    blob.upload_from_file(pdf_io, content_type="application/pdf")

    # return svg_filenames
    return svg_html_parts[:1]
