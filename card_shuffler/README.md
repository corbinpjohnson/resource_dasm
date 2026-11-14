# Gravity comb shuffler for sleeved cards

A fully 3D-printed shuffler with no motor, springs, screws or moving parts.
Lower a 90 to 100 card sleeved deck into the top, lift two piles out of the
bins, stack them, repeat.

**Status: designed and simulated, not printed.** The geometry is checked by
the test suite and by a rigid-body physics simulation (MuJoCo). The design has
been through six versions, each driven by a failure in that simulation. The
current one delivers every card in 58 of 64 simulated drops under nominal
conditions (90 and 100 cards) and at least 98% of cards in every condition
except a nearly solid deck. It still has known limits, listed below, and a
simulation of rigid cards is not a print.

![section](section.png)
![assembly](assembly.png)

## How it works

1. **Hopper.** The deck goes in short edge down, lowered by its edges through
   the finger slots until it almost touches the blades. The whole machine
   leans back 2 degrees on wedge-shaped feet.
2. **Comb.** Seventeen blades, 5 mm apart at the rim, slice the deck into
   packets of about seven cards.
3. **Ramps.** Each channel has a 40 degree floor. Channels alternate left,
   right, left, right. A packet free-falls one card height, lands on a corner,
   tips onto its short edge and slides out sideways.
4. **Bins.** Left-going and right-going packets collect in two tilted bins
   against a full-height fence, with finger notches for lifting them out.
5. **Repeat.** Put the left pile on the right pile and go again.

## What makes the comb not jam

Getting 60 cards through a comb under their own weight was the whole problem.
Five things turned out to matter, and removing any one of them brings the jams
back (each is a test in section 9 of `test_shuffler.py`):

- **The blades fan out.** They are tilted like the ribs of a fan hinged 400 mm
  above the rim, under a degree apart. The bottoms of the cards can then spread
  by the thickness of all the blades while the tops stay together, and every
  channel gets wider on the way down. With parallel blades the same comb
  delivers 49% of cards.
- **Each blade thickens slowly.** One 0.2 mm layer at the tip, 1 mm thick
  110 mm lower. Slowly enough that no channel ever narrows: whatever the tips
  let in can fall. Thickening over 20 mm instead delivers 28%.
- **Blade faces are flush.** The taper runs right across each blade, ears
  included. A 0.5 mm step there caught cards as they swung out sideways.
- **The machine leans back 2 degrees.** Gravity then pulls every card slightly
  to one side, so none balances on a blade tip and arrives late. On a level
  machine about a third of drops leave a stray card. The lean has to be the
  whole machine: leaning only the hopper (the previous version) tilts the
  cards against half the channels, and a deck dropped from the top of the
  hopper then locked solid in 8 drops of 16.
- **The blade tips are thin enough to give.** The top 27 mm of each blade is a
  single 0.2 mm layer. Modelled as a rigid knife, a deck with a tenth of its
  thickness air jams in 25 drops of 32. Modelled as the PETG film it would
  really be, the tips give by under half a millimetre and the same deck
  delivers 99.6%. The result is the same from a third to three times the
  stiffness of PETG, so it is not finely tuned. Do not thicken the tips.

The slices that make up the comb have slightly wedge-shaped spacers, so
stacking them builds the fan. The machine is 90 mm deep inside at the rim and
143 mm at the table.

## Simulation results

`physics_sim.py` builds the card-facing surfaces from the same parameters as
the CAD and drops rigid cards into them. Two modelling choices change the
outcome, so both are explicit: card edges are rounded (a sleeve's folded edge)
or square (a rigid cut plate), and blade tips are flexible films or rigid.
Unless stated, results are for rounded edges and flexible tips, 32 drops each.

![physics](physics.png)

| Condition | Clean drops | Cards delivered | What went wrong |
|---|---|---|---|
| 100 cards | 30 of 32 | 99.9% | one card left in the comb, twice |
| 90 cards | 28 of 32 | 99.9% | one card left in the comb, four times |
| 100 cards, square edges | 8 of 32 | 98.3% | cards perched on blade tips |
| Dropped from 30 mm | 25 of 32 | 99.7% | a stray card in 7 drops |
| Dropped from 50 mm | 25 of 32 | 98.4% | a few cards left in 7 drops |
| Dropped from the top of the hopper (90 mm) | 21 of 32 | 98.5% | a few cards left in 10 drops |
| Deck leaning 4 degrees in the hopper | 32 of 32 | 100% | |
| Table 2 degrees off level, backwards | 31 of 32 | 100.0% | |
| Table 2 degrees off level, forwards | 21 of 32 | 99.6% | a stray card in 11 drops |
| Slippery cards (friction 0.12 / 0.20) | 32 of 32 | 100% | |
| Grippy cards (0.35 / 0.50) | 24 of 32 | 99.7% | cards stop short of the fence |
| Tight deck, 12% air | 25 of 32 | 99.3% | |
| Tight deck, 10% air | 19 of 32 | 99.0% | one or two cards left in 13 drops |
| Tight deck, 6% air | 10 of 32 | 94.2% | cards left in the comb in 22 drops |
| Rigid blade tips, 10% air | 4 of 32 | 70% | comb jams in 28 drops |

No condition here stops the whole deck. The cards left behind are single
cards, or a packet, that arrived late: cocked a few degrees in the collar,
held against a blade, or resting on a card that has not finished sliding out.

## Known limits

- **Stray cards.** Roughly one drop in ten at nominal conditions, and more
  often with tight decks or drops from a height, leaves one or a few cards
  standing in the comb. They are visible from above.
- **A nearly solid deck loses cards.** With flexible tips, decks down to a
  tenth air deliver 99%. One squeezed to 6% air delivers 94%. Thinner lower
  blades and a stronger fan made no difference.
- **Square-edged cards perch.** With square rigid edges, a card comes to rest
  on a blade tip in over half of drops. With rounded edges it is rare.
- **Level matters a little.** A table that cancels the machine's 2 degree lean
  brings back the stray cards of a level machine.
- **Piles are untidy.** The bins are much deeper than a 50-card pile, so the
  cards lean. They come out in order, but need squaring up.
- **Simulation limits.** Cards are rigid and friction is guessed. Blade-tip
  flexibility is modelled as a sprung hinge, which captures bending but not
  buckling or creasing.

### If cards are left behind

1. Lift the hopper off. Cards standing in the comb can be picked out and
   added to the deck for the next drop.
2. A packet stuck lower down can be pushed through with the printed
   `jam_key`, which is thin enough for any channel and long enough to reach
   the ramps.
3. If it happens often, riffle the deck once to let air in, and lower it by
   its edges instead of dropping it.

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

## Size and printing

Assembled: 315 wide x 149 deep x 326 tall mm (234 without the hopper). Needs a
bed of at least 250 x 250 mm; the wall pieces are 158 x 236 mm. Roughly 600 g
of filament at 15% infill (estimated from 1,000 cm3 of solid volume). No
supports.

| File (in `out/`) | Qty | Orientation (files are already oriented) |
|---|---|---|
| `slice_00` ... `slice_17` | 1 each | blade on the bed, rib up |
| `back_L`, `back_R`, `front_L`, `front_R` | 1 each | wall on the bed, half a bin floor standing up |
| `hopper` | 1 | upside down, throat ring on the bed |
| `bar_ear`, `bar_low`, `bar_bin` | 2 each | lying down, slot vertical (115, 150 and 162 mm long) |
| `wedge` | 6 | flat |
| `foot` | 2 | on its side |
| `jam_key` | 1 | flat |

`out/assembly.step` is the whole machine for viewing or editing in CAD.

Settings: 0.4 mm nozzle, **0.2 mm layers** (blade tips are exactly one layer),
3 perimeters. Use PETG for the slices: the top 27 mm of each blade is a
single-layer film and is meant to flex. PLA is fine for everything else.

## Assembly

1. Stack slices 00 to 17 in order. Slices 00 to 08 go blade towards the front,
   09 to 17 blade towards the back, so the two middle blades touch. The stack
   fans out towards the bottom; that is intended. The small notches on the
   right-hand edge form one diagonal line when the order is correct.
2. Stand the stack between the four wall pieces. The two halves of each bin
   floor meet in the middle.
3. Push the six bars through from the back (short ones at the top, longest
   through the bin fences) and tap a wedge, narrow end first, into each slot
   until snug. Do not over-drive them; squeezing the stack bows the blades.
4. Press the two feet onto the bottom edges, thick ends at the front so the
   machine leans back, and set the hopper on top.

## Use

Hold the deck by its long edges, short edge down. Lower it through the finger
slots until it is just above the blades and let go. Dropping it in from above
works, but leaves stray cards more often. Pinch each pile through the notches, put left on right, square up,
repeat.

## Changing it

All dimensions are fields of `Params` in `shuffler_design.py`.

```
pip install cadquery mujoco pytest matplotlib
python shuffler_design.py out     # regenerate STL + STEP
python render.py .                # regenerate the pictures
python physics_sim.py 12          # 12 simulated drops, about a minute
pytest test_shuffler.py           # 117 checks, about 20 minutes on 4 cores
pytest test_shuffler.py -k "not Physics and not Limits"    # geometry only, 15 s
```

- **Larger or double sleeves:** set `sleeve_w`, `sleeve_h`, `card_pitch`
  (about 0.8 for double-sleeved) and `n_channels=22`, then re-run the physics.
- **Fan angle:** hinge heights of 300 to 550 mm all worked; 250 squeezes the
  tops of the packets together and 1500 is too close to parallel.
- **Machine lean:** 2 degrees. 4 was as good at nominal but left more cards
  with tight decks, and 8 was worse outright.
- **Smaller decks:** set `n_cards` and `n_channels` (60 cards needs 12).
- **Bed of 320 mm or more:** the wall halves could be merged into single
  plates; the split at the centre line exists only to fit 250 mm beds.

## Tried and rejected

Each of these was simulated and made things worse or no better: raked
(scissor-like) blade tips, a deeper chevron, a two-stage comb with alternate
blades starting lower, lane walls reaching into the bins at two heights, a
hopper flared below the ring, a ring raised above the deck, a hopper that
leans on its own, a single leading centre blade, wider blade spacing, and
thinner lower blades.
