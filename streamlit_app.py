import base64
import io

import numpy as np
import streamlit as st
from PIL import Image

# ----------------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Raster Normalizer", page_icon="🗺️", layout="centered")

ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg", "bmp", "tif", "tiff", "gif", "webp"]

# ----------------------------------------------------------------------------
# Normalization logic - unchanged from the Flask version
# ----------------------------------------------------------------------------


def load_as_array(image: Image.Image):
    """
    Return (color_array, alpha_array_or_None) as float64.
    Alpha is kept aside untouched - normalization is only ever applied
    to color/intensity values, never to transparency.
    """
    if "A" in image.getbands():
        rgba = image.convert("RGBA")
        arr = np.array(rgba).astype(np.float64)
        return arr[:, :, :3], arr[:, :, 3]
    rgb = image.convert("RGB")
    arr = np.array(rgb).astype(np.float64)
    return arr, None


def normalize_perchannel(arr):
    """R, G, B each rescaled by their own Xmin/Xmax."""
    mins = arr.min(axis=(0, 1))
    maxs = arr.max(axis=(0, 1))
    ranges = maxs - mins
    safe_ranges = np.where(ranges == 0, 1, ranges)
    out = (arr - mins) / safe_ranges
    out = np.where(ranges == 0, 0, out)
    stats = "\n".join(
        f"{ch}  min {int(mn)} max {int(mx)}" for ch, mn, mx in zip("RGB", mins, maxs)
    )
    return out, stats


def normalize_global(arr):
    """A single Xmin/Xmax shared across all channels."""
    x_min = arr.min()
    x_max = arr.max()
    if x_max - x_min == 0:
        out = np.zeros_like(arr)
    else:
        out = (arr - x_min) / (x_max - x_min)
    stats = f"Xmin {int(x_min)}   Xmax {int(x_max)}   (shared across R, G, B)"
    return out, stats


def normalize_luminance(arr):
    """Collapse to grayscale via perceptual luminance, then normalize."""
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    x_min = lum.min()
    x_max = lum.max()
    if x_max - x_min == 0:
        norm = np.zeros_like(lum)
    else:
        norm = (lum - x_min) / (x_max - x_min)
    out = np.stack([norm, norm, norm], axis=-1)
    stats = f"Xmin {x_min:.1f}   Xmax {x_max:.1f}   (perceptual luminance)"
    return out, stats


def normalize_image(image: Image.Image, mode: str):
    """
    Normalize every pixel value using:
        X_norm = (X - Xmin) / (Xmax - Xmin)
    then rescale to 0-255 so the result can be saved/viewed as a standard
    image. `mode` selects how Xmin/Xmax are chosen:
      - "perchannel": independently per R, G, B channel (default)
      - "global":     one shared min/max across all channels
      - "luminance":  min/max of perceptual grayscale luminance
    Alpha, if present, passes through unmodified.
    """
    arr, alpha = load_as_array(image)

    if mode == "global":
        normalized, stats = normalize_global(arr)
    elif mode == "luminance":
        normalized, stats = normalize_luminance(arr)
    else:
        mode = "perchannel"
        normalized, stats = normalize_perchannel(arr)

    scaled = np.clip(normalized * 255.0, 0, 255).round().astype(np.uint8)

    if alpha is not None:
        rgba = np.dstack([scaled, alpha.astype(np.uint8)])
        result = Image.fromarray(rgba, "RGBA")
    else:
        result = Image.fromarray(scaled, "RGB")

    return result, stats


def to_data_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# ----------------------------------------------------------------------------
# Front-end design - CSS ported from the original templates/index.html
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Roboto+Mono:wght@400;500&display=swap');

    :root{
        --ink:#1b2420;
        --paper:#d8d1a1;
        --line:#141414;
        --line1:#5162b5;
        --accent:#8e6e37;
        --accent1:#42584ad3;
        --accent-dim:#549f64;
        --mono: "Roboto Mono", "SFMono-Regular", Consolas, monospace;
        --sans: "IBM Plex Sans", "Segoe UI", sans-serif;
    }

    .stApp{
        background:var(--paper);
        color:var(--ink);
        font-family:var(--sans);
    }
    .block-container{
        max-width:920px;
        padding-top:40px;
        padding-bottom:80px;
    }

    /* ---- header box ---- */
    .rn-header{
        margin-bottom:36px;
        border:2px solid var(--line);
        border-radius:4px;
        background:#f2f5e7;
        padding:32px 28px;
        text-align:center;
    }
    .rn-header h1{
        font-size:34px;
        font-weight:600;
        margin:0 0 12px;
        letter-spacing:-0.01em;
        color:var(--ink);
        font-family:var(--sans);
    }
    .rn-sub{
        font-family:var(--sans);
        font-size:15px;
        color:#310c0c;
        line-height:1.6;
        max-width:60ch;
        margin:0 auto;
    }
    .fraction{
        display:inline-flex;
        flex-direction:column;
        align-items:center;
        vertical-align:middle;
        margin:10px 6px;
        font-family:var(--mono);
        line-height:1.4;
    }
    .fraction .num{
        padding:0 6px 3px;
        border-bottom:1.5px solid var(--ink);
    }
    .fraction .den{
        padding:3px 6px 0;
    }

    /* ---- error box ---- */
    .rn-error{
        font-family:var(--mono);
        font-size:13px;
        background:#f4e4e1;
        border:1px solid #be8879;
        color:#7a3225;
        padding:12px 16px;
        margin-bottom:24px;
        border-radius:2px;
    }

    /* ---- mode select label ---- */
    .rn-modelabel{
        font-family:var(--mono);
        font-size:15px;
        color:#3e3e3e;
        margin:20px 0 4px;
    }

    /* ---- panels grid ---- */
    .rn-panel{
        border:1px solid var(--line);
        background:#f7f8f4;
        margin-bottom:8px;
    }
    .rn-panel h2{
        font-size:11px;
        text-transform:uppercase;
        letter-spacing:.08em;
        font-weight:500;
        color:#565755;
        margin:0;
        padding:10px 14px;
        border-bottom:1px solid var(--line);
        font-family:var(--mono);
    }
    .rn-panel .imgwrap{
        padding:14px;
        display:flex;
        align-items:center;
        justify-content:center;
        min-height:180px;
    }
    .rn-panel img{
        max-width:100%;
        height:auto;
        display:block;
        image-rendering:pixelated;
    }
    .rn-stats{
        font-family:var(--mono);
        font-size:12.5px;
        color:#7a6868;
        padding:0 14px 14px;
        line-height:1.6;
        white-space:pre-line;
    }

    /* ---- footer ---- */
    .rn-footer{
        margin-top:56px;
        font-family:var(--sans);
        font-size:13px;
        color:#171717;
        border-top:1px solid var(--line);
        padding-top:16px;
    }
    .rn-madeby{
        text-align:center;
        margin-top:60px;
        font-family:var(--sans);
        font-size:13px;
        color:#474747;
        border-top:1px solid var(--line);
        padding-top:16px;
    }

    /* ---- restyle native Streamlit widgets to match the original look ---- */

    /* file uploader label -> merged as the top half of one seamless box */
    [data-testid="stFileUploader"] [data-testid="stWidgetLabel"]{
        background:#ebf6cc !important;
        border:2px solid var(--line);
        border-bottom:none;
        border-radius:2px 2px 0 0;
        padding:14px 18px 6px;
        margin-bottom:0 !important;
    }
    [data-testid="stFileUploader"] [data-testid="stWidgetLabel"] p{
        font-family:var(--sans) !important;
        color:var(--ink) !important;
        font-size:14px;
        margin:0;
    }

    /* dropzone -> bottom half of the same box, seam removed between the two */
    [data-testid="stFileUploaderDropzone"]{
        border:2px solid var(--line) !important;
        border-top:none !important;
        border-radius:0 0 2px 2px !important;
        background:#ebf6cc !important;
        margin-top:0 !important;
    }

    /* only the instruction/helper text is restyled - icons and the Browse
       button are left alone so their built-in accessibility text stays
       correctly hidden instead of doubling up on screen */
    [data-testid="stFileUploaderDropzoneInstructions"] span{
        font-family:var(--sans) !important;
        color:var(--ink) !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] small{
        font-family:var(--sans) !important;
        color:#555 !important;
    }
    [data-testid="stFileUploaderDropzone"] button{
        color:#ffffff !important;
    }
    /* select box -> matches select/button styling */
    div[data-baseweb="select"] > div{
        font-family:var(--mono) !important;
        border:2px solid var(--line1) !important;
        background:#dae7f0 !important;
        border-radius:2px !important;
        color:var(--ink) !important;
    }

    /* download button -> a.download-btn look */
    div[data-testid="stDownloadButton"] button{
        font-family:var(--sans) !important;
        font-size:13px !important;
        padding:9px 14px !important;
        border:1px solid var(--accent) !important;
        background:var(--accent1) !important;
        color:#f4f4f4 !important;
        border-radius:2px !important;
        font-weight:500 !important;
        width:100%;
    }
    div[data-testid="stDownloadButton"] button:hover{
        background:var(--accent-dim) !important;
        border-color:var(--accent-dim) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="rn-header">
        <h1>Raster Normalizer</h1>
        <div class="rn-sub">
            Min–max normalization per pixel:
            <span class="fraction">
                <span class="num">X − Xmin</span>
                <span class="den">Xmax − Xmin</span>
            </span>
            <br>
            Rescaled to the 0–255 output range. Processing happens on the server for this version; your image is not stored.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Upload + mode select
# (Streamlit reruns automatically whenever either widget changes, so
# switching the mode re-normalizes the already-uploaded file with no
# extra button or re-upload needed.)
# ----------------------------------------------------------------------------
uploaded_file = st.file_uploader(
    "Click to choose a raster image or drag one here — PNG, JPEG, WebP, BMP, TIFF, GIF.",
    type=ALLOWED_EXTENSIONS,
    label_visibility="visible",
)

st.markdown('<div class="rn-modelabel">Normalization Mode:</div>', unsafe_allow_html=True)
mode_labels = {
    "perchannel": "Per-channel (R, G, B independently)",
    "global": "Global (single min/max across all channels)",
    "luminance": "Luminance only (grayscale output)",
}
mode = st.selectbox(
    "Normalization mode",
    options=list(mode_labels.keys()),
    format_func=lambda k: mode_labels[k],
    label_visibility="collapsed",
)

# ----------------------------------------------------------------------------
# Process + display
# ----------------------------------------------------------------------------
if uploaded_file is not None:
    try:
        image = Image.open(uploaded_file)
        image.load()
    except Exception:
        st.markdown(
            '<div class="rn-error">Could not read that file as an image.</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    width, height = image.size
    preview_mode = "RGBA" if "A" in image.getbands() else "RGB"
    original_uri = to_data_uri(image.convert(preview_mode))

    normalized, stats = normalize_image(image, mode)
    result_uri = to_data_uri(normalized)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div class="rn-panel">
                <h2>Original</h2>
                <div class="imgwrap"><img src="{original_uri}" alt="Original raster"></div>
                <div class="rn-stats">{width} &times; {height}px</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="rn-panel">
                <h2>Normalized</h2>
                <div class="imgwrap"><img src="{result_uri}" alt="Normalized raster"></div>
                <div class="rn-stats">{stats}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.download_button(
        label="Download normalized PNG",
        data=to_png_bytes(normalized),
        file_name="normalized.png",
        mime="image/png",
        use_container_width=True,
    )

# ----------------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="rn-footer">
        X = pixel value<br>
        Xmin / Xmax = extrema of the chosen range — output scaled to 0–255 for display and export
    </div>
    <div class="rn-madeby">
        Made by<br>Rinaldo Jevin Bala<br>240425
    </div>
    """,
    unsafe_allow_html=True,
)
