"""
Inspect the resolution/metadata of a large TIF image and randomly crop
several square regions, saving each as a PNG.

Usage:
    python inspect_tif.py [--n 10] [--size 100] [--outdir samples] [--seed 0] TIF_PATH

Defaults to the single .tif file found in the current directory.
"""

import argparse
import glob
import os
import random

import numpy as np
import tifffile
from PIL import Image


def find_default_tif():
    candidates = glob.glob(os.path.join(os.path.dirname(__file__), "*.tif")) + glob.glob(
        os.path.join(os.path.dirname(__file__), "*.tiff")
    )
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        raise SystemExit("No .tif/.tiff file found in the current directory; please pass a path explicitly.")
    raise SystemExit(f"Multiple tif files found in the current directory; please specify one: {candidates}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tif_path", nargs="?", default=None, help="Path to the TIF file")
    parser.add_argument("--n", type=int, default=10, help="Number of random regions to crop")
    parser.add_argument("--size", type=int, default=100, help="Side length of the square crop (pixels)")
    parser.add_argument("--outdir", default="samples", help="Output directory for saved crops")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (for reproducibility)")
    args = parser.parse_args()

    tif_path = args.tif_path or find_default_tif()
    if args.seed is not None:
        random.seed(args.seed)

    metadata_lines = []

    def log(line):
        print(line)
        metadata_lines.append(line)

    with tifffile.TiffFile(tif_path) as tif:
        series = tif.series[0]
        page = series.pages[0]

        log(f"File: {tif_path}")
        log(f"File size: {os.path.getsize(tif_path) / (1024 ** 3):.2f} GB")
        log(f"Pages/levels (series): {len(series.pages)}, image shape: {series.shape}, dtype: {series.dtype}")
        log(f"Axes order: {series.axes}")

        # Try to read resolution tags (pixels/unit + unit), common in microscopy/scanner images
        tags = page.tags
        res_x = tags.get("XResolution")
        res_y = tags.get("YResolution")
        unit = tags.get("ResolutionUnit")
        if res_x is not None and res_y is not None:
            def ratio_to_float(v):
                if isinstance(v, tuple) and len(v) == 2:
                    return v[0] / v[1] if v[1] else float("nan")
                return float(v)

            rx = ratio_to_float(res_x.value)
            ry = ratio_to_float(res_y.value)
            unit_map = {1: "unitless", 2: "inch", 3: "cm"}
            unit_str = unit_map.get(unit.value if unit else 2, str(unit.value if unit else "unknown"))
            log(f"Resolution tags: X={rx:.4f}, Y={ry:.4f} pixels/{unit_str}")
        else:
            log("No XResolution/YResolution tags found.")

        # Pixel dimensions (width x height)
        axes = series.axes
        shape = series.shape
        dims = dict(zip(axes, shape))
        height = dims.get("Y")
        width = dims.get("X")
        log(f"Pixel dimensions: width={width}, height={height}")

        if width is None or height is None:
            raise SystemExit(f"Could not resolve width/height from axes={axes}, shape={shape}.")

        size = args.size
        if width < size or height < size:
            raise SystemExit(f"Image is smaller than the requested {size}x{size} crop.")

        os.makedirs(args.outdir, exist_ok=True)

        # Use a lazy zarr array to read small regions on demand, avoiding loading the whole image
        # tifffile's aszarr() exposes it as a multi-resolution group; '0' is the full-resolution level
        store = series.aszarr()
        import zarr

        g = zarr.open(store, mode="r")
        z = g["0"] if hasattr(g, "keys") else g

        for i in range(args.n):
            x0 = random.randint(0, width - size)
            y0 = random.randint(0, height - size)

            # Build the slice index following axes order: slice X/Y to the target region,
            # keep the S (color channel) axis in full, and take index 0 for any other axis
            # (e.g. Z/T/C)
            index = []
            for ax in axes:
                if ax == "Y":
                    index.append(slice(y0, y0 + size))
                elif ax == "X":
                    index.append(slice(x0, x0 + size))
                elif ax == "S":
                    index.append(slice(None))
                else:
                    index.append(0)
            patch = np.asarray(z[tuple(index)])

            img = Image.fromarray(patch)
            out_path = os.path.join(args.outdir, f"patch_{i:02d}_x{x0}_y{y0}.png")
            img.save(out_path)
            log(f"[{i+1}/{args.n}] saved {out_path}  (from x={x0}, y={y0}, {size}x{size})")

        store.close()

    log(f"Done. Saved {args.n} {size}x{size} sample crops to: {args.outdir}")

    metadata_path = os.path.join(args.outdir, "metadata.txt")
    with open(metadata_path, "w") as f:
        f.write("\n".join(metadata_lines) + "\n")
    print(f"Metadata written to: {metadata_path}")


if __name__ == "__main__":
    main()
