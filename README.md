# Raster Normalizer (Streamlit)

A Streamlit port of the Flask/Vercel app. Upload a raster image and it normalizes pixel values with

    X_norm = (X - Xmin) / (Xmax - Xmin)

rescaled to the 0–255 range, with a live preview and PNG download — same front-end design, same three normalization modes.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run streamlit_app.py
```

This opens the app in your browser (usually **http://localhost:8501**).

## How it works

- `streamlit_app.py` is the entire app — normalization logic (identical to the Flask version) plus the UI, in one file.
- Normalization modes, unchanged from before:
  - **Per-channel** (default) — R, G, B each rescaled by their own Xmin/Xmax.
  - **Global** — one Xmin/Xmax shared across all channels.
  - **Luminance only** — collapses to grayscale via perceptual luminance before normalizing.
- Alpha passes through unmodified in every mode.
- **No submit button needed** — Streamlit reruns the script automatically whenever you upload a file or change the mode dropdown, so switching modes re-normalizes the already-uploaded image instantly.
- Supported input formats: PNG, JPG, JPEG, BMP, TIF/TIFF, WEBP, GIF. Output is always PNG.
- Everything happens in memory — nothing is written to disk.

## Front-end design

The CSS is ported directly from the original `templates/index.html` (same color variables, header box, fraction-style formula, panel grid, stats text, footer, "Made by" credit), injected via `st.markdown(..., unsafe_allow_html=True)`. Native Streamlit widgets (file uploader, mode select, download button) are restyled with CSS targeting their internal `data-testid`/`data-baseweb` attributes to match the original dropzone, select, and button look as closely as Streamlit's component model allows.

**Note on Streamlit's internal DOM:** the selectors used to restyle the file uploader and select box (`[data-testid="stFileUploaderDropzone"]`, `div[data-baseweb="select"]`, etc.) target Streamlit's internal markup, which can change between Streamlit versions. If a future Streamlit upgrade changes these attribute names and the styling stops applying, inspect the widget in your browser's dev tools to find the new attribute and update the corresponding CSS selector in `streamlit_app.py`.

## Deploying to Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in, and click "New app".
3. Point it at your repo, with **Main file path** set to `streamlit_app.py`.
4. Deploy — no extra configuration needed; `requirements.txt` is picked up automatically.

Streamlit Cloud's default upload limit is 200MB per file (configurable via `.streamlit/config.toml` → `[server] maxUploadSize`), which is much more headroom than Vercel's ~4.5MB serverless payload cap.

## Notes / possible extensions

- No explicit file size limit is set beyond Streamlit's own default; add `[server] maxUploadSize` in `.streamlit/config.toml` to change it.
- True multi-band GIS rasters (GeoTIFF with more than 3 bands, non-8-bit data) aren't handled — Pillow reads standard image formats only. That would need `rasterio` or `gdal` instead.
