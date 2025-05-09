# colormusic-render-tool
### Renders Traditional Sheet Music to ColorMusic-style

Goal for prototype was to render a MEI file to ColorMusic-style SVG. Leveraged the existing work of others to solve the ColorMusic rendering problem with the least resistance.

Note prototype was done in a speedily manner for POC, structure/formatting was low priority.  Script found at prototype/render.py.  Test outputs can be found at prototype/tests.

#### Steps

* Modify input MEI note elements with labels containing pitch and duration details.  These details get lost in the initial rendering if not provided in labels.
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
    * Create ColorMusic logo as SVG

<br>

### *Acknowledgements*

ColorMusic - Mike George - https://www.mycolormusic.com
<br>
BeautifulSoup used for MEI/SVG modifications.
<br>
Verovio used for rendering MEI files to SVG. Visit Verovio at https://www.verovio.org for details.