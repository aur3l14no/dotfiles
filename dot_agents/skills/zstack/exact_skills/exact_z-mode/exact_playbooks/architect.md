# Architect

For a settled intent that changes the codebase's shape: which component owns what, the interfaces between them, the types and signatures callers use. The output is a sketch that the unit's brief carries.

1. Ground in the code it touches: how it works now, and what depends on what will change (callers, copies of the same rule, recordings, other languages reading the same bytes). Bring that list to the user with the sketch.
2. Write the caller's usage first and derive the sketch from it: types, signatures and module boundaries, with bodies left unimplemented.
3. A key boundary gets two or three sketches in parallel. Judge them on the cost of a likely change, counted in lines touched.
4. Before putting a capability into the runtime, ask whether it can work offline over recordings, or be captured on demand.
5. Review the sketch with a bounded ask: at most seven items, what to simplify and what is missing. Adversarial review waits for a diff.
