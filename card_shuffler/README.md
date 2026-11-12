# Gravity comb shuffler for sleeved cards

A fully 3D-printed shuffler with no motor, springs, screws or moving parts.
Drop a 60-card sleeved deck in the top, lift two piles out of the bins, stack
them, drop again.

**Status: designed and simulated, not printed.** The geometry is checked by
the test suite and by a rigid-body physics simulation (MuJoCo). The first
version failed that simulation badly; this is the revised design that passes
it. A simulation of rigid cards is still not a print, so expect some tuning.

![section](section.png)
![assembly](assembly.png)

## How it works

1. **Hopper.** The deck goes in short edge down. A ring at the top of the
   hopper holds the deck upright; it is 6 mm deeper than the deck, and where
   the deck sits in that slack decides where the blades cut.
2. **Comb.** Thirteen 0.8 mm blades, 5 mm apart, slice the deck into packets
   of seven cards. The tips form a chevron with one centre blade highest and
   each neighbour 3.5 mm lower.
3. **Ramps.** Each channel has a 40 degree floor. Channels alternate left,
   right, left, right. A packet free-falls one card height, lands on a corner,
   tips onto its short edge and slides out sideways.
4. **Bins.** Left-going and right-going packets collect in two tilted bins
   against a tall end stop, with finger notches for lifting them out.
5. **Repeat.** Put the left pile on the right pile and drop again.

## What the physics simulation showed

`physics_sim.py` builds the card-facing surfaces from the same parameters as
the CAD and drops 60 rigid 0.6 mm cards into them.

![physics](physics.png)

The first version (1.2 mm blades, 4.7 mm apart, 26 mm end stops, no hopper)
failed in three ways, each now kept as a regression test:

| Fault found | Cause | Fix |
|---|---|---|
| About 40 of 60 cards jammed in the comb | Thick blades force the deck to fan out; tilted cards lock in the slots | Blades 0.8 mm at 5 mm pitch |
| Cards that got through somersaulted out of the bins | End stop was below a card's centre of gravity | Stop raised from 26 to 60 mm |
| Deck toppled over the rim while being combed | Nothing held the top of the deck | Hopper with a throat ring |

Results for the revised design:

- **16 single drops:** 945 of 960 cards reached a bin (98%). Eleven drops were
  perfect, four left one or two cards in the hopper, and one jammed a packet
  of ten. No card left the machine.
- **12 consecutive drops, restacking in between:** zero to two cards left in
  the hopper per drop.
- **Typical failure:** a single card comes to rest balanced on a blade tip,
  leaning on the hopper wall. It is visible from above and a nudge frees it.

Limits of the simulation: cards are rigid plates with flat bottom edges and
guessed friction (0.22 card to card, 0.35 card to plastic). Real sleeved cards
bend, trap air and have soft rounded edges, which should make jams less
likely and perched cards less stable, but that is untested. The blades are
modelled as rigid; printed 0.8 mm blades will flex.

## How many drops

The simulation also showed something useful: the card a blade tip lands on is
delayed and ends up elsewhere in its packet. That moves single cards, and it
roughly halves the number of drops needed.

| Drops | Adjacent pairs still together (model) | Same, 12-drop physics run |
|---|---|---|
| 1 | 73% | 68% |
| 5 | 21% | 14% |
| 7 | 12% | 8% |
| 10 | 6% | 2% |
| 13 | 3% | 2% (at 12) |

A fully random deck scores 1.7%. By seven drops every card is equally likely
to be at any position. Ten drops is reasonable for casual play; twelve or
thirteen is thorough. The model column is `shuffle_sim.py`, calibrated to the
physics; the physics column is a single run, so treat it as indicative.

## Size and printing

Assembled: 283 wide x 76 deep x 326 tall mm (234 without the hopper). Needs a
bed of at least 250 x 250 mm; the wall halves are 143 x 234 mm. Roughly 450 g
of filament at 15% infill (estimated from solid volume). No supports.

| File (in `out/`) | Qty | Orientation (files are already oriented) |
|---|---|---|
| `slice_00` ... `slice_13` | 1 each | blade on the bed, rib up |
| `back_L`, `back_R` | 1 each | wall on the bed, bin floor standing up |
| `front_L`, `front_R` | 1 each | flat |
| `hopper` | 1 | upside down, throat ring on the bed |
| `bar` | 6 | lying down, slot vertical |
| `wedge` | 6 | flat |
| `foot` | 2 | on its side |

`out/assembly.step` is the whole machine for viewing or editing in CAD.

Settings: 0.4 mm nozzle, **0.2 mm layers** (blades are four layers thick and
taper to a one-layer tip), 3 perimeters. PETG is the better choice for the
slices because the blades are thin; PLA is fine for everything else.

## Assembly

1. Stack slices 00 to 13 in order. Slices 00 to 06 go blade towards the front,
   07 to 13 blade towards the back, so the two middle blades touch. The small
   notches on the right-hand edge form one diagonal line when the order is
   correct.
2. Lay `back_L` and `back_R` down side by side and set the stack on them.
3. Add `front_L` and `front_R`; the tongues on the bin floors key into their
   slots.
4. Push the six bars through from the back and tap a wedge, narrow end first,
   into each slot until snug. Do not over-drive them; squeezing the stack bows
   the blades.
5. Press the two feet onto the bottom edges and set the hopper on top.

## Use

Lower the deck, short edge down, through the hopper until it almost touches
the blades, and let go. Dropping from higher gains nothing. Pinch each pile
through the notches, put left on right, square up, repeat. If a card is left
standing in the hopper, nudge it or add it to the deck for the next drop.

## Changing it

All dimensions are fields of `Params` in `shuffler_design.py`.

```
pip install cadquery mujoco pytest matplotlib
python shuffler_design.py out     # regenerate STL + STEP
python render.py .                # regenerate the pictures
python physics_sim.py 12          # 12 simulated drops, about 90 s
pytest test_shuffler.py           # 82 checks, about a minute
```

- **Larger or double sleeves:** set `sleeve_w`, `sleeve_h`, `card_pitch`
  (about 0.8 for double-sleeved), then re-run the physics.
- **Blade thickness and spacing:** in the simulation, blades thicker than about
  17% of their spacing jam. Thinner blades or wider channels are safer;
  narrower channels shuffle faster.
- **Bed of 300 mm or more:** the wall halves could be merged into single
  plates; the split at the centre line exists only to fit 250 mm beds.

## Likely tuning after a first print

- **Cards perch on blade tips:** sand the tips to a knife edge, or increase
  `roof_deg`.
- **Deck jams in the comb:** increase `channel_w`, or check the blades have
  not bowed (loosen the wedges).
- **Cards stall on a ramp:** raise `ramp_deg` (costs height), or polish the
  rib tops.
- **A late card blocks its channel:** raise `fall_clear`.
- **Sleeve corners scuffing:** the landing corner takes a knock on every drop;
  a strip of tape on the top 15 mm of each rib softens it.
