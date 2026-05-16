import re
import zipfile
import tempfile
from pathlib import Path

import streamlit as st
import easyocr
from PIL import Image

st.set_page_config(page_title="Loulune OCR", layout="centered")

st.title("📖 Lirabyne OCR")
st.write("Upload un ZIP contenant les pages du chapitre. Le site récupère le texte anglais et génère un TXT propre.")

@st.cache_resource
def load_reader():
    return easyocr.Reader(["en"], gpu=False)


def is_image_file(path: Path):
    return path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]


def prepare_image(image_path: Path):
    img = Image.open(image_path).convert("RGB")

    max_width = 1000

    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height))

    output_path = image_path.with_suffix(".ocr.jpg")
    img.save(output_path, quality=90)

    return output_path


def clean_text(text):
    text = str(text).strip()

    # enlève les lignes vides
    if not text:
        return ""

    # enlève les lignes composées seulement de chiffres / symboles
    if re.fullmatch(r"[\d\s\W_]+", text):
        return ""

    # ignore pubs / watermarks / crédits
    ignored_words = [
        "rokari",
        "rokaricomics",
        "discord",
        "recruiting",
        "translator",
        "translators",
        "proofreader",
        "proofreaders",
        "editor",
        "editors",
        "website",
        "to be continued",
        "join our",
        "apply",
    ]

    lowered = text.lower()

    if any(word in lowered for word in ignored_words):
        return ""

    # corrige les séparateurs chelous
    text = text.replace("_", "")
    text = text.replace(";", ",")
    text = text.replace(":", ".")
    text = text.replace("|", "I")

    # supprime caractères trop parasites
    text = re.sub(r"[{}\[\]<>~^`]", "", text)

    # espaces propres
    text = re.sub(r"\s+", " ", text).strip()

    # met tout en minuscule puis majuscule au début
    text = text.lower()

    if text:
        text = text[0].upper() + text[1:]

    return text


def merge_lines_into_sentences(lines):
    cleaned = []

    for line in lines:
        line = clean_text(line)
        if line:
            cleaned.append(line)

    if not cleaned:
        return []

    sentences = []
    buffer = ""

    for line in cleaned:
        if not buffer:
            buffer = line
        else:
            buffer += " " + line[0].lower() + line[1:]

        if buffer.endswith((".", "?", "!", "…")):
            sentences.append(buffer.strip())
            buffer = ""

    if buffer:
        sentences.append(buffer.strip())

    return sentences


def ocr_image(image_path: Path):

    prepared = prepare_image(image_path)

    reader = load_reader()

    results = reader.readtext(
        str(prepared),
        detail=0,
        paragraph=False
    )

    return merge_lines_into_sentences(results)


uploaded_zip = st.file_uploader("Upload ZIP", type=["zip"])

if uploaded_zip:

    if st.button("Lancer OCR"):

        with tempfile.TemporaryDirectory() as temp_dir:

            temp_dir = Path(temp_dir)

            zip_path = temp_dir / "chapter.zip"
            zip_path.write_bytes(uploaded_zip.read())

            extract_dir = temp_dir / "pages"
            extract_dir.mkdir()

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            image_files = sorted(
                [
                    p for p in extract_dir.rglob("*")
                    if p.is_file() and is_image_file(p)
                ],
                key=lambda p: p.name.lower()
            )

            if not image_files:
                st.error("Aucune image trouvée dans le ZIP.")
                st.stop()

            progress = st.progress(0)
            status = st.empty()

            final_text = ""

            for index, image_path in enumerate(image_files, start=1):

                status.write(
                    f"Traitement page {index}/{len(image_files)} : {image_path.name}"
                )

                final_text += f"\n\n===== PAGE {index:03d} - {image_path.name} =====\n\n"

                sentences = ocr_image(image_path)

                if not sentences:
                    final_text += "Aucun texte détecté.\n"
                else:
                    for sentence in sentences:
                        final_text += sentence + "\n"

                progress.progress(index / len(image_files))

            st.success("OCR terminé.")

            st.download_button(
                label="Télécharger TXT",
                data=final_text.strip().encode("utf-8"),
                file_name="ocr_chapitre.txt",
                mime="text/plain"
            )

            st.text_area(
                "Aperçu du texte",
                final_text.strip(),
                height=500
            )
