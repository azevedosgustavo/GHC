"""Convert selected files into chat-completion content blocks."""
import base64
import io
import os
import zipfile

import docx
import openpyxl
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError
from openpyxl.utils.exceptions import InvalidFileException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 500000
MAX_CELLS = 20000


def _image_type(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _check_office_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_DOCUMENT_BYTES:
            raise ValueError("Documento descompactado excede 20 MiB.")
        if any(item.flag_bits & 1 for item in archive.infolist()):
            raise ValueError("Documento protegido por senha não é suportado.")


def _extract_document(data, ext):
    try:
        if ext == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("PDF protegido por senha não é suportado.")
            if len(reader.pages) > 100:
                raise ValueError("PDF excede o limite de 100 páginas.")
            parts = []
            size = 0
            for i, page in enumerate(reader.pages):
                part = "[Página %d]\n%s" % (i + 1, page.extract_text())
                size += len(part)
                if size > MAX_TEXT_CHARS:
                    raise ValueError("Texto extraído excede 500.000 caracteres.")
                parts.append(part)
            body = "\n".join(parts)
            if not any(page.strip() for page in [p.split("\n", 1)[1] for p in parts]):
                raise ValueError("PDF sem texto extraível; documentos digitalizados precisam de OCR.")
            return body
        _check_office_archive(data)
        if ext == ".docx":
            document = docx.Document(io.BytesIO(data))
            parts = []
            for element in document.element.body.iterchildren():
                if element.tag.endswith("}p"):
                    parts.append(Paragraph(element, document).text)
                elif element.tag.endswith("}tbl"):
                    table = Table(element, document)
                    parts.extend("\t".join(cell.text for cell in row.cells) for row in table.rows)
            body = "\n".join(parts)
        else:
            workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_links=False)
            try:
                parts = []
                count = 0
                size = 0
                for sheet in workbook.worksheets:
                    if sheet.max_row and sheet.max_column and sheet.max_row * sheet.max_column > MAX_CELLS:
                        raise ValueError("Planilha excede o limite de 20.000 células.")
                    parts.append("[Planilha: %s]" % sheet.title)
                    for row in sheet.iter_rows(values_only=True):
                        count += len(row)
                        if count > MAX_CELLS:
                            raise ValueError("Planilha excede o limite de 20.000 células.")
                        line = "\t".join("" if value is None else str(value) for value in row)
                        size += len(line)
                        if size > MAX_TEXT_CHARS:
                            raise ValueError("Texto extraído excede 500.000 caracteres.")
                        parts.append(line)
                body = "\n".join(parts)
            finally:
                workbook.close()
        if len(body) > MAX_TEXT_CHARS:
            raise ValueError("Texto extraído excede 500.000 caracteres.")
        if not body.strip():
            raise ValueError("Documento não contém texto extraível.")
        return body
    except (PdfReadError, zipfile.BadZipFile, PackageNotFoundError, XMLSyntaxError,
            InvalidFileException, KeyError) as e:
        raise ValueError("Não foi possível ler o documento: %s" % e) from e


def prepare_content(text, paths):
    blocks = [{"type": "text", "text": text}]
    files = []
    total = 0
    for path in paths:
        with open(path, "rb") as f:
            data = f.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Arquivo excede 2 MiB: %s" % os.path.basename(path))
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Os anexos juntos excedem 4 MiB.")
        name = os.path.basename(path).replace("\n", " ").replace("\r", " ")
        block_index = len(blocks)
        image_type = _image_type(data)
        if image_type:
            blocks.append({"type": "text", "text": "Imagem anexada: " + name})
            blocks.append({"type": "image_url", "image_url": {
                "url": "data:%s;base64,%s" % (image_type, base64.b64encode(data).decode("ascii"))}})
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext in (".pdf", ".docx", ".xlsx"):
                body = _extract_document(data, ext)
            else:
                try:
                    body = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    raise ValueError("Formato não suportado: %s. Use texto UTF-8, imagem, PDF, DOCX ou XLSX." % name)
                if any(ord(c) < 32 and c not in "\n\r\t" for c in body):
                    raise ValueError("Arquivo binario nao suportado: %s" % name)
            blocks.append({"type": "text", "text": "Arquivo anexado: %s\n%s" % (name, body)})
        files.append({"name": name, "data": data, "block": block_index})
    return (blocks if paths else text), files


def make_content(text, paths):
    return prepare_content(text, paths)[0]


def display_content(content):
    if isinstance(content, str):
        return content
    lines = []
    for index, block in enumerate(content or []):
        if block.get("type") == "text":
            text = block.get("text", "")
            if index and text.startswith(("Arquivo anexado: ", "Imagem anexada: ")):
                text = text.split("\n", 1)[0]
            lines.append(text)
    return "\n".join(lines)
