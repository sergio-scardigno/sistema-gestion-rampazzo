"""
Deteccion de duplicados por CUIL, nombre similar e ID carpeta.
"""
from collections import defaultdict

try:
    from Levenshtein import ratio as lev_ratio
except ImportError:
    def lev_ratio(a, b):
        """Fallback simple de similitud."""
        if not a or not b:
            return 0.0
        shorter = min(len(a), len(b))
        matches = sum(1 for x, y in zip(a, b) if x == y)
        return matches / max(len(a), len(b))


def find_duplicates(records: list[dict], threshold: float = 0.85) -> list[dict]:
    """
    Encontrar posibles duplicados entre registros normalizados.
    Returns lista de grupos de duplicados con info para el usuario.
    """
    # Index by CUIL
    by_cuil = defaultdict(list)
    by_carpeta = defaultdict(list)
    by_name = []

    for i, rec in enumerate(records):
        cuil = str(rec.get("cuil", "")).strip()
        if cuil and len(cuil) >= 7:
            by_cuil[cuil].append(i)

        carpeta = str(rec.get("id_carpeta", "")).strip()
        if carpeta and carpeta != "None":
            by_carpeta[carpeta].append(i)

        nombre = str(rec.get("nombre_completo", "")).strip().upper()
        if nombre:
            by_name.append((i, nombre))

    duplicates = []
    seen_pairs = set()

    # 1. Exact CUIL matches
    for cuil, indices in by_cuil.items():
        if len(indices) > 1:
            for j in range(1, len(indices)):
                pair = (min(indices[0], indices[j]), max(indices[0], indices[j]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    duplicates.append({
                        "type": "CUIL exacto",
                        "cuil": cuil,
                        "record_a_idx": indices[0],
                        "record_b_idx": indices[j],
                        "record_a": records[indices[0]],
                        "record_b": records[indices[j]],
                        "confidence": 1.0,
                    })

    # 2. Same carpeta ID across sheets
    for carpeta, indices in by_carpeta.items():
        if len(indices) > 1:
            # Only flag if different sheets
            sheets = set(records[i].get("_source_sheet", "") for i in indices)
            if len(sheets) > 1:
                for j in range(1, len(indices)):
                    pair = (min(indices[0], indices[j]), max(indices[0], indices[j]))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        duplicates.append({
                            "type": "ID Carpeta",
                            "carpeta": carpeta,
                            "record_a_idx": indices[0],
                            "record_b_idx": indices[j],
                            "record_a": records[indices[0]],
                            "record_b": records[indices[j]],
                            "confidence": 0.95,
                        })

    # 3. Similar names (only check within reasonable limits to avoid O(n^2) for large datasets)
    max_name_checks = min(len(by_name), 2000)
    for i in range(max_name_checks):
        for j in range(i + 1, max_name_checks):
            idx_a, name_a = by_name[i]
            idx_b, name_b = by_name[j]
            pair = (min(idx_a, idx_b), max(idx_a, idx_b))
            if pair in seen_pairs:
                continue

            similarity = lev_ratio(name_a, name_b)
            if similarity >= threshold and name_a != name_b:
                seen_pairs.add(pair)
                duplicates.append({
                    "type": "Nombre similar",
                    "similarity": round(similarity, 2),
                    "record_a_idx": idx_a,
                    "record_b_idx": idx_b,
                    "record_a": records[idx_a],
                    "record_b": records[idx_b],
                    "confidence": similarity,
                })

    # Sort by confidence descending
    duplicates.sort(key=lambda d: d["confidence"], reverse=True)
    return duplicates
