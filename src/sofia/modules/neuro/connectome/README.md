# Experimental connectome research layer

This package is biologically inspired research, not an actual fly-brain
simulation and not a production authority. `circuits.py` records sources,
grouping, sign assumptions, prototype weight derivation, simplifications, and
the intended Sofía mapping. It does not bundle FlyWire data or claim to
reproduce the cited connectomes.

`competition.py` and `associative.py` are opt-in comparison prototypes. They do
not replace NEURO v0.1. Association can nominate a memory ID only after a caller
supplies the existing MEM eligibility decision; it cannot retrieve, promote, or
cross audience/privacy boundaries. Adaptive weights are bounded, rate-limited,
decayed, provenance-linked, exportable, versioned, and resettable.
