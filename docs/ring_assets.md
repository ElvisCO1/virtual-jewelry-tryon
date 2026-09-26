# Ring test assets

Generated with the built-in image_gen tool using the imagegen skill. These are synthetic demonstration assets, not calibrated product photographs or crops from the original sheet. The design reference is now stored at `assets/references/pack_anillos.png`. The original sheet is unchanged.

- `assets/rings/demo/ring_front.png`: decorative view for the back of the hand.
- `assets/rings/demo/ring_back.png`: band view for the palm.
- Both have true alpha transparency, matched canvas size and horizontal band alignment, and assume an upright finger (asset angle -90 degrees).

## Front prompt

Use case: background-extraction / product-mockup. Reference image: the supplied labeled ring sheet, for gold solitaire ring design only. Create ONE clean production RGBA PNG sprite of its gold solitaire diamond ring's decorative front, for a 2D webcam finger overlay. Truly transparent background with an alpha channel, no checkerboard drawn, no background, no shadow outside the object, no text or labels, no hands. Orthographic view as seen on the BACK of a hand whose finger points straight up: gold band extends horizontally, bright round diamond centered on the band, symmetrical, NO full vertical circular hoop. Canvas 1024 x 512, ring extent about x=64 to 960 and y=64 to 448, optical/placement center exactly canvas center, diamond centered at (512,256). Show only visible front-facing surfaces; hidden rear band should not be visible. Polished gold and realistic diamond highlights, crisp clean antialiased alpha edges. One ring only, not a sheet.

## Back prompt

Use case: precise-object-edit. Edit target: the supplied single gold solitaire ring PNG. Create its matching BACK/BAND sprite for overlay on the PALM side of the finger. Preserve exact canvas dimensions, transparent alpha background, gold metal color, horizontal alignment and total left/right extent. Remove the diamond and prongs entirely because these lie behind the finger and are occluded in the palm view. Show only the smooth plain polished gold band, a slightly curved horizontal ribbon centered at the exact same image center (half width, half height). Band left/right endpoints match the reference ring. Band vertical thickness about 18 percent of canvas height. No visible full circular hoop, no gem, no labels, no text, no hand, no extra objects, no cast shadow, no background or checkerboard. Output ONE true RGBA transparent PNG with smooth antialiased edges. Same gold ring seen from its palm-side underside.

