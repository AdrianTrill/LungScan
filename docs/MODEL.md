# The model

LungScan reads single axial CT slices with a ResNet-50 classifier, and shows where its evidence for cancer lies with Grad-CAM. This page describes the network, how it is exported and stored, how the app runs it, how its output becomes a read, and how well it does, measured on the images it was published with.

> [!IMPORTANT]
> LungScan is research software, not a medical device. Treat every read as a demonstration of the software, never as a diagnosis (see [Limitations](#limitations)).

## The network

[dorsar/lung-cancer-detection](https://huggingface.co/dorsar/lung-cancer-detection) (MIT license) is a ResNet-50 pretrained on ImageNet, with its last layer replaced by a two-layer head (2048 → 256 → 4) and fine-tuned on 2D slices in four classes: adenocarcinoma, large cell carcinoma, squamous cell carcinoma, and normal. LungScan pins revision [`aa7426d`](https://huggingface.co/dorsar/lung-cancer-detection/tree/aa7426d75fbc0567fc6f0b36d47776fefae103f1) of the repository, which also holds the train, validation, and test splits the model was trained and evaluated on.

## Preprocessing

The app prepares a slice exactly as the model's training code did: [`preprocess.py`](https://huggingface.co/dorsar/lung-cancer-detection/blob/aa7426d75fbc0567fc6f0b36d47776fefae103f1/preprocess.py) resizes images to 250×250, then [`architecture.py`](https://huggingface.co/dorsar/lung-cancer-detection/blob/aa7426d75fbc0567fc6f0b36d47776fefae103f1/architecture.py) applies `Resize(256)` and `CenterCrop(224)`, both bilinear, and normalizes with the ImageNet mean and standard deviation per channel. The crop keeps the central 87.5% of the slice in each direction.

The pipeline was chosen on the validation split, using the criterion the training code selected its checkpoint by (four-class accuracy). `python -m tools.evaluate` repeats the comparison:

| Pipeline | Four-class (validation) | Cancer vs normal (validation) |
| --- | ---: | ---: |
| **Training: 250×250, then 256, crop 224** (used) | **0.667** | 0.972 |
| The model repository's `run.py`: shorter side 256, crop 224 | 0.556 | 1.000 |
| Stretch to 224×224 | 0.625 | 0.986 |
| LungScan's previous pipeline: stretch, red-channel statistics for every channel | 0.500 | 0.986 |

`run.py` keeps only the middle of wide slices (a 1.4:1 slice loses 19% of its width on each side), and LungScan's previous pipeline normalized the green and blue channels with the red channel's statistics.

## Grad-CAM in one forward pass

[`tools/export_model.py`](../backend/tools/export_model.py) exports the network to ONNX with two outputs: the four logits, and `cam`, a 7×7 [Grad-CAM](https://arxiv.org/abs/1610.02391) map of the evidence for cancer on the last convolutional feature map.

Grad-CAM usually needs a backward pass. Here it doesn't. The score explained is the log-odds of cancer, `s = logsumexp(z_adeno, z_large, z_squamous) − z_normal`. The head is `z = W₂ · relu(W₁ · p + b₁) + b₂`, where `p` is the global average of the feature maps `A`. So:

- `∂s/∂z` is the softmax over the three cancer logits, and −1 for normal;
- `∂s/∂p = W₁ᵀ · (relu′(h) ⊙ W₂ᵀ · ∂s/∂z)`, the head's Jacobian, which the graph computes with two matrix products;
- because of the average pooling, every location of `A` gets the same gradient, `∂s/∂p / 49`. Those are Grad-CAM's channel weights, and the map is `relu(Σₖ αₖ Aₖ)`.

The export wraps the network in [`ExplainedNet`](../backend/tools/network.py), which does exactly this, and checks it before writing the file: with the same weights, ONNX Runtime must reproduce PyTorch's logits (largest difference 3.3×10⁻⁶), and the map must match the Grad-CAM autograd computes (5.1×10⁻⁷). A unit test checks the same identity on random weights. The graph uses only basic operators, so ONNX Runtime Web runs it unchanged.

## Int8 weights

Convolution weights are nearly all of the 96.1 MB float32 file. [`tools/quantize.py`](../backend/tools/quantize.py) folds each BatchNorm into the convolution before it, then rounds the weights of the convolutions in layers 2 to 4 to int8: each output channel's weights are split into blocks of 32, and each block gets a float32 scale that maps its largest magnitude to 127. The stem and layer 1 stay in float32, as do the biases and the head. The file is 29.3 MB, of which the int8 values take 23.2 MB and their scales 2.9 MB.

In the graph, each rounded weight is `Reshape(Cast(int8 blocks) × scales)`. All its inputs are constants, so ONNX Runtime folds it back into a float32 weight when it loads the file (in 0.2 s on the server), and the network runs as a float32 network with the rounded weights. That network is what the exporter compares with PyTorch, and the file's outputs are bit for bit those of the same weights stored in float32.

The scheme was chosen on the 72 validation and 295 test slices, against the published float32 weights:

| Int8 weights | Same flag (of 367) | Same class (of 367) | Largest change in a cancer probability |
| --- | ---: | ---: | ---: |
| One scale per output channel, all but the stem | 367 | 362 | 16.7 points |
| One scale per output channel, stem and layer 1 in float32 | 367 | 365 | 4.4 points |
| Blocks of 32, all but the stem | 367 | 362 | 6.0 points |
| **Blocks of 32, stem and layer 1 in float32** (used) | **367** | **367** | **1.5 points** |

With one scale per output channel, rounding layer 1 alone moves cancer probabilities by up to 14.8 points, although it holds 0.2 of the 23.5 million convolution weights; rounding layer 2, 3, or 4 alone moves them by 3.1 points at most. With the scheme used, the median change is 0.009 points. Blocks of 32 cost 2.9 MB of scales over one scale per channel, and are what removes the class changes.

Two checks keep it that way. The exporter reads the seven sample slices with the file and with the float32 weights in PyTorch, and refuses to write the file if a flag or a class differs, or if a cancer probability moves by more than 2 points; the largest change is 0.5 points. [`tools/evaluate.py`](../backend/tools/evaluate.py) records the agreement on the validation and test splits in `model/evaluation.json`, and CI requires it to stay the same.

## From output to read

[`app/services/analysis.py`](../backend/app/services/analysis.py) turns the two outputs into a read, and [`frontend/src/lib/inference/interpret.ts`](../frontend/src/lib/inference/interpret.ts) does the same in the browser:

1. **Probabilities**: the softmax of the logits. The **cancer probability** is the sum of the three cancer classes.
2. **Flag**: a slice is flagged when its cancer probability is at least 0.5. Its **subtype** is the most probable cancer class, shown as unreliable (see below).
3. **Heat map**: the map divided by its maximum, then multiplied by the cancer probability, so a confidently normal slice shows no heat. It covers the 224×224 crop, mapped back onto the original slice.
4. **Regions**: on flagged slices, grid cells with at least half the maximum are grouped into 8-connected regions. Each region's center is the evidence-weighted centroid of its cells, and its radius that of a disc of the same area. The three strongest are kept.
5. **Summary**: one sentence, built from the values above.

Rounding is half up throughout, so the server and the browser produce the same text. The regions are where the network's evidence is concentrated, not detected nodules: on this dataset they often cover the mediastinum or a whole lung.

## Measured performance

[`tools/evaluate.py`](../backend/tools/evaluate.py) runs the app's own pipeline on the test split published with the model, and writes [`model/evaluation.json`](../model/evaluation.json).

**The published test split is mostly duplicates for normal slices.** It has 295 images, not the 315 its dataset card lists. 48 of its 54 normal slices are copies of training or validation images, or of each other. Five of those copies are re-encoded or resized, so the evaluation compares perceptual hashes (a 16×16 difference hash), not file contents: copies are 0 to 3 bits apart out of 256, and different slices more than 20. Two squamous cell slices repeat within the split. Without the 50 duplicates, 245 slices remain: 239 with cancer and 6 normal.

On those 245 slices:

| Measure | Result |
| --- | --- |
| Cancers flagged (sensitivity) | 237 of 239 (99.2%, 95% CI 97.0 to 99.8%) |
| Normal slices cleared (specificity) | 6 of 6 (95% CI 61 to 100%) |
| Cancer vs normal, ROC AUC | 1.000 |
| Four-class accuracy | 53.5% |
| Subtype accuracy on cancer slices | 53.1% (127 of 239; chance is 33.3%) |

Confusion matrix (rows: truth; columns: prediction):

| | Adeno | Large cell | Normal | Squamous |
| --- | ---: | ---: | ---: | ---: |
| **Adenocarcinoma** (100) | 31 | 50 | 3 | 16 |
| **Large cell carcinoma** (51) | 0 | 50 | 0 | 1 |
| **Normal** (6) | 0 | 0 | 6 | 0 |
| **Squamous cell carcinoma** (88) | 3 | 41 | 0 | 44 |

The model calls most cancers large cell carcinoma, so the app shows the subtype as a guess and says how often it is right. The model card reports 98% accuracy for cancer vs normal and 83% for the four classes; on the whole published test split, duplicates included, the app's pipeline reaches 99.3% and 61.0%.

## Limitations

- **Six normal slices.** With six unique normal slices, specificity is barely measured: its 95% interval runs from 61% to 100%.
- **Near-duplicates and patients.** Copies are removed, but neighbouring slices of the same patient may sit in different splits; the dataset has no patient IDs to check.
- **2D, 8-bit slices.** The model sees one 8-bit image of a slice, not a volume in Hounsfield units, and the regions come from a 7×7 map.
- **One public dataset.** The model was trained, validated, and tested on slices from one public collection, so these results say nothing yet about scans from other hospitals or scanners.

The [segmentation research](../AI%20model/README.md) in this repository works on 3D volumes and is a separate line of work.

## Where it runs

The exported file, `lungscan.onnx` (29 MB), runs in two places:

- **The server**: [`app/services/model.py`](../backend/app/services/model.py) loads it with ONNX Runtime on the CPU, about 20 ms per slice on an Apple M-series laptop. PyTorch is not needed. If `model/lungscan.onnx` is missing, the server downloads it from the project's GitHub Pages site on first use, with its manifest, and checks its SHA-256.
- **The browser**: the in-browser build runs the same file with ONNX Runtime Web, in a worker ([`public/inference-worker.js`](../frontend/public/inference-worker.js)), on WebGPU when the browser has it and on WebAssembly otherwise. The model is downloaded once, checked against the same SHA-256, and kept in Cache Storage.

The browser prepares slices with a port of Pillow 13's bilinear resize ([`resample.ts`](../frontend/src/lib/inference/resample.ts)), down to its fixed-point weights and the order of its two passes, so a PNG slice reaches the network as exactly the same tensor on both sides. Tests hold the ports to the server's own output (fixtures from `tools/make_fixtures.py`). In headless Chrome, the browser's reads of the seven sample slices agree with the server's to within 10⁻⁵, and exactly for five of them on WebAssembly: the runtimes' kernels add in different orders, which moves the sixth decimal at most.

## Tools

Run them from `backend/`. `fetch_model` needs only `requirements.txt`; the others need `requirements-model.txt` (PyTorch, ONNX, and the Hugging Face client).

| Command | What it does |
| --- | --- |
| `python -m tools.fetch_model` | Downloads `model/lungscan.onnx` from GitHub Pages and checks it |
| `python -m tools.export_model` | Builds `model/lungscan.onnx` from the pinned weights, with int8 convolution weights, and checks it against PyTorch, autograd, and the float32 weights |
| `python -m tools.evaluate` | Measures the model on the deduplicated test split, and how often its int8 weights agree with the float32 ones; writes `model/evaluation.json` |
| `python -m tools.make_samples` | Rebuilds the sample slices and their reference reads in `model/samples/` |
| `python -m tools.make_samples --check` | Re-runs the model on the samples and compares with `model/samples/samples.json` |
| `python -m tools.make_fixtures` | Writes the server's outputs the frontend's tests compare against |
