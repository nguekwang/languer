---
paths:
  - "source-data/**"
  - "schema/**"
  - "tools/**"
---

# Lang Log data

The owner's rule (2026-11-07): Lang Log has its own data, in one shape for every record. Glottolog, WALS, the study trees and any other dataset are only references.

- Keep each source's files in `source-data/` as the source published them, and list the source in `source-data/sources.json` (version, retrieval date, license, download address, files). Do not edit a source's files by hand.
- Deploy only Lang Log's own data: the build converts the sources into the shape of `schema/languoid.schema.json` (`tools/build_languoids.py`). Do not commit the converted files.
- Everything is a languoid (the owner's rule, 2026-11-07): never give families, languages, dialects or clades different shapes or a Lang Log type of their own. Keep each source's level (family, language, dialect, genus ...) as that source's claim in `classification.<source>.level`.
- The only labels Lang Log itself gives a languoid are its modality (spoken, signed, written) and whether it is constructed (artificial or formal languages). Families of every modality (Indo-European, a sign language family, the Brahmic scripts) are parallel roots of one tree; do not split the data or the pages by modality.
- Every record has the same fields whatever its sources; a language missing from a source gets the same fields, with that data left out, never a different shape.
- Every value carries its source and version. Keep every source's value as evidence when they disagree; never drop one to resolve a conflict.
- Features are Lang Log's own, in `source-data/lang-log/features.json`; each source's features are mapped onto them. Values the owner adds go under source `lang-log`, with a reference.
- One function per source converts it, and it writes only that source's values, so a new release of one source never changes another source's or the owner's values.
- A new source, field or feature changes the schema, the converter and `README.md` (section "Lang Log data") in the same pull request.
- Page generators and page scripts read Lang Log's data, not a source's files directly. (Until the record pages are built from it, `tools/build_paths.py` still reads `dist/data.json` and `dist/integrated.json`.)
