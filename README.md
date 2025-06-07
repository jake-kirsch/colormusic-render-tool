# colormusic-render-tool
### Renders Traditional Sheet Music to ColorMusic-style

Goal for prototype was to render a MEI file to ColorMusic-style SVG. Leveraged the existing work of others to solve the ColorMusic rendering problem with the least resistance.

Core logic for rendering found at render-service/app/renderer.py.

#### Steps

* Convert input file to MEI file (if applicable)
* Modify input MEI note elements with labels containing pitch, accidental, and duration details.  These details get lost in the initial rendering if not provided in labels.
* With the modified MEI use Verovio toolkit to render to SVG.
* Modify original SVG to ColorMusic-style.  Following actions performed:
    * Define symbols for square noteheads in the following combos for each square pitch: open/stem up, filled/stem up, open/stem down, filled/stem down, open/no stem, filled/no stem.  Append to defs.  These will be reusable during rendering.
    * For each note, apply render steps:
        * Determine pitch and duration by parsing label
        * Check if pitch is part of the "Square Pitches" group.  If so:
            * Determine stem direction (up/down/no stem)
            * Determine if open/filled based on duration (<= 2 should be open)
            * Extract *use* from the notehead and update *xlink:href* to the appropriate symbol def, ex. #E-open-stem-up
        * If pitch is part of "Circle Pitches" group then preserve shape of notehead but adjust fill color, stroke, and stroke-width.
    * For each note, reorder addition to DOM so that the stem is added *before* the notehead.  Notehead should be in front of the stem.
* Render SVGs to single-file PDF

<br>

### *Acknowledgements*

ColorMusic - Mike George - https://www.mycolormusic.com
<br>
Verovio - https://www.verovio.org/index.xhtml
<br>
Music Encoding Initiative (MEI) - https://music-encoding.org/
<br>
MusicXML - https://www.musicxml.com/
<br>
BeautifulSoup - https://pypi.org/project/beautifulsoup4/