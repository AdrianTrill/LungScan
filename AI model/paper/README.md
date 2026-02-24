# Paper Materials

This directory contains all materials related to the academic publication.

## 📄 Contents

### Documentation
- `MIRPR_VISTA_3D_Documentation.pdf` - VISTA 3D model documentation
- `lab3_MIRPR.pdf` - Lab report and interim findings

### Literature Reviews
The `literature_reviews/` directory contains comprehensive reviews of foundational papers:
- `papers-1-2-summary.tex` - Reviews of papers 1-2
- `papers-3-4-summary.tex` - Reviews of papers 3-4  
- `papers-5-6-summary.tex` - Reviews of papers 5-6
- `papers-7-8-summary.tex` - Reviews of papers 7-8
- `Lab2/` - Lab 2 materials with experimental results

### Figures (To Be Added)
High-resolution figures for the manuscript:
- Architecture diagrams
- Training curves
- Comparative results
- Qualitative examples

### Tables (To Be Added)
Result tables in CSV/LaTeX format:
- Performance metrics
- Ablation studies
- Computational requirements

## 📝 Manuscript (To Be Added)

The main paper manuscript will be placed here:
- `manuscript.pdf` - Final paper
- `manuscript_source/` - LaTeX source files
- `supplementary_materials.pdf` - Appendices

## 🔬 Generating Figures

To regenerate all paper figures:

```bash
cd ../research/notebooks
jupyter notebook generate_paper_figures.ipynb
```

Or use the automated script:

```bash
python ../scripts/generate_all_figures.py --output figures/
```

## 📊 Result Tables

Result tables are generated from experiment logs:

```bash
python ../research/evaluation/generate_tables.py --output tables/
```

## 🎯 Citation

See `../CITATION.cff` for citation information.
