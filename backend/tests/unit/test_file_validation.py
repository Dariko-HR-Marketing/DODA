"""FR-KNW-001's own acceptance criterion: a security test proving a
malicious/malformed upload is rejected. `validate_file` is pure and
DB-free, so this is a plain unit test file, no fixtures needed.
"""

import io
import zipfile

import pytest

from doda.domain.knowledge.file_validation import (
    FileContentMismatchError,
    FileTooLargeError,
    FileValidationError,
    InvalidFilenameError,
    UnsupportedFileTypeError,
    sanitize_filename,
    storage_key_for,
    validate_file,
)

_REAL_PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nrest of a real pdf body"
_REAL_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_WINDOWS_PE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00rest of a windows executable"


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


_REAL_DOCX_BYTES = _zip_bytes({"word/document.xml": b"<document/>", "[Content_Types].xml": b"<Types/>"})
_REAL_XLSX_BYTES = _zip_bytes({"xl/workbook.xml": b"<workbook/>", "[Content_Types].xml": b"<Types/>"})


def test_a_well_formed_pdf_is_accepted() -> None:
    content_type = validate_file(
        filename="report.pdf",
        declared_content_type="application/pdf",
        data=_REAL_PDF_BYTES,
        max_size_bytes=1_000_000,
    )
    assert content_type == "application/pdf"


def test_a_well_formed_png_is_accepted() -> None:
    content_type = validate_file(
        filename="chart.png",
        declared_content_type="image/png",
        data=_REAL_PNG_BYTES,
        max_size_bytes=1_000_000,
    )
    assert content_type == "image/png"


def test_a_well_formed_docx_is_accepted() -> None:
    content_type = validate_file(
        filename="report.docx",
        declared_content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=_REAL_DOCX_BYTES,
        max_size_bytes=1_000_000,
    )
    assert content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_a_well_formed_xlsx_is_accepted() -> None:
    content_type = validate_file(
        filename="budget.xlsx",
        declared_content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        data=_REAL_XLSX_BYTES,
        max_size_bytes=1_000_000,
    )
    assert content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_a_generic_zip_archive_renamed_to_docx_is_rejected() -> None:
    """A well-formed ZIP that is NOT an OOXML Word package (no
    word/document.xml) — e.g. a renamed .epub, .jar, or an arbitrary
    archive — used to pass validation because only the ZIP magic bytes
    were checked, not the actual OOXML container contents."""
    not_a_docx = _zip_bytes({"readme.txt": b"this is just a plain zip, not a Word document"})
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="report.docx",
            declared_content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            data=not_a_docx,
            max_size_bytes=1_000_000,
        )


def test_an_xlsx_renamed_from_a_docx_is_rejected() -> None:
    """Both share the same ZIP magic bytes — only the internal member
    (xl/workbook.xml vs word/document.xml) tells them apart."""
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="budget.xlsx",
            declared_content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            data=_REAL_DOCX_BYTES,
            max_size_bytes=1_000_000,
        )


def test_a_corrupted_zip_with_a_docx_extension_is_rejected() -> None:
    """Valid ZIP magic bytes followed by garbage (truncated upload, or a
    deliberately malformed archive) must not raise an unhandled
    zipfile.BadZipFile out of validate_file — it is caught and converted
    to the same FileContentMismatchError as every other mismatch."""
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="report.docx",
            declared_content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            data=b"PK\x03\x04" + b"\x00" * 32,
            max_size_bytes=1_000_000,
        )


def test_a_plain_utf8_text_file_is_accepted() -> None:
    content_type = validate_file(
        filename="notes.txt",
        declared_content_type="text/plain",
        data=b"Salom, DODA!",
        max_size_bytes=1_000_000,
    )
    assert content_type == "text/plain"


def test_a_windows_executable_renamed_to_pdf_is_rejected() -> None:
    """The security-test acceptance criterion, made concrete: a Windows
    PE binary with a .pdf extension and a matching declared Content-Type
    must still be rejected, because its actual bytes are an executable,
    not a PDF."""
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="invoice.pdf",
            declared_content_type="application/pdf",
            data=_WINDOWS_PE_BYTES,
            max_size_bytes=1_000_000,
        )


def test_an_elf_executable_renamed_to_a_supported_extension_is_rejected() -> None:
    elf_bytes = b"\x7fELF" + b"\x00" * 32
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="photo.png",
            declared_content_type="image/png",
            data=elf_bytes,
            max_size_bytes=1_000_000,
        )


def test_a_shell_script_renamed_to_txt_is_rejected() -> None:
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="notes.txt",
            declared_content_type="text/plain",
            data=b"#!/bin/sh\nrm -rf /\n",
            max_size_bytes=1_000_000,
        )


def test_a_file_larger_than_the_limit_is_rejected() -> None:
    with pytest.raises(FileTooLargeError):
        validate_file(
            filename="report.pdf",
            declared_content_type="application/pdf",
            data=_REAL_PDF_BYTES,
            max_size_bytes=len(_REAL_PDF_BYTES) - 1,
        )


def test_an_empty_file_is_rejected() -> None:
    with pytest.raises(FileValidationError):
        validate_file(
            filename="report.pdf", declared_content_type="application/pdf", data=b"", max_size_bytes=1_000_000
        )


def test_an_unsupported_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_file(
            filename="archive.zip",
            declared_content_type="application/zip",
            data=b"PK\x03\x04rest",
            max_size_bytes=1_000_000,
        )


def test_a_declared_content_type_that_does_not_match_the_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_file(
            filename="report.pdf",
            declared_content_type="image/png",
            data=_REAL_PDF_BYTES,
            max_size_bytes=1_000_000,
        )


def test_a_binary_blob_renamed_to_txt_is_rejected() -> None:
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="notes.txt",
            declared_content_type="text/plain",
            data=b"\xff\xfe\x00\x01not valid utf-8: \x80\x81",
            max_size_bytes=1_000_000,
        )


def test_a_corrupted_or_truncated_upload_with_the_right_extension_is_rejected() -> None:
    """FileContentMismatchError's own docstring claims it catches "a
    renamed executable OR a truncated/corrupted upload" — the renamed-
    executable half is covered above, but garbage bytes that are also not
    one of the recognized executable signatures (so they fall through to
    the plain magic-byte mismatch branch, not the executable-signature
    one) had never been exercised."""
    with pytest.raises(FileContentMismatchError):
        validate_file(
            filename="report.pdf",
            declared_content_type="application/pdf",
            data=b"not actually a pdf, just garbage bytes",
            max_size_bytes=1_000_000,
        )


@pytest.mark.parametrize(
    "filename", ["../../etc/passwd.pdf", "a/b.pdf", "a\\b.pdf", "", "a" * 300 + ".pdf", "a\x00b.pdf"]
)
def test_a_suspicious_or_malformed_filename_is_rejected(filename: str) -> None:
    with pytest.raises(InvalidFilenameError):
        sanitize_filename(filename)


def test_a_filename_with_no_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_file(
            filename="report",
            declared_content_type="application/pdf",
            data=_REAL_PDF_BYTES,
            max_size_bytes=1000,
        )


def test_storage_key_is_derived_only_from_server_generated_ids() -> None:
    import uuid

    customer_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    document_id = uuid.uuid4()
    key = storage_key_for(customer_id=customer_id, workspace_id=workspace_id, document_id=document_id)
    assert key == f"{customer_id}/{workspace_id}/{document_id}"
