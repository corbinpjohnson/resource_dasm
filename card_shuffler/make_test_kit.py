"""Export a small test version of the shuffler: 30 cards, 6 channels.

Same blades, film, fan, ramps, bins and hopper as the full machine, about half
the plastic.  Its job is to answer the one question the simulation cannot:
how do your sleeves' bottom edges behave on a 0.2 mm blade tip?

Drop 30 of your sleeved cards through it ten times and count the cards left
standing in the comb.  The simulation predicts, over ten drops:

    about 1 card     the bottom edges behave like a rounded edge
    about 10 cards   they behave like a welded seam (rock the machine to clear)
    about 30 cards   they behave like a square-cut edge (rock the machine to clear)

With rocking after each drop the simulation leaves almost none in every case.

Usage:  python make_test_kit.py [out_dir]          (default: out_test_kit)
"""

from dataclasses import replace

from shuffler_design import Params, export

KIT = replace(Params(), n_cards=30, n_channels=6)

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "out_test_kit"
    export(KIT, out)
    print(f"test kit exported to {out}/: {KIT.n_channels} comb slices for a {KIT.n_cards}-card deck")
