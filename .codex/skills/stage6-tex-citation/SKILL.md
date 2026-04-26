---
name: stage6-tex-citation
description: "Use when stage6 processes TeX/LaTeX fulltext and must locate a target-paper citation from extracted source files."
---

# Stage6 TeX Citation Workflow

Use this workflow when the stage6 citation-sentiment agent receives a paper whose stage5 output came from `arXiv e-print` or other TeX/LaTeX source.

## Goal

Find the target paper's citation in a TeX-derived document reliably enough to extract the actual citing sentence(s) before asking the LLM for sentiment.

## Inputs

- Parsed fulltext text from stage5
- If available, `extracted_dir` produced by stage5
- Target paper title
- Target paper DOI
- Any known aliases or canonical paper names

## Procedure

1. Start from the extracted `.tex` files, not only the flattened text.
2. Grep for the target paper DOI first.
3. If DOI is missing, grep for distinctive title fragments.
4. When a hit appears in the bibliography / references section, identify the citation key or marker.
   Examples:
   - `\\bibitem{foo2020}`
   - `@article{foo2020,...}`
   - `[12]`
   - author-year style references
5. After recovering the citation key or marker, grep the body files for:
   - `\\cite{key}`
   - `\\citep{key}`
   - `\\citet{key}`
   - the numeric marker such as `[12]`
6. Collect the surrounding sentence or paragraph as candidate citation context.
7. Only after locating the real body context, ask the LLM to judge sentiment.

## Rules

- Prefer exact DOI matches over title-only matches.
- Prefer bibliography matches over incidental body mentions.
- Prefer body windows that explicitly carry the recovered citation key/marker.
- If no reference entry can be recovered, return `unknown` instead of guessing.
- If TeX source exists, do not rely only on flattened text until the source grep path has failed.

## Expected Output

- Matched bibliography entry
- Citation key / marker
- Body citation context
- Evidence note describing how the match was found
