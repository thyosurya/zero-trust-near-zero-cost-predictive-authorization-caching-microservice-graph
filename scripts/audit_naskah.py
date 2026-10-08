import re

with open('draft/naskah-artikel.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

findings = []

def report(cat, line_no, msg, snippet):
    findings.append({
        'category': cat,
        'line': line_no,
        'message': msg,
        'snippet': snippet.strip()
    })

in_code = False
for idx, line in enumerate(lines, 1):
    raw = line
    if raw.strip().startswith('```'):
        in_code = not in_code
        continue
    if in_code:
        continue

    # 1. Spasi ganda di dalam teks (di luar tabel dan blok kode)
    if not raw.strip().startswith('|'):
        trimmed = raw.rstrip()
        m_dsp = re.search(r'[^\s] {2,}[^\s]', trimmed)
        if m_dsp:
            report('SPASI_GANDA', idx, f'Spasi ganda di "{m_dsp.group()}"', raw)

    # 2. Spasi sebelum tanda baca (, . : ; ? !)
    if not raw.strip().startswith('|') and not raw.strip().startswith('$$'):
        no_math = re.sub(r'\$.*?\$', '[MATH]', raw)
        no_url = re.sub(r'\]\([^)]+\)', ']', no_math)
        m_sp_punc = re.search(r'[a-zA-Z0-9\)]\s+[,;:!?]', no_url)
        if m_sp_punc:
            report('TANDA_BACA_SPASI', idx, f'Spasi sebelum tanda baca: "{m_sp_punc.group()}"', raw)

    # 3. Tanda baca ganda (di luar ellipsis ...)
    no_math = re.sub(r'\$.*?\$', '[MATH]', raw)
    no_ellip = re.sub(r'\.{3,}', '[ELLIP]', no_math)
    if not raw.strip().startswith('#'):
        m_dbl = re.search(r'([,;:!?]{2,}|\.\.)', no_ellip)
        if m_dbl:
            report('TANDA_BACA_GANDA', idx, f'Tanda baca berulang: "{m_dbl.group()}"', raw)

    # 4. Kosakata & Ejaan Baku KBBI
    if re.search(r'\botentikasi\b', raw, re.IGNORECASE):
        report('EJAAN_KBBI', idx, 'Kata "otentikasi" -> baku: "autentikasi"', raw)
    if re.search(r'\bteoritis\b', raw, re.IGNORECASE):
        report('EJAAN_KBBI', idx, 'Kata "teoritis" -> baku: "teoretis"', raw)
    if re.search(r'\banalisa\b', raw, re.IGNORECASE):
        report('EJAAN_KBBI', idx, 'Kata "analisa" -> baku: "analisis"', raw)
    if re.search(r'\bpraktek\b', raw, re.IGNORECASE):
        report('EJAAN_KBBI', idx, 'Kata "praktek" -> baku: "praktik"', raw)
    if re.search(r'\bstandarisasi\b', raw, re.IGNORECASE):
        report('EJAAN_KBBI', idx, 'Kata "standarisasi" -> baku: "standardisasi"', raw)
    if re.search(r'\bhirarki\b', raw, re.IGNORECASE):
        report('EJAAN_KBBI', idx, 'Kata "hirarki" -> baku: "hierarki"', raw)

    # 5. Kata terikat "antar-" (EYD V)
    m_antar = re.search(r'\bantar\s+(service|backend|node|topologi|kelompok)\b', raw, re.IGNORECASE)
    if m_antar:
        report('BENTUK_TERIKAT', idx, f'Bentuk terikat "{m_antar.group()}" -> sambung/tanda hubung: antar-{m_antar.group(1)} / antar{m_antar.group(1)}', raw)

    # 6. Kata "script" -> "skrip"
    if idx < 500 and not raw.strip().startswith('|'):
        m_script = re.search(r'(?<!\*)\bscript\b(?!\*)', raw, re.IGNORECASE)
        if m_script:
            report('KATA_SERAPAN', idx, 'Kata "script" -> gunakan bahasa baku "skrip" atau cetak miring (*script*)', raw)

    # 7. Inkonsistensi "Zero-Trust" (dengan strip) vs "Zero Trust" (tanpa strip)
    m_zt = re.search(r'\bZero-Trust\b', raw)
    if m_zt and idx > 2:
        report('INKONSISTENSI_ISTILAH', idx, 'Kata "Zero-Trust" (dengan strip) -> seragamkan dengan "Zero Trust"', raw)

    # 8. Sitasi parentetikal APA 7th: (Author dan Author, Year) -> seharusnya ampersand &
    m_apa_dan = re.search(r'\([A-Z][a-zA-Z\s,]+?\s+dan\s+[A-Z][a-zA-Z\s,]+?,\s*\d{4}\)', raw)
    if m_apa_dan:
        report('SITASI_APA', idx, f'Sitasi parentetikal "{m_apa_dan.group()}" -> gunakan ampersand "&" sesuai APA: "{m_apa_dan.group().replace(" dan ", " & ")}"', raw)

    # 9. Rentang nomor halaman di daftar pustaka (hyphen - vs en-dash –)
    if idx >= 502:
        no_url_dapus = re.sub(r'https?://\S+', '', raw)
        m_pages_hyphen = re.search(r'\b(\d+)-(\d+)\b', no_url_dapus)
        if m_pages_hyphen:
            # pastikan bukan NIST SP 800-207 atau tanggal
            p1, p2 = m_pages_hyphen.groups()
            if int(p1) > 0 and int(p2) > 0 and not p1.startswith('800') and not p1.startswith('202'):
                report('TIPOGRAFI_DAPUS', idx, f'Rentang halaman "{p1}-{p2}" sebaiknya memakai en-dash ("{p1}–{p2}")', raw)

print(f"Total temuan audit: {len(findings)}\n")
for f in findings:
    print(f"[{f['category']}] Baris {f['line']}: {f['message']}")
    print(f"   Konteks: {f['snippet'][:110]}\n")
