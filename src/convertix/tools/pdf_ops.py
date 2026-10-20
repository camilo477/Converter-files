"""PDF tools preserve page objects; no page rasterization during editing."""
import re
from pathlib import Path
from ..detect import MAX_PAGES
from ..models import ConversionError


def open_pdf(path):
    import pymupdf
    try:
        doc = pymupdf.open(path)
        if not doc.is_pdf:
            doc.close()
            raise ConversionError("El archivo seleccionado no es un documento PDF.")
        if doc.needs_pass or doc.is_encrypted:
            doc.close()
            raise ConversionError("El PDF está protegido; crea antes una copia sin contraseña.")
        if not 1 <= len(doc) <= MAX_PAGES:
            doc.close()
            raise ConversionError(f"PDF vacío o con más de {MAX_PAGES} páginas.")
        if doc.is_repaired:
            doc.close()
            raise ConversionError("El PDF está dañado y necesita reparación antes de modificarlo.")
        return doc
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"No se puede abrir el PDF: {exc}") from exc


def check_signatures(doc, params):
    if doc.get_sigflags() > 0 and not params.get("allow_signed", False):
        raise ConversionError("El PDF contiene campos de firma. Reescribirlo puede invalidar firmas digitales; activa la aceptación correspondiente para generar una copia.")


def parse_pages(text, count):
    if not isinstance(text, str) or len(text) > 10000 or not text.strip():
        raise ConversionError("Introduce páginas o rangos, por ejemplo 1,3,5-8.")
    pages = []
    for part in text.split(","):
        match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not match:
            raise ConversionError("Rango inválido. Usa 1,3,5-8; separa grupos de archivos con punto y coma.")
        start, end = int(match[1]), int(match[2] or match[1])
        if not 1 <= start <= end <= count:
            raise ConversionError(f"Rango fuera de límites: el PDF tiene {count} páginas.")
        for number in range(start-1, end):
            if number not in pages:
                pages.append(number)
    return pages


def split_groups(params, count):
    mode = params.get("split_mode", "extract")
    if mode == "extract":
        return [parse_pages(params.get("pages", ""), count)]
    if mode == "each":
        return [[i] for i in range(count)]
    if mode == "interval":
        size = int(params.get("interval", 1))
        if not 1 <= size <= count:
            raise ConversionError("El intervalo debe estar entre 1 y el número de páginas.")
        return [list(range(i, min(i+size, count))) for i in range(0, count, size)]
    if mode == "ranges":
        text = params.get("pages", "")
        if not isinstance(text, str) or len(text) > 10000:
            raise ConversionError("Introduce rangos válidos.")
        return [parse_pages(group, count) for group in text.split(";")]
    raise ConversionError("Modo de división desconocido.")


def save(doc, path):
    doc.save(path, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True,
             use_objstms=1, incremental=False)


def verify_pdf(path, sizes):
    with open_pdf(path) as doc:
        if len(doc) != len(sizes):
            raise ConversionError("El PDF generado no conserva el número esperado de páginas.")
        for page, expected in zip(doc, sizes):
            if any(abs(a-b) > 0.1 for a, b in zip((page.rect.width, page.rect.height), expected)):
                raise ConversionError("Cambió inesperadamente el tamaño de una página.")
            page.get_text()  # Parse each published page, not only its header.


def merge(paths, params, output, progress):
    import pymupdf
    if len(paths) < 2:
        raise ConversionError("Añade al menos dos PDFs para unirlos.")
    sizes, toc = [], []
    with pymupdf.open() as result:
        for i, path in enumerate(paths):
            progress(f"Uniendo PDF {i+1}/{len(paths)}")
            with open_pdf(path) as doc:
                check_signatures(doc, params)
                offset = len(result)
                if offset+len(doc) > MAX_PAGES:
                    raise ConversionError(f"El resultado excedería {MAX_PAGES} páginas.")
                sizes += [(p.rect.width, p.rect.height) for p in doc]
                result.insert_pdf(doc, links=True, annots=True, widgets=True)
                for level, title, page in doc.get_toc():
                    if page > 0:
                        toc.append([level, title, page+offset])
        if toc:
            # A filtered outline may skip hierarchy levels; normalize without losing titles.
            previous = 0
            for item in toc:
                item[0] = min(item[0], previous+1)
                previous = item[0]
            result.set_toc(toc)
        path = output/"unido.pdf"
        save(result, path)
    verify_pdf(path, sizes)
    return {"name": "documentos_unidos.pdf", "summary": f"PDF unido correctamente · {len(sizes)} páginas"}


def split(paths, params, output, progress):
    if len(paths) != 1:
        raise ConversionError("Selecciona un único PDF para dividirlo.")
    with open_pdf(paths[0]) as doc:
        check_signatures(doc, params)
        groups = split_groups(params, len(doc))
        sizes = [(p.rect.width, p.rect.height) for p in doc]
    stem = Path(params["original_names"][0]).stem
    for i, group in enumerate(groups):
        progress(f"Creando parte {i+1}/{len(groups)} · {len(group)} páginas")
        with open_pdf(paths[0]) as doc:
            toc = [[level, title, group.index(page-1)+1] for level, title, page in doc.get_toc() if page-1 in group]
            doc.select(group)
            previous = 0
            for item in toc:
                item[0] = min(item[0], previous+1)
                previous = item[0]
            doc.set_toc(toc)
            path = output/f"{stem}_parte_{i+1}.pdf"
            save(doc, path)
        verify_pdf(path, [sizes[n] for n in group])
    return {"name": stem+"_extraido.pdf" if len(groups) == 1 else stem+"_partes",
            "directory": len(groups) > 1, "summary": f"Se crearon {len(groups)} documentos · {sum(map(len, groups))} páginas"}


def optimize(paths, params, output, progress):
    if len(paths) != 1:
        raise ConversionError("Optimiza un PDF por trabajo.")
    mode = params.get("level", "lossless")
    if mode not in ("lossless", "balanced", "maximum"):
        raise ConversionError("Nivel de optimización desconocido.")
    path = output/"optimizado.pdf"
    with open_pdf(paths[0]) as doc:
        check_signatures(doc, params)
        sizes = [(p.rect.width, p.rect.height) for p in doc]
        text = [p.get_text() for p in doc]
        progress("Optimizando recursos PDF…")
        if mode != "lossless":
            dpi, quality = (150, 80) if mode == "balanced" else (96, 55)
            doc.rewrite_images(dpi_threshold=round(dpi*1.3), dpi_target=dpi, quality=quality,
                               bitonal=False, set_to_gray=False)
        save(doc, path)
    verify_pdf(path, sizes)
    with open_pdf(path) as doc:
        if [p.get_text() for p in doc] != text:
            raise ConversionError("La optimización alteró el texto seleccionable; se descartó.")
    stats, summary = reduction(paths[0], path, mode, params)
    return {"name": Path(params["original_names"][0]).stem+"_optimizado.pdf", "summary": summary, "stats": stats}


def reduction(source, output, mode, params):
    before, after = source.stat().st_size, output.stat().st_size
    saving = round((1-after/before)*100, 2)
    if after >= before and not params.get("keep_larger", False):
        raise ConversionError(f"No hubo reducción: {before:,} → {after:,} bytes ({saving:+.2f} % de ahorro). No se publicó. Puedes elegir conservarlo expresamente.")
    stats = {"original_bytes": before, "result_bytes": after, "saving_percent": saving, "level": mode}
    label = "Sin pérdida" if mode == "lossless" else "Equilibrado" if mode == "balanced" else "Máximo"
    return stats, f"{before:,} → {after:,} bytes · ahorro {saving:.2f} % · {label}"
