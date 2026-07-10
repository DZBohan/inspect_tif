# inspect_tif.py

Inspects the metadata and resolution of a large TIF image (e.g. a microscopy/tissue scan whole-slide image), and randomly crops several square regions saved as PNG for quick preview.

Optimized for very large files (the example file in this repo is about 14GB): uses `tifffile` + `zarr` for lazy reading, decoding only the tiles needed instead of loading the whole image into memory.

## Setup

Dependencies: `tifffile`, `numpy`, `Pillow`, `zarr`, `imagecodecs`

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install tifffile numpy Pillow zarr imagecodecs
```

## Usage

```bash
./.venv/bin/python inspect_tif.py [TIF_PATH] [--n 10] [--size 100] [--outdir samples] [--seed 0]
```

### Arguments

| Argument | Default | Description |
| --- | --- | --- |
| `TIF_PATH` | the single `.tif`/`.tiff` file in the current directory | Path to the TIF file to inspect |
| `--n` | `10` | Number of random regions to crop |
| `--size` | `100` | Side length of the square crop (pixels) |
| `--outdir` | `samples` | Output directory for the saved PNGs |
| `--seed` | none (different each run) | Random seed; set it to reproduce the same crops |

### Examples

Inspect resolution and generate 10 crops of 100x100:

```bash
./.venv/bin/python inspect_tif.py --n 10 --size 100 --outdir samples
```

Generate 10 crops of 1000x1000, reproducible via `--seed`:

```bash
./.venv/bin/python inspect_tif.py --n 10 --size 1000 --outdir samples --seed 0
```

## Output

The script first prints image metadata, e.g.:

```
File: dls093-7_20260709_Stitching_c1-3.tif
File size: 13.84 GB
Pages/levels (series): 1, image shape: (63146, 68867, 3), dtype: uint8
Axes order: YXS
Resolution tags: X=96923.4151, Y=96923.4151 pixels/cm
Pixel dimensions: width=68867, height=63146
```

Then, for each crop, a line like:

```
[1/10] saved samples/patch_00_x50494_y49673.png  (from x=50494, y=49673, 1000x1000)
```

And finally:

```
Done. Saved 10 1000x1000 sample crops to: samples
Metadata written to: samples/metadata.txt
```

It writes PNG files into the `--outdir` directory, named as:

```
patch_{index}_x{start_x}_y{start_y}.png
```

For example, `patch_00_x50494_y49673.png` is a crop taken from the original image at `(x=50494, y=49673)`; the coordinates in the filename can be used to locate the region back in the source image.

Everything printed to the terminal (metadata plus the list of saved crops) is also written to `metadata.txt` inside `--outdir`, so the run's output is preserved alongside the PNGs.

## Implementation notes

- Resolution is read from the `XResolution`/`YResolution`/`ResolutionUnit` tags via `tifffile.TiffFile(...).series[0].pages[0].tags`.
- The image is a tiled, uncompressed TIFF, so `tifffile.memmap` cannot memory-map it directly; instead `series.aszarr()` exposes it as a lazy zarr array for on-demand region reads.
- `aszarr()` returns a multi-resolution group; the script reads level `'0'` (full resolution).
- The axes order is `YXS` (height, width, color channel). Only the X/Y axes are sliced to the target region; the S (color channel) axis is kept in full to produce RGB output, while any other axis (e.g. Z/T/C) is fixed at index 0.
