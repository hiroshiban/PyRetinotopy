# Project and Experiment Guides

The Japanese and English editions cover the same 15 chapters, including run selection/reruns and PTB3 fixation/task/display controls. They introduce **PyRetinotopy**, author/responsible investigator **Hiroshi Ban**, and the project's purpose before explaining experimental operation. References, license information, and acknowledgments close the guides.

- [Japanese PDF](../PyRetinotopy_Experiment_Guide_ja.pdf)
- [English PDF](../PyRetinotopy_Experiment_Guide_en.pdf)
- Editable sources: `guide_ja.json`, `guide_en.json`.

Build from the project root using a Python environment with ReportLab:

```shell
python tools/build_manual.py
```

PDFs are written to `docs/` by default. Use `--language ja` or `--language en` to rebuild one edition. Japanese defaults use Windows Yu Gothic; pass `--font` and `--bold-font` with appropriate TTF/TTC fonts on another system. The guide-building dependency is separate from presentation dependencies.

After changing content, render both PDFs with Poppler and inspect every page. Keep command blocks identical between language editions and preserve the original software/research/image-data acknowledgments. The guides describe operating procedures; timing, calibration, and binocular presentation must be checked on the apparatus used for data collection.

English is the default language. `README_ja.md`, `*.ja.md`, the Japanese PDF, and `guide_ja.json` are explicitly localized Japanese editions. Each language's README links to documentation in the same language; language switches are labeled. Each guide source provides `pdf_title` for localized PDF metadata.
