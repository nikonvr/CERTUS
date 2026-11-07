# Code 1: hidden resonances found from the complex plane

`hidden_resonances.py` is a minimal reference implementation of the method of the paper. It covers normal incidence,
non-dispersive lossless materials and transmittance targets, and needs only NumPy and SciPy.

- `char_y`, `transmittance`, `merit`: characteristic matrices (Macleod), real or complex wavelengths; layer 1 on the
  substrate.
- `phase_steps`: steps of pi of arg t along lambda + i*gamma, sampled on the design grid.
- `newton_pole`: pole of t (zero of Y = eta0 B + C) in the complex wavenumber plane.
- `find_poles`: resonances of the design (wavelength, FWHM, height), with several Newton starts per phase step.
- `charge_poles`: rounds of detection and least-squares polish on the grid plus one wavelength per resonance, at its pole.

Demonstration (Appendix A design, `three_line_101_recreated.csv`):

    python hidden_resonances.py three_line_101_recreated.csv

It prints the MF on the 277 points (0.0128 %) and resolved on 0.001 nm steps (0.3483 %), the three resonances
(402.5253, 410.6528 and 422.4040 nm), then the rounds of the treatment. The Jacobian is computed by finite differences
for readability, so a round takes a few minutes; the computations of the paper used analytic derivatives.
`demo_output.txt` is the output of this run: after 40 rounds (81 min on a desktop computer) the MF is 0.0249 % on the
277 points and 0.0221 % resolved, the highest remaining peak 0.33 % (the paper reports 0.0216 and 0.0189 % with the
analytic Jacobian).
