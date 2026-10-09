"""Small canonical catalog for normalized Model Security findings.

Native dependency identifiers stay inside the adapter boundary. Workflow
output uses only stable, product-owned codes and generic analysis names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class SecurityErrorDefinition:
    """One scanner finding with a product-owned code and bilingual guidance."""

    engine: str
    source_code: str
    source_name: str
    risk_level: str
    english_description: str
    turkish_description: str
    guidance_en: str
    guidance_tr: str
    source_condition: str = ""
    custom_code: str = ""


_PREFIX_BY_RISK = {
    "low": "L",
    "medium": "M",
    "high": "H",
    "critical": "C",
    "info": "I",
    "debug": "I",
    "warning": "M",
    "suspicious": "M",
    "possibly_unsafe": "L",
    "likely_unsafe": "H",
    "likely_overtly_malicious": "C",
    "overtly_malicious": "C",
}


def _risk_level(value: Any) -> str:
    """Normalize dependency severity names and numeric values."""

    if isinstance(value, bool):
        return "info"
    if isinstance(value, (int, float)):
        number = int(value)
        if number >= 4:
            return "critical"
        if number >= 3:
            return "high"
        if number >= 2:
            return "medium"
        if number == 1:
            return "low"
        return "info"
    name = getattr(value, "name", value)
    normalized = str(name or "info").strip().lower().split(".")[-1]
    return normalized if normalized in _PREFIX_BY_RISK else "info"


def risk_prefix(value: Any) -> str:
    """Return the product prefix (L/M/H/C/I) for a scanner severity."""

    return _PREFIX_BY_RISK.get(_risk_level(value), "I")


def _source_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _artifact_rule_translation(code: str, fallback: str) -> str:
    return ARTIFACT_RULE_TURKISH.get(
        code,
        f"{fallback.rstrip('.')} güvenlik bulgusu tespit edildi.",
    )


def _guidance(engine: str, source_code: str) -> tuple[str, str]:
    """Use short, actionable guidance without duplicating scanner logic."""

    token = _source_token(source_code)
    if engine == "artifact_analysis":
        try:
            number = int(re.sub(r"[^0-9]", "", source_code))
        except ValueError:
            number = 0
        if 100 <= number < 200 or 1100 <= number < 1200:
            return (
                "Remove the unsafe code path or use a trusted, allowlisted loader before deployment.",
                "Dağıtımdan önce güvensiz kod yolunu kaldırın veya güvenilir ve izin verilen bir yükleyici kullanın.",
            )
        if 200 <= number < 300:
            return (
                "Do not deserialize untrusted pickle data; prefer safetensors or a restricted weights-only loader.",
                "Güvenilmeyen pickle verisini serileştirmeden çıkarmayın; safetensors veya kısıtlı weights-only yükleyici kullanın.",
            )
        if 300 <= number < 400:
            return (
                "Remove unexpected network behavior and restrict any required endpoint to an explicit allowlist.",
                "Beklenmeyen ağ davranışını kaldırın; gerekli uç noktaları açık bir izin listesiyle sınırlandırın.",
            )
        if 400 <= number < 500:
            return (
                "Validate archive members and paths, reject traversal or links, and rebuild the artifact if needed.",
                "Arşiv üyelerini ve yolları doğrulayın, dizin kaçışlarını veya bağlantıları reddedin; gerekirse artefaktı yeniden oluşturun.",
            )
        if 500 <= number < 600:
            return (
                "Remove embedded executables or scripts and rebuild the model from a trusted source.",
                "Gömülü çalıştırılabilir dosyaları veya betikleri kaldırın ve modeli güvenilir bir kaynaktan yeniden oluşturun.",
            )
        if 600 <= number < 700:
            return (
                "Decode and inspect the payload; reject obfuscation that is not documented and required.",
                "Yükü çözerek inceleyin; belgelenmemiş ve gerekli olmayan gizleme yöntemlerini reddedin.",
            )
        if 700 <= number < 800:
            return (
                "Remove exposed credentials, rotate affected secrets, and rescan the artifact.",
                "Açığa çıkan kimlik bilgilerini kaldırın, etkilenen sırları yenileyin ve artefaktı yeniden tarayın.",
            )
        if 800 <= number < 900:
            return (
                "Compare the model against a trusted build and review unexpected weights or layers before release.",
                "Modeli güvenilir bir derlemeyle karşılaştırın; yayımdan önce beklenmeyen ağırlıkları veya katmanları inceleyin.",
            )
        if 900 <= number < 1000:
            return (
                "Verify the file signature and format, then regenerate the artifact if its structure is invalid.",
                "Dosya imzasını ve biçimini doğrulayın; yapısı geçersizse artefaktı yeniden üretin.",
            )
        if 1000 <= number < 1100:
            return (
                "Verify provenance, signatures, hashes, and license compatibility before accepting the model.",
                "Modeli kabul etmeden önce kaynağı, imzaları, özetleri ve lisans uyumluluğunu doğrulayın.",
            )
        return (
            "Review the finding and confirm that the artifact was produced by a trusted, reproducible process.",
            "Bulguyu inceleyin ve artefaktın güvenilir, tekrarlanabilir bir süreçle üretildiğini doğrulayın.",
        )

    if "resourceexhaustion" in token or "expansionattack" in token:
        return (
            "Reject the artifact and enforce bounded interpretation resources before retrying.",
            "Artefaktı reddedin ve yeniden denemeden önce yorumlama kaynaklarını sınırlandırın.",
        )
    if (
        "scannerdeactivation" in token
        or "unsafeimports" in token
        or "overtlybadeval" in token
    ):
        return (
            "Reject the pickle and inspect how executable imports or calls entered the artifact.",
            "Pickle dosyasını reddedin ve çalıştırılabilir içe aktarmaların veya çağrıların artefakta nasıl girdiğini inceleyin.",
        )
    if "import" in token or "allowlist" in token:
        return (
            "Remove the untrusted import or explicitly review it against the approved ML allowlist.",
            "Güvenilmeyen içe aktarmayı kaldırın veya onaylı ML izin listesine göre açıkça inceleyin.",
        )
    if "error" in token or "opcode" in token or "proto" in token:
        return (
            "Treat the artifact as untrusted, validate it with a clean rebuild, and do not deserialize it directly.",
            "Artefaktı güvenilmeyen kabul edin, temiz bir yeniden üretimle doğrulayın ve doğrudan serileştirmeden çıkarmayın.",
        )
    return (
        "Review the finding before allowing the model into a serving environment.",
        "Modeli sunum ortamına almadan önce bulguyu inceleyin.",
    )


def _load_artifact_rule_entries() -> list[SecurityErrorDefinition]:
    try:
        from modelaudit.rule_catalog import RULE_CATALOG  # noqa: PLC0415
    except Exception:
        return []

    entries: list[SecurityErrorDefinition] = []
    for native in RULE_CATALOG:
        code = str(getattr(native, "code", "")).strip().upper()
        if not code:
            continue
        name = str(getattr(native, "name", code)).strip()
        description = str(getattr(native, "description", name)).strip()
        risk = _risk_level(getattr(native, "severity", "info"))
        guidance_en, guidance_tr = _guidance("artifact_analysis", code)
        entries.append(
            SecurityErrorDefinition(
                engine="artifact_analysis",
                source_code=code,
                source_name=name,
                risk_level=risk,
                english_description=description,
                turkish_description=_artifact_rule_translation(code, description),
                guidance_en=guidance_en,
                guidance_tr=guidance_tr,
            )
        )
    return entries


def _serialization_entry(
    source_code: str,
    risk_level: str,
    source_name: str,
    english_description: str,
    turkish_description: str,
    *,
    source_condition: str = "",
) -> SecurityErrorDefinition:
    guidance_en, guidance_tr = _guidance("serialization_analysis", source_code)
    return SecurityErrorDefinition(
        engine="serialization_analysis",
        source_code=source_code,
        source_name=source_name,
        risk_level=risk_level,
        english_description=english_description,
        turkish_description=turkish_description,
        guidance_en=guidance_en,
        guidance_tr=guidance_tr,
        source_condition=source_condition,
    )


def _load_serialization_entries() -> list[SecurityErrorDefinition]:
    return [
        _serialization_entry(
            "DuplicateProtoAnalysis",
            "high",
            "Duplicate PROTO opcode",
            "A duplicate PROTO opcode may indicate a tampered pickle.",
            "Yinelenen PROTO opcode'u değiştirilmiş bir pickle dosyasına işaret edebilir.",
        ),
        _serialization_entry(
            "MisplacedProtoAnalysis",
            "high",
            "Misplaced PROTO opcode",
            "A PROTO opcode appears in an invalid position and may indicate tampering.",
            "PROTO opcode'u geçersiz bir konumda bulunuyor; bu durum değiştirme girişimine işaret edebilir.",
        ),
        _serialization_entry(
            "InvalidOpcode",
            "high",
            "Invalid pickle opcode",
            "The file contains invalid opcode(s) and may be corrupted or crafted to bypass analysis.",
            "Dosya geçersiz opcode'lar içeriyor; bozulmuş olabilir veya analizi atlatmak için hazırlanmış olabilir.",
        ),
        _serialization_entry(
            "InterpretationError",
            "high",
            "Malformed opcode sequence",
            "The pickle contains malformed opcode sequences and cannot be trusted.",
            "Pickle dosyası bozuk opcode dizileri içeriyor ve güvenilir kabul edilemez.",
        ),
        _serialization_entry(
            "ResourceExhaustion",
            "critical",
            "Resource exhaustion",
            "Interpretation exceeded resource limits, indicating a possible expansion denial-of-service attack.",
            "Yorumlama kaynak sınırlarını aştı; bu durum olası bir genişleme tabanlı hizmet engelleme saldırısına işaret eder.",
        ),
        _serialization_entry(
            "NonStandardImports",
            "high",
            "Non-standard import",
            "The pickle imports a non-standard Python module that can execute arbitrary code.",
            "Pickle dosyası keyfi kod çalıştırabilecek standart dışı bir Python modülü içe aktarıyor.",
        ),
        _serialization_entry(
            "UnsafeImportsML",
            "critical",
            "Unsafe ML import",
            "The pickle uses an ML module or function that can load, compile, or execute untrusted code.",
            "Pickle dosyası güvenilmeyen kodu yükleyebilen, derleyebilen veya çalıştırabilen riskli bir ML modülü ya da işlevi kullanıyor.",
        ),
        _serialization_entry(
            "OvertlyBadEval",
            "critical",
            "Overtly malicious call",
            "The pickle calls eval, exec, compile, open, or another function in a way that is almost certainly malicious.",
            "Pickle dosyası eval, exec, compile, open veya başka bir işlevi neredeyse kesinlikle kötü amaçlı olacak şekilde çağırıyor.",
            source_condition="Analysis severity is OVERTLY_MALICIOUS.",
        ),
        _serialization_entry(
            "OvertlyBadEval",
            "high",
            "Unsafe executable call",
            "The pickle calls a function that can execute arbitrary code and is inherently unsafe.",
            "Pickle dosyası keyfi kod çalıştırabilen ve doğası gereği güvensiz olan bir işlevi çağırıyor.",
            source_condition="Analysis severity is LIKELY_UNSAFE.",
        ),
        _serialization_entry(
            "UnsafeImports",
            "critical",
            "Unsafe import",
            "The pickle imports a suspicious module that is indicative of an overtly malicious file.",
            "Pickle dosyası açıkça kötü amaçlı bir dosyaya işaret eden şüpheli bir modülü içe aktarıyor.",
        ),
        _serialization_entry(
            "UnusedVariables",
            "medium",
            "Unused suspicious variable",
            "An assigned value is never used, which may indicate a hidden malicious payload.",
            "Atanan bir değer hiç kullanılmıyor; bu durum gizlenmiş kötü amaçlı bir yüke işaret edebilir.",
        ),
        _serialization_entry(
            "ScannerDeactivation",
            "critical",
            "Scanner deactivation attempt",
            "The pickle imports a security scanner library in an attempt to deactivate or interfere with analysis.",
            "Pickle dosyası analizi devre dışı bırakmaya veya engellemeye çalışarak bir güvenlik tarayıcısı kütüphanesini içe aktarıyor.",
        ),
        _serialization_entry(
            "ExpansionAttackAnalysis",
            "high",
            "Expansion attack pattern",
            "The pickle has an extreme GET/PUT or duplication pattern that can cause resource exhaustion.",
            "Pickle dosyasında kaynak tükenmesine yol açabilecek aşırı GET/PUT veya çoğaltma deseni bulunuyor.",
            source_condition="Analysis severity is LIKELY_UNSAFE.",
        ),
        _serialization_entry(
            "ExpansionAttackAnalysis",
            "medium",
            "Possible expansion attack pattern",
            "The pickle has a suspicious GET/PUT or duplication pattern that may indicate expansion abuse.",
            "Pickle dosyasında genişleme istismarına işaret edebilecek şüpheli bir GET/PUT veya çoğaltma deseni bulunuyor.",
            source_condition="Analysis severity is SUSPICIOUS.",
        ),
        _serialization_entry(
            "MLAllowlist",
            "high",
            "ML allowlist violation",
            "The pickle imports an ML module or symbol outside the approved allowlist.",
            "Pickle dosyası onaylı izin listesi dışında bir ML modülünü veya sembolünü içe aktarıyor.",
        ),
        _serialization_entry(
            "FileError",
            "medium",
            "File read error",
            "The analysis engine could not read the target file, so the security result is incomplete.",
            "Analiz motoru hedef dosyayı okuyamadı; bu nedenle güvenlik sonucu eksik kaldı.",
            source_condition="Loader error prefix: File error.",
        ),
        _serialization_entry(
            "ReadError",
            "medium",
            "Archive member read error",
            "The analysis engine could not read an archive member, so the security result is incomplete.",
            "Analiz motoru bir arşiv üyesini okuyamadı; bu nedenle güvenlik sonucu eksik kaldı.",
            source_condition="Loader error prefix: Read error.",
        ),
        _serialization_entry(
            "ArchiveError",
            "medium",
            "Archive read error",
            "The analysis engine could not open the archive, so the security result is incomplete.",
            "Analiz motoru arşivi açamadı; bu nedenle güvenlik sonucu eksik kaldı.",
            source_condition="Loader error prefix: Archive error.",
        ),
        _serialization_entry(
            "AnalysisError",
            "high",
            "Analysis execution error",
            "The engine failed while running a security analysis, so the result must be treated as inconclusive.",
            "Motor güvenlik analizini çalıştırırken başarısız oldu; sonuç kesin olmayan kabul edilmelidir.",
            source_condition="Loader error prefix: Analysis error.",
        ),
        _serialization_entry(
            "ParseError",
            "high",
            "Pickle parse error",
            "The analysis engine could not parse the pickle; malformed or intentionally evasive content may be present.",
            "Analiz motoru pickle dosyasını ayrıştıramadı; bozuk veya kasıtlı olarak kaçamak hazırlanmış içerik olabilir.",
            source_condition="Loader error prefix: Parse error.",
        ),
        _serialization_entry(
            "UnexpectedError",
            "high",
            "Unexpected scanner error",
            "The analysis engine raised an unexpected error, so the security result is not conclusive.",
            "Analiz motoru beklenmeyen bir hata verdi; bu nedenle güvenlik sonucu kesin değildir.",
            source_condition="Loader error prefix: Unexpected error.",
        ),
    ]


@lru_cache(maxsize=1)
def get_security_error_catalog() -> tuple[SecurityErrorDefinition, ...]:
    """Return the complete catalog with stable per-risk sequential codes."""

    entries = [*_load_artifact_rule_entries(), *_load_serialization_entries()]
    counters = {prefix: 0 for prefix in ("L", "M", "H", "C", "I")}
    assigned: list[SecurityErrorDefinition] = []
    for entry in entries:
        prefix = risk_prefix(entry.risk_level)
        counters[prefix] += 1
        assigned.append(replace(entry, custom_code=f"{prefix}{counters[prefix]:03d}"))
    return tuple(assigned)


def _canonical_engine(value: Any) -> str:
    token = _source_token(value)
    if token in {"artifactanalysis", "staticanalysis"}:
        return "artifact_analysis"
    if token in {"serializationanalysis", "picklesecurity", "pickleanalysis"}:
        return "serialization_analysis"
    return str(value or "").strip()


def infer_serialization_source_code(value: Any) -> str:
    """Infer a stable serialization-analysis key from a result or error string."""

    text = str(value or "")
    token = _source_token(text)
    for candidate in (
        "ResourceExhaustion",
        "ScannerDeactivation",
        "UnsafeImportsML",
        "UnsafeImports",
        "OvertlyBadEval",
        "ExpansionAttackAnalysis",
        "NonStandardImports",
        "DuplicateProtoAnalysis",
        "MisplacedProtoAnalysis",
        "InvalidOpcode",
        "InterpretationError",
        "UnusedVariables",
        "MLAllowlist",
    ):
        if _source_token(candidate) in token:
            return candidate
    for prefix, candidate in (
        ("fileerror", "FileError"),
        ("readerror", "ReadError"),
        ("archiveerror", "ArchiveError"),
        ("analysiserror", "AnalysisError"),
        ("parseerror", "ParseError"),
        ("unexpectederror", "UnexpectedError"),
    ):
        if prefix in token:
            return candidate
    if "invalidopcode" in token or "invalidopcode" in _source_token(text):
        return "InvalidOpcode"
    if "malformedopcodesequence" in token or "interpretationerror" in token:
        return "InterpretationError"
    return ""


def find_security_error(
    engine: Any,
    source_code: Any,
    *,
    severity: Any = None,
) -> SecurityErrorDefinition | None:
    """Find a catalog row by native engine identifier and observed severity."""

    engine_name = _canonical_engine(engine)
    source = str(source_code or "").strip()
    if engine_name == "serialization_analysis":
        source = infer_serialization_source_code(source) or source
    source_token = _source_token(source)
    if not source_token:
        return None
    candidates = [
        entry
        for entry in get_security_error_catalog()
        if entry.engine == engine_name
        and _source_token(entry.source_code) == source_token
    ]
    if not candidates:
        return None
    if severity is not None:
        requested_prefix = risk_prefix(severity)
        for candidate in candidates:
            if risk_prefix(candidate.risk_level) == requested_prefix:
                return candidate
    return candidates[0]


def enrich_security_finding(
    engine: Any,
    source_code: Any,
    *,
    severity: Any = None,
    message: Any = None,
) -> dict[str, str]:
    """Return product-owned fields for a scanner finding, if it is cataloged."""

    source = str(source_code or "").strip()
    if _canonical_engine(engine) == "serialization_analysis":
        source = infer_serialization_source_code(source) or source
    definition = find_security_error(engine, source, severity=severity)
    if definition is None:
        return {}
    return {
        "rule_code": definition.custom_code,
        "risk_level": definition.risk_level,
        "rule_description": definition.english_description,
        "rule_solution": definition.guidance_en,
    }


def catalog_as_rows() -> list[dict[str, str]]:
    """Return workbook-friendly rows without exposing dataclass internals."""

    return [
        {
            "custom_code": entry.custom_code,
            "source_name": entry.source_name,
            "risk_level": entry.risk_level,
            "english_description": entry.english_description,
            "turkish_description": entry.turkish_description,
            "guidance_en": entry.guidance_en,
            "guidance_tr": entry.guidance_tr,
            "source_condition": entry.source_condition,
        }
        for entry in get_security_error_catalog()
    ]


# Turkish translations for the pinned artifact-rule catalog. Keeping these beside
# the normalization logic makes the Excel export and future UI copy use one
# source of truth without changing the third-party package.
ARTIFACT_RULE_TURKISH = {
    "S101": "os modülü üzerinden işletim sistemi komutu çalıştırılıyor.",
    "S102": "sys modülü üzerinden sistem üzerinde değişiklik yapılabiliyor.",
    "S103": "subprocess modülü üzerinden süreç başlatılabiliyor.",
    "S104": "eval veya exec üzerinden dinamik kod çalıştırılıyor.",
    "S105": "Çalışma zamanında kod derleniyor.",
    "S106": "Dinamik modül içe aktarma için __import__ kullanılıyor.",
    "S107": "importlib üzerinden dinamik içe aktarma mekanizması kullanılıyor.",
    "S108": "Python modülleri betik olarak çalıştırılıyor.",
    "S109": "Programatik olarak web tarayıcısı açılıyor.",
    "S110": "ctypes üzerinden yabancı işlev arayüzü kullanılıyor.",
    "S115": "Kod çalıştırmayı mümkün kılabilecek tehlikeli yerleşiklere erişiliyor.",
    "S201": "Pickle REDUCE opcode'u üzerinden keyfi çağrılabilir kod çalıştırılabiliyor.",
    "S202": "Pickle INST opcode'u üzerinden sınıf örneği oluşturulabiliyor.",
    "S203": "Pickle OBJ opcode'u üzerinden nesne oluşturulabiliyor.",
    "S204": "Pickle NEWOBJ opcode'u üzerinden yeni tip sınıf oluşturulabiliyor.",
    "S205": "Pickle üzerinden yığın tabanlı global ad çözümleme yapılıyor.",
    "S206": "Pickle üzerinden global ad çözümleme yapılıyor.",
    "S207": "Pickle üzerinden nesne oluşturma işlemleri yapılıyor.",
    "S208": "Pickle SETATTR opcode'u üzerinden öznitelik atanıyor.",
    "S209": "Pickle üzerinden öğe atama işlemi yapılıyor.",
    "S210": "Pickle üzerinden birden fazla öğe atanıyor.",
    "S211": "Pickle EXT opcode'u üzerinden copyreg uzantı referansı kullanılıyor.",
    "S212": "Pickle persistent_load geri çağrısı üzerinden kalıcı nesne çözümleme yapılıyor.",
    "S213": "İç içe veya kodlanmış pickle yükü tespit edildi.",
    "S214": "Pickle grafiğinde aşırı bellek veya CPU tüketebilecek genişleme deseni tespit edildi.",
    "S301": "socket modülü üzerinden düşük seviyeli ağ işlemi yapılıyor.",
    "S302": "HTTP istemcisi işlemleri tespit edildi.",
    "S303": "HTTP protokolü işleme işlemi tespit edildi.",
    "S304": "FTP işlemleri tespit edildi.",
    "S305": "Telnet protokolü kullanımı tespit edildi.",
    "S306": "E-posta gönderme yeteneği tespit edildi.",
    "S307": "Alan adı çözümleme işlemi tespit edildi.",
    "S308": "Sabit IP adresleri bulundu.",
    "S309": "Sabit URL'ler bulundu.",
    "S310": "Olası veri hırsızlığı desenleri tespit edildi.",
    "S401": "Dosyaya yazma işlemleri tespit edildi.",
    "S402": "Yol tabanlı dosya yazma işlemleri tespit edildi.",
    "S403": "shutil üzerinden dosya veya dizin işlemleri yapılıyor.",
    "S404": "Geçici dosya oluşturma işlemi tespit edildi.",
    "S405": "Dizin sınırlarından kaçma girişimi tespit edildi.",
    "S406": "Kapsam dışına işaret eden sembolik veya sabit arşiv bağlantısı tespit edildi.",
    "S407": "Gizli dosya işlemleri tespit edildi.",
    "S408": "Sistem yapılandırma dosyalarına erişim tespit edildi.",
    "S409": "Kullanıcı dizini işlemleri tespit edildi.",
    "S410": "Aşırı sıkıştırma oranına sahip arşiv tespit edildi.",
    "S501": "Gömülü Windows ikili dosyası tespit edildi.",
    "S502": "Gömülü Linux ikili dosyası tespit edildi.",
    "S503": "Gömülü macOS ikili dosyası tespit edildi.",
    "S504": "Gömülü kabuk betiği tespit edildi.",
    "S505": "Gömülü Windows toplu iş betiği tespit edildi.",
    "S506": "Gömülü PowerShell kodu tespit edildi.",
    "S507": "Dize verisi olarak gömülü Python kodu tespit edildi.",
    "S508": "Gömülü JavaScript kodu tespit edildi.",
    "S509": "Gömülü WASM ikili dosyası tespit edildi.",
    "S510": "JIT derlenmiş kod tespit edildi.",
    "S601": "Base64 ile kodlanmış veri tespit edildi.",
    "S602": "Onaltılık biçimde kodlanmış veri tespit edildi.",
    "S603": "Sıkıştırılmış içerik tespit edildi.",
    "S604": "Şifrelenmiş veya gizlenmiş yük tespit edildi.",
    "S605": "Unicode gizleme yöntemi tespit edildi.",
    "S606": "Basit bir şifreleme yöntemi tespit edildi.",
    "S607": "XOR ile şifrelenmiş veri tespit edildi.",
    "S609": "Yükü gizlemek için URL kodlaması kullanılıyor.",
    "S610": "Yükü gizlemek için özel veya bilinmeyen kodlama kullanılıyor.",
    "S701": "API anahtarı tespit edildi.",
    "S702": "Parola veya kimlik bilgisi tespit edildi.",
    "S703": "Özel kriptografik anahtar tespit edildi.",
    "S704": "AWS erişim anahtarları tespit edildi.",
    "S705": "Bulut sağlayıcısı kimlik bilgileri tespit edildi.",
    "S706": "Veritabanı bağlantı URL'si tespit edildi.",
    "S707": "JSON Web Token tespit edildi.",
    "S708": "OAuth belirteci tespit edildi.",
    "S709": "Webhook uç noktası tespit edildi.",
    "S710": "Rastgele görünümlü yüksek entropili dize tespit edildi.",
    "S801": "Ağırlıklarda istatistiksel anormallikler tespit edildi.",
    "S802": "Aşırı ağırlık değerlerine sahip nöronlar tespit edildi.",
    "S803": "Tutarsız ağırlık desenleri tespit edildi.",
    "S804": "Olağandışı büyük katman boyutları tespit edildi.",
    "S805": "Standart dışı model mimarisi tespit edildi.",
    "S806": "Belgelendirilmemiş katmanlar bulundu.",
    "S807": "Olası arka kapı tespit edildi.",
    "S808": "Değiştirilmiş ağırlık belirtileri tespit edildi.",
    "S809": "Özel aktivasyon işlevleri tespit edildi.",
    "S810": "Çalıştırılabilir kod içeren katmanlar tespit edildi.",
    "S901": "Dosya uzantısı ile içerik arasında uyuşmazlık var.",
    "S902": "Geçersiz dosya biçimi tespit edildi.",
    "S903": "Yanlış dosya imzası tespit edildi.",
    "S904": "Dosya boyut sınırlarını aşıyor.",
    "S905": "Olağandışı dosya üst verisi tespit edildi.",
    "S906": "Yaygın olmayan dosya uzantısı tespit edildi.",
    "S907": "Birden fazla dosya biçimi göstergesi bulundu.",
    "S908": "Birden fazla biçimde geçerli olan polyglot dosya tespit edildi.",
    "S999": "Tarayıcı beklenmeyen bir ikili ayrıştırma hatasıyla karşılaştı.",
    "S1001": "Bilinen kötü amaçlı model adı tespit edildi.",
    "S1002": "Dosya kötü amaçlı yazılım imzasıyla eşleşiyor.",
    "S1003": "Popüler bir modele benzeyen ad tespit edildi.",
    "S1004": "Modelde dijital imza bulunmuyor.",
    "S1005": "Dijital imza doğrulaması başarısız oldu.",
    "S1006": "İmzalama sertifikasının süresi dolmuş.",
    "S1007": "Model bilinmeyen bir kaynaktan geliyor.",
    "S1008": "Lisans çakışması tespit edildi.",
    "S1009": "Ticari bağlamda GPL lisansı kullanılıyor.",
    "S1010": "Kaynak izleme bilgisi bulunmuyor.",
    "S1101": "weights_only=True kullanılmadan torch.load çağrılıyor.",
    "S1102": "TensorFlow SavedModel güvenlik riski içeriyor.",
    "S1103": "Kod içeren Keras Lambda katmanları tespit edildi.",
    "S1104": "ONNX sürüm uyumluluğu sorunu tespit edildi.",
    "S1105": "JAX JIT derlemesi güvenlik riski taşıyor.",
    "S1106": "MXNet özel operatörleri güvenlik riski taşıyor.",
    "S1107": "PaddlePaddle dinamik grafik modu güvenlik riski taşıyor.",
    "S1108": "CoreML özel katmanları güvenlik riski taşıyor.",
    "S1109": "TensorRT eklentisi güvenlik riski taşıyor.",
    "S1110": "GGUF/GGML biçimi güvenlik riski taşıyor.",
    "S1111": "ONNX modeli harici bir özel operatör uygulamasına bağlı olabilir.",
}


__all__ = [
    "SecurityErrorDefinition",
    "catalog_as_rows",
    "enrich_security_finding",
    "find_security_error",
    "get_security_error_catalog",
    "infer_serialization_source_code",
    "risk_prefix",
]
