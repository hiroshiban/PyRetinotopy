# Attribution

PyRetinotopy is a Python/PsychoPy adaptation of **Retinotopy toolbox by Hiroshi Ban**:
https://github.com/hiroshiban/Retinotopy

Original source revision examined: `34170a20c64dddc3aa656b099f0bf1847b42b64d` (2024-10-31), together with the user's existing local modifications. LICENSE.txt identifies the Python/PsychoPy adaptation and retains the original copyright notice, BSD conditions and disclaimer.

The MATLAB Psychtoolbox 3 version was rewritten in Python for PsychoPy with support from OpenAI's generative AI tools, including Codex, for source-code review, migration planning, implementation, testing, and documentation.

The binary m-sequence formulation follows the original `Common/mseq.m`, which credits Giedrius T. Buracas and Thomas Liu, with modifications by Hiroshi Ban. Only the fixed binary order-eight sequence needed for the original default multifocal protocol is reimplemented here.

The object-image bank credits work from Talia Konkle's research group. Version 0.2 uses a lossless native NumPy bank, converted once from the original database; normal presentation does not read legacy MAT files. The image data are separate from the source-code distribution. Conversion does not change their attribution or terms. Cite the applicable papers, including:

- Konkle & Caramazza (2013), Journal of Neuroscience 33, 10235–10242.
- Konkle & Oliva (2012), Neuron 74, 1114–1124.
- Brady et al. (2008), PNAS 105, 14325–14329.
- Konkle et al. (2010), Journal of Experimental Psychology: General 139, 558–578.
- Konkle & Oliva (2012), Journal of Experimental Psychology: Human Perception and Performance 38, 561–569.

Local QA previews containing object images inherit those source-image considerations; do not treat them as newly licensed artwork. PsychoPy and other dependencies retain their respective licenses. Cite PsychoPy according to the version used in the study.

The optional GLFW integration uses the official psychopy-glfw plugin by Matthew Cutone / Open Science Tools, distributed under GPLv3. The project-local compatibility adapter bridges the PsychoPy 2024.2 cursor API and dispatches OS events after collecting flip timestamps; vendor source files are not modified. See https://github.com/psychopy/psychopy-glfw for the original plugin.


The six files in `pyretinotopy/data/brainvoyager/` are unchanged copies of Hiroshi Ban's original `pRF/olt/*.olt` color tables. Their original names, color entries and attribution are retained; `export-olts` copies them without modification.
