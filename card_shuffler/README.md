# Gravity comb shuffler for sleeved cards

A fully 3D-printed shuffler with no motor, springs, screws or moving parts.
Drop a 90 to 100 card sleeved deck into the top, rock the machine front and
back on the table, gather the two piles, stack them, repeat.

**Status: designed and simulated, not printed.** The geometry is checked by
the test suite and by a rigid-body physics simulation (MuJoCo). The design has
been through ten versions, each driven by a failure in that simulation. The
current one delivers at least 99.5% of cards in every condition simulated,
and every card in 31 or 32 drops of 32 in most of them. The exception is the
bottom edge of the cards: a sleeve's welded seam can leave a card or two
standing on the blades. Rocking the machine onto its front and back edges
clears every card in 60 drops of 64 (see below). A simulation of rigid cards is
not a print.

![section](section.png)
![assembly](assembly.png)

## How it works

1. **Hopper.** The deck goes in short edge down. It can be lowered by its
   edges through the finger slots or simply dropped in from the top.
2. **Comb.** Seventeen blades, 5 mm apart at the rim, slice the deck into
   packets of about seven cards.
3. **Ramps.** Each channel has a 46 degree floor. Channels alternate left,
   right, left, right. A packet free-falls one card height, lands on a corner,
   tips onto its short edge and slides out sideways.
4. **Bins.** Left-going and right-going packets collect in two tilted bins
   against a full-height fence, with finger notches for lifting them out. The
   bins are 35 mm longer than a card.
5. **Repeat.** Put the left pile on the right pile and go again.

## What makes the comb not jam

Getting 60 cards through a comb under their own weight was the whole problem.
Seven things turned out to matter, and removing any one of them brings the jams
back (each is a test in section 9 of `test_shuffler.py`):

- **The blades fan out.** They are tilted like the ribs of a fan hinged 400 mm
  above the rim, under a degree apart. The bottoms of the cards can then spread
  by the thickness of all the blades while the tops stay together, and every
  channel gets wider on the way down. With parallel blades the same comb
  delivers 49% of cards.
- **Each blade is a film at the top and thickens slowly.** The top 60 mm of
  each blade is a 0.2 mm film; below that it thickens one 0.1 mm layer at a
  time to 1 mm, 80 mm further down. No channel ever narrows on the way down,
  so whatever the tips let in can fall. Thickening over 20 mm delivered 28%.
- **Blade faces are flush.** The taper runs right across each blade, ears
  included. A 0.5 mm step there caught cards as they swung out sideways.
- **Nothing leans.** Two earlier versions leaned the hopper, then the whole
  machine, to stop cards balancing on blade tips and arriving late. A leaning
  hopper tilts the cards against half the channels, and a deck dropped from
  the top then locked solid in 8 drops of 16. Once the bins were fixed (below)
  neither lean was needed.
- **The film gives way to a squeezed packet.** Modelled as rigid knives,
  blades jam a deck with a tenth of its thickness air in 25 drops of 32;
  modelled as the PETG film they would be, they give by under a millimetre and
  the deck goes through. The film has to be long: eight cards squeezed to
  6% air are 5.3 mm, and the channel is only that wide 45 mm down. With the
  film ending at 27 mm such decks lost a card in ten; at 60 mm they lose one in
  two hundred. The result holds for plastic half or twice as stiff as PETG. A
  75 mm film is too floppy. Do not thicken the tips.

- **The comb is printed in 0.1 mm layers.** A blade printed flat thickens one
  layer at a time, and every layer is a small ledge on the wall cards slide
  down. With 0.2 mm ledges a deck with a tenth air went from 32 clean drops in
  32 to 29, and a nearly solid one from 90% delivered to 78%.
- **Cards must get clear of the tower.** With 40 degree ramps and bins barely
  longer than a card, some cards stopped short of the fence with a corner
  still under the tower, and later cards landed on them. Steeper ramps and
  longer bins took a drop from the top of the hopper from 21 clean drops in
  32 to 32, and a tight deck from 19 to 31.

The slices that make up the comb have slightly wedge-shaped spacers, so
stacking them builds the fan. The machine is 90 mm deep inside at the rim and
152 mm at the table.

## Simulation results

`physics_sim.py` builds the card-facing surfaces from the same parameters as
the CAD and drops rigid cards into them. Two modelling choices change the
outcome, so both are explicit: card edges are rounded (a sleeve's folded edge)
or square (a rigid cut plate), and blade tips are flexible films or rigid.
Unless stated, results are for rounded edges and flexible tips, 32 drops each.

![physics](physics.png)

Blades modelled as printed, thickening in 0.1 mm steps, with flexible film
tips, rounded card edges:

| Condition | Clean drops | Cards delivered | What went wrong |
|---|---|---|---|
| 100 cards | 32 of 32 | 100% | |
| 90 cards | 32 of 32 | 100% | |
| 60 cards | 32 of 32 | 100% | |
| Dropped from 30 mm | 32 of 32 | 100% | |
| Dropped from 50 mm | 32 of 32 | 100% | |
| Dropped from the top of the hopper (90 mm) | 32 of 32 | 100% | |
| Deck leaning 4 degrees in the hopper | 31 of 32 | 99.7% | |
| Table 3 degrees off level, either way | 32 of 32 each | 100% | |
| Slippery cards (friction 0.12 / 0.20) | 32 of 32 | 100% | |
| Grippy cards (friction 0.35 / 0.50) | 31 of 32 | 100.0% | |
| Tight deck, 12% air | 32 of 32 | 100% | |
| Tight deck, 10% air | 31 of 32 | 100.0% | |
| Tight deck, 6% air | 24 of 32 | 99.5% | a card left in 8 drops |

### The bottom edge of the cards

How the bottom edge of a card meets a 0.2 mm blade tip turns out to matter
more than anything else left. Four edge models, nominal conditions:

| Bottom edge | Clean drops | Cards delivered |
|---|---|---|
| Rounded (radius half the card's thickness) | 32 of 32 | 100% |
| Square, corners rounded 0.2 mm | 24 of 32 | 99.8% (earlier blade model) |
| Square | 10 of 32 | 98.7% |
| Sleeve seam: a 1.5 mm x 0.15 mm welded flange under the card | 2 of 32 | 97.3% |

A sleeve is welded shut below the card, so the seam is probably the closest
model to sleeved cards, and the worst. Modelling the seam as hinged
polypropylene instead of rigid changes nothing: a 1.5 mm flap is stiff on the
scale of a 2 g card. What goes wrong is always the same: the last few cards to
leave have room to lean, and one comes to rest with its edge on a blade tip and
its top against the hopper.

**Rocking the machine clears them.** Lift the front about a centimetre, so it
pivots on its back feet, and let it drop; then the same with the back. In the
simulation this is modelled from the motion itself: while the machine is
tipped, gravity leans in its frame; when it lands, every card keeps the
velocity its own part of the machine had, which is largest high up and far
from the pivot.

| Condition | No handling | Rocked front and back (1 cm) |
|---|---|---|
| Sleeve seam (64 drops) | about 1 in 16 clean | 60 of 64, 99.9% |
| Sleeve seam, deck dropped from the top | 8 of 32, 98.8% | 31 of 32, 100.0% |
| Sleeve seam, 90 cards | | 30 of 32, 99.9% |
| Square edges | 10 of 32, 98.7% | 29 of 32, 99.9% |
| Tight deck, 6% air (rounded edges) | 24 of 32, 99.5% | 26 of 32, 99.7% |

Rocking by only 5 mm cleared 28 of 32. On a soft table, where the machine takes
15 or 30 ms to stop instead of stopping at once, it cleared 29 and 26 of 32. Other handling, simulated the same way,
does not work:

| Handling of seam-edged cards | Clean drops |
|---|---|
| None | 1 of 16 |
| Lift 1 cm and drop it flat, twice | 1 of 16 (the cards just keep falling onto the tips) |
| Tip it slowly 15 or 25 degrees front and back, no landing | 7 of 16 |
| Tip it slowly side to side | 1 of 16 |
| Rock it front and back | 16 of 16 |

Corners rounded to 0.2 mm, the sweep shows, do most of the work too:

| Corner radius on a square edge | Clean drops |
|---|---|
| 0 | 12 of 32 |
| 0.05 mm | 9 of 32 |
| 0.10 mm | 11 of 32 |
| 0.15 mm | 20 of 32 |
| 0.20 mm | 24 of 32 |
| 0.30 mm (fully round) | 32 of 32 |

### Loads

- **Blades.** The film at the top of each blade is checked by the test suite
  to stay under 5 MPa of bending stress in the harshest cases, against roughly
  50 MPa that PETG can take. Not
  modelled: a card corner denting the film locally.
- **Cards.** The fastest card moves at 1.6 m/s when the deck is lowered in and
  1.9 m/s when it is dropped from the top: the same as a card dropped onto a
  table from 13 to 18 cm.

## Known limits

- **Sleeve seams.** Simulated with a welded seam, a card or two is left on the
  blades in most drops, and rocking the machine front and back clears it in
  60 drops of 64. Real seams vary; only a real deck will say whether the routine is
  needed every time or never. Design changes tried instead (steeper blade
  roof, thinner tips, a weighted plate on the deck) did not help.
- **Drop count.** About 15 drops for casual play and two dozen for a thorough
  shuffle of 100 cards. By the same measure, hand riffles of a 100-card deck
  need about 6: a drop is worth about a quarter of a riffle, because a riffle
  separates neighbouring cards at about every other card and a drop only where
  a blade cuts. That is set by the seven-card packets; finer combs were tried
  again with the long film and still left stray cards; smaller packets
  brought the jams back. Restacking habits (turning the deck round, either pile
  on top, cutting) make no difference, and neither would three or four output
  piles: packets go to the piles in a fixed rotation, so extra piles add no
  randomness.
- **Piles need gathering.** Cards land standing in their own lanes, so a
  50-card pile is spread across about 100 mm of a 150 mm-deep bin. Pushing it
  together with a finger through each of the two notches (front and back
  walls) squares it to 34 to 47 mm in the simulation, with every card staying
  in the bin and the order almost unchanged (a few neighbouring cards swap,
  which only adds to the shuffle). Tilting the bin floors did not gather them.
- **Simulation limits.** Cards are rigid and friction is guessed. Blade-film
  flexibility is modelled as a sprung hinge, which captures bending but not
  buckling or creasing.

### If cards are left behind

1. Rock the machine: lift the front about a centimetre and let it drop, then
   the back. Lifting it flat and dropping it does not help.
2. Lift the hopper off. Cards standing in the comb can be picked out and added
   to the deck for the next drop.
3. A packet stuck lower down can be pushed through with the printed
   `jam_key`, which is thin enough for any channel and long enough to reach
   the ramps.

## How many drops

One drop is an inverse riffle shuffle done in seven-card clumps, so it takes
more drops than a hand riffle. Removing the jams also removed a side effect
that had been helping: early versions delayed a card at about half the cuts,
which moved single cards around.

| Drops | Adjacent pairs still together, 100 cards (model) |
|---|---|
| 1 | 82% |
| 5 | 37% |
| 10 | 15% |
| 15 | 6% |
| 20 | 3% |
| 25 | 2% |

A fully random 100-card deck scores 1%. By eight drops every card is equally
likely to be at any position. Fifteen drops is reasonable for casual play;
about two dozen is thorough. A finer comb needs fewer (about 16 with
five-card packets) but is less tolerant of tight decks. The model is
`shuffle_sim.py`, calibrated against consecutive simulated drops of the
60-card version.

## Test before you build

The one thing the simulation cannot tell you is how the bottom edges of your
sleeves behave on a 0.2 mm blade tip. `python make_test_kit.py` exports a
30-card, 6-channel version to `out_test_kit/`: the same blades, film, fan,
ramps, bins and hopper, in 28 pieces and about half the plastic.

Drop 30 of your sleeved cards through it ten times, without rocking, and count
the cards left standing in the comb. The simulation predicts, over ten drops:

| Cards left standing | Your sleeves behave like | What it means for the full machine |
|---|---|---|
| about 1 | a rounded edge | rocking is rarely needed |
| about 10 | a welded seam | rock it after every drop; with rocking the test kit left none in 32 drops |
| about 30 | a square-cut edge | rocking is needed and may not be enough; tell me what you see |

The test kit is also a usable shuffler for smaller decks.

## Size and printing

Assembled: 361 wide x 158 deep x 369 tall mm (277 without the hopper). Needs a
bed of at least 250 x 250 mm; the largest pieces are 180 x 232 mm. Roughly
650 g of filament at 15% infill (estimated from 1,130 cm3 of solid volume). No
supports. 40 pieces in all.

| File (in `out/`) | Qty | Orientation (files are already oriented) |
|---|---|---|
| `slice_00` ... `slice_17` | 1 each | blade on the bed, rib up |
| `back_L`, `back_R`, `front_L`, `front_R` | 1 each | wall on the bed, half a bin floor standing up |
| `upper_front`, `upper_back` | 1 each | flat |
| `hopper` | 1 | upside down, throat ring on the bed |
| `bar_ear`, `bar_low`, `bar_bin` | 2 each | lying down, slot vertical (115, 153 and 172 mm long) |
| `wedge` | 6 | flat |
| `foot` | 2 | on its side |
| `jam_key` | 1 | flat |

`out/assembly.step` is the whole machine for viewing or editing in CAD.

Settings: 0.4 mm nozzle, 3 perimeters. Print the comb slices with
`print/comb_slices_prusaslicer.ini` (0.1 mm layers, 0.1 mm first layer, and at
least 0.6 mm of solid shell top and bottom: with PrusaSlicer's default three
solid layers the middle of each 1 mm blade is printed as sparse infill; the
test suite slices a comb slice to check this). Print them in PETG at **0.1 mm
layers**: the top 60 mm of each blade is a 0.2 mm film that is meant
to flex, and the blade thickens one layer at a time below it. The film is the
first two layers on the bed: use a smooth flexible plate and let it cool before
peeling the slice off, so the film is not creased. Everything else can
be 0.2 mm layers in PLA.

## Assembly

1. Stack slices 00 to 17 in order. Slices 00 to 08 go blade towards the front,
   09 to 17 blade towards the back, so the two middle blades touch. The stack
   fans out towards the bottom; that is intended. The small notches on the
   right-hand edge form one diagonal line when the order is correct.
2. Stand the stack between the four lower wall pieces; the two halves of each
   bin floor meet in the middle. Add the two upper wall plates, which overlap
   the lower pieces in a half lap.
3. Push the six bars through from the back (short ones at the top, longest
   through the bin fences) and tap a wedge, narrow end first, into each slot
   until snug. Do not over-drive them; squeezing the stack bows the blades.
4. Press the two feet onto the bottom edges and set the hopper on top.

## Use

Hold the deck by its long edges, short edge down. Lower it through the finger
slots until it is just above the blades and let go, or drop it in from the top
of the hopper. Then rock it front and back (see "If cards are left behind").
Push each pile together with a finger through each notch, lift it out, put
left on right, square up, repeat.

## Changing it

All dimensions are fields of `Params` in `shuffler_design.py`.

```
pip install cadquery mujoco pytest matplotlib
python shuffler_design.py out     # regenerate STL + STEP
python make_test_kit.py           # the 30-card test version, to out_test_kit/
python render.py .                # regenerate the pictures
python physics_sim.py 12          # 12 simulated drops, about a minute
pytest test_shuffler.py           # 147 checks, about an hour on 4 cores
pytest test_shuffler.py -k "not Physics and not Limits"    # geometry only, 15 s
```

- **Larger or double sleeves:** set `sleeve_w`, `sleeve_h`, `card_pitch`
  (about 0.8 for double-sleeved) and `n_channels=22`, then re-run the physics.
- **Fan angle:** hinge heights of 300 to 550 mm all worked; 250 squeezes the
  tops of the packets together and 1500 is too close to parallel.
- **Leaning the machine:** `machine_tilt_deg` cuts the feet as wedges. Not
  needed with the current bins.
- **Smaller decks:** set `n_cards` and `n_channels` (60 cards needs 12).
- **Very tight decks:** `channel_w=4.5` (5.5 mm blade spacing) suits a deck
  known to be squeezed nearly solid; it costs a little for normal decks.
- **Larger beds:** the end walls are in three pieces each only to fit 250 mm
  beds.

## Tried and rejected

Each of these was simulated and made things worse or no better: raked
(scissor-like) blade tips, a deeper chevron, a two-stage comb with alternate
blades starting lower, lane walls reaching into the bins at two heights, a
hopper flared below the ring, a ring raised above the deck, a hopper that
leans on its own, a single leading centre blade, wider blade spacing,
thinner lower blades, a forward-shifted hopper, a finer comb, blades on the
outer side of their channels, a second row of short blades halfway down, and
one-layer (0.1 mm) blade tips, bin floors tilted towards the back, a steeper
blade roof, a 75 mm blade film, three or four output piles, a weighted
plate laid on top of the deck to stop the last cards leaning, and, with the
long film, finer combs (4.5 and 4.0 mm spacing: about 22 and 19 drops instead
of 24, but 11 or 12 clean drops in 16 instead of 16).
