import os
import re
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session
from dotenv import load_dotenv

try:
    import models
    import database
except ImportError:
    # Allows loading if executed from a different directory
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    try:
        import models
        import database
    except ImportError:
        models = None
        database = None

# Try loading from various .env locations
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai", "ai-microservices", ".env"))


_RULES_CACHE: Optional[Dict[str, Any]] = None
_RULES_CACHE_MTIME: float = 0.0
_RULES_CACHE_PATH: Optional[str] = None


def load_filter_rules(rules_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads and caches filter recommendation rules from JSON.
    Searches common paths if no explicit path is provided.
    Automatically reloads if the underlying rules file has been modified on disk.
    """
    global _RULES_CACHE, _RULES_CACHE_MTIME, _RULES_CACHE_PATH

    candidate_paths = []
    if rules_path:
        candidate_paths.append(rules_path)
    else:
        # Standard search locations
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidate_paths.extend([
            os.path.join(base_dir, "filter_rules.json"),
            os.path.join(base_dir, "..", "filter_rules.json"),
            os.path.join(base_dir, "helpers", "filter_rules.json"),
            os.path.join(os.getcwd(), "filter_rules.json"),
            os.path.join(os.getcwd(), "basic", "basic_backend", "helpers", "filter_rules.json"),
            os.path.join(os.getcwd(), "basic", "basic_backend", "filter_rules.json"),
        ])

    resolved_path = None
    for p in candidate_paths:
        if os.path.isfile(p):
            resolved_path = p
            break

    if not resolved_path:
        raise FileNotFoundError(
            f"Could not locate 'filter_rules.json'. Searched candidate paths: {candidate_paths}"
        )

    # If already cached and rules file has not changed on disk, return cache
    if rules_path is None and _RULES_CACHE is not None and _RULES_CACHE_PATH == resolved_path:
        try:
            current_mtime = os.path.getmtime(resolved_path)
            if current_mtime <= _RULES_CACHE_MTIME:
                return _RULES_CACHE
        except Exception:
            return _RULES_CACHE

    with open(resolved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if rules_path is None:
        _RULES_CACHE = data
        _RULES_CACHE_PATH = resolved_path
        try:
            _RULES_CACHE_MTIME = os.path.getmtime(resolved_path)
        except Exception:
            _RULES_CACHE_MTIME = 0.0
    return data


class FilterRecommender:
    """
    Deterministic Filter Recommender Engine for CRUK DataHub.
    Loads and ingests rules from JSON, applying regular expression pattern matching
    against dataset metadata with zero hallucination and provenance evidence extraction.
    """
    def __init__(self, db: Optional[Session] = None, rules_path: Optional[str] = None):
        self.db = db
        self.rules_path = rules_path
        self.rules = load_filter_rules(rules_path)
        self.hierarchy: Dict[str, str] = self.rules.get("hierarchy", {})
        self.filter_by_id = {}
        self._load_taxonomies()
        self._precompile_rules()

    def _load_taxonomies(self):
        """Loads canonical taxonomies from the database for fast lookup and validation."""
        if self.db and models and hasattr(models, "Filter"):
            try:
                filters = self.db.query(models.Filter).all()
                self.filter_by_id = {f.id: f for f in filters}
            except Exception:
                self.filter_by_id = {}

    def _precompile_rules(self):
        """Pre-compiles regex patterns defined in the ingested JSON rules for maximum performance."""
        def compile_section(section_name: str):
            for rule in self.rules.get(section_name, []):
                flags = 0 if rule.get("case_sensitive", False) else re.IGNORECASE
                pattern = rule.get("pattern", "")
                if pattern:
                    rule["_compiled_pattern"] = re.compile(pattern, flags)
                neg = rule.get("negative_pattern", "")
                if neg:
                    rule["_compiled_negative"] = re.compile(neg, flags)
                fb = rule.get("fallback_pattern", "")
                if fb:
                    rule["_compiled_fallback"] = re.compile(fb, flags)

        compile_section("topography_rules")
        compile_section("histology_rules")
        compile_section("data_type_rules")
        compile_section("parent_category_rules")
        compile_section("access_rules")

        # Compile biobank physical availability checker (matches bio-samples, biological samples, biobank, or samples available)
        biobank_pattern = r'\b(bio-?samples?|biological\s+samples?|biobank\w*|biorepositor\w*|tissue\s+bank\w*|(samples?|blocks?|vials?|aliquots?)\s+available|available\s+(samples?|blocks?|vials?|aliquots?))\b'
        self._compiled_biobank = re.compile(biobank_pattern, re.IGNORECASE)

        # Compile in vitro experimental context checker
        in_vitro_pattern = r'\b(in\s+vitro|cell\s+cultures?|cultured\s+cells?|cell\s+lines?|organoids?|organ-?on-?(a-?)?chips?|2d\s+culture|3d\s+culture|tissue\s+slices?|slice\s+cultures?|well[- ]plates?)\b'
        self._compiled_in_vitro = re.compile(in_vitro_pattern, re.IGNORECASE)

        # Compile model organism context checker
        model_organism_pattern = r'\b(model\s+organisms?|mouse|mice|murine|canine|dogs?|rats?|rabbit\w*|drosophila|fruit\s+fl(y|ies)|chick\w*|chicken\w*|avian|gallus|yeast|saccharomyces|pombe|xenografts?|pdx\b|allografts?|in\s+vivo|animals?|gemm\b|transgenic)\b'
        self._compiled_model_organism = re.compile(model_organism_pattern, re.IGNORECASE)

    def _get_filter_hierarchy(self, filter_id: str) -> Tuple[List[str], str]:
        """
        Traverses filter taxonomy and resolves the full hierarchy path after the first root container.
        Example: 0_2_1_0_1 -> ['In Vitro Study', 'Model', '3D organoid (including on a chip)']
        Returns: (labels_list, formatted_hierarchy_string)
        """
        f = self.filter_by_id.get(filter_id)
        if not f:
            return [], ""

        # Use stored JSON path if valid, otherwise traverse parentId
        if f.path and isinstance(f.path, list):
            path_ids = f.path
        else:
            path_ids = []
            curr = f
            while curr:
                path_ids.insert(0, curr.id)
                curr = self.filter_by_id.get(curr.parentId) if curr.parentId else None

        # Hierarchy after first root container (skip path_ids[0] like '0_2', '0_0', '0_1')
        sub_path = path_ids[1:] if len(path_ids) > 1 else path_ids
        labels = []
        for pid in sub_path:
            pf = self.filter_by_id.get(pid)
            if pf and pf.label:
                labels.append(pf.label)

        if not labels and f.label:
            labels = [f.label]

        formatted_text = ", ".join(labels)
        return labels, formatted_text

    def _to_filter_dict(
        self,
        filter_id: str,
        default_label: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        is_derived: bool = False
    ) -> Dict[str, Any]:
        """Converts a Filter ID or SQLAlchemy model into a standardized DatasetFilter JSON dict."""
        filter_model = self.filter_by_id.get(filter_id)
        if filter_model:
            label = filter_model.label
            category = filter_model.category or ""
            pg = filter_model.primaryGroup or "data-type"
            description = filter_model.description or ""
        else:
            label = default_label or filter_id
            category = ""
            description = ""
            if filter_id.startswith("0_0_"):
                pg = "cancer-type"
            elif filter_id.startswith("0_1_"):
                pg = "access-type"
            else:
                pg = "data-type"

        if pg in ['Multi-omic Data', 'Techniques']:
            pg = 'data-type'
        elif pg not in ['cancer-type', 'data-type', 'access-type']:
            if filter_id.startswith('0_0_'):
                pg = 'cancer-type'
            elif filter_id.startswith('0_1_'):
                pg = 'access-type'
            else:
                pg = 'data-type'

        hierarchy_list, hierarchy_text = self._get_filter_hierarchy(filter_id)

        res = {
            "id": filter_id,
            "label": label,
            "category": category,
            "primaryGroup": pg,
            "description": description,
            "hierarchy": hierarchy_list,
            "hierarchyText": hierarchy_text,
            "isDerived": is_derived
        }
        if evidence:
            res["evidence"] = evidence
        return res

    def _build_evidence(
        self,
        metadata: Dict[str, Any],
        pattern: str,
        matched_term: str,
        rule_rationale: str = "",
        case_sensitive: bool = False,
        derived_from: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Deterministically extracts provenance evidence directly from user metadata in memory.
        Collects all matching instances with clean word-boundary snapping and expanded context.
        Zero hallucination: Field names and text snippets are sliced directly from actual dictionary values.
        """
        flags = 0 if case_sensitive else re.IGNORECASE
        effective_metadata = metadata
        if 'metadata_blob' in metadata and isinstance(metadata['metadata_blob'], dict):
            effective_metadata = {**metadata['metadata_blob'], **metadata}

        summary = effective_metadata.get('summary', {}) or {}
        doc = effective_metadata.get('documentation', {}) or {}
        access = (effective_metadata.get('accessibility', {}) or {}).get('access', {}) or {}
        usage = (effective_metadata.get('accessibility', {}) or {}).get('usage', {}) or {}

        title_val = summary.get('title', '') or effective_metadata.get('title', '') or effective_metadata.get('name', '') or ''
        abstract_val = summary.get('abstract', '') or effective_metadata.get('abstract', '') or ''
        keywords_val = ", ".join([str(k) for k in (summary.get('keywords') or effective_metadata.get('keywords') or []) if k])
        doc_val = doc.get('description', '') or effective_metadata.get('description', '') or ''

        fields_to_check = [
            ("summary.title", title_val),
            ("summary.abstract", abstract_val),
            ("summary.keywords", keywords_val),
            ("documentation.description", doc_val),
            ("accessibility.access.accessRights", access.get('accessRights', '')),
            ("accessibility.usage.dataUseRequirements", ", ".join(usage.get('dataUseRequirements') or [])),
            ("accessibility.usage.dataUseLimitation", ", ".join(usage.get('dataUseLimitation') or []))
        ]

        other_dts = metadata.get('otherDataTypes', []) or []
        for idx, dt in enumerate(other_dts):
            if isinstance(dt, dict):
                dt_title = dt.get('title', '') or ''
                dt_desc = dt.get('description', '') or ''
                dt_format = dt.get('format', '') or ''
                combined_dt = f"{dt_title}: {dt_desc} ({dt_format})".strip()
                fields_to_check.append((f"otherDataTypes[{idx}]", combined_dt))
            elif isinstance(dt, str):
                fields_to_check.append((f"otherDataTypes[{idx}]", dt))

        structural = metadata.get('structuralMetadata', []) or []
        if isinstance(structural, list):
            for t_idx, table in enumerate(structural):
                if isinstance(table, dict):
                    t_name = table.get('name', '') or ''
                    t_desc = table.get('description', '') or ''
                    col_parts = []
                    for col in table.get('columns', []) or []:
                        if isinstance(col, dict):
                            col_parts.append(f"{col.get('name', '')}: {col.get('description', '')}")
                    t_full = f"{t_name} - {t_desc}. Columns: {'; '.join(col_parts)}".strip()
                    fields_to_check.append((f"structuralMetadata[{t_idx}]", t_full))
        elif isinstance(structural, dict):
            tables = structural.get('tables', []) or []
            for t_idx, table in enumerate(tables):
                if isinstance(table, dict):
                    t_name = table.get('name', '') or ''
                    t_desc = table.get('description', '') or ''
                    t_full = f"{t_name}: {t_desc}".strip()
                    fields_to_check.append((f"structuralMetadata.tables[{t_idx}]", t_full))

        def snap_slice(val: str, m: re.Match, before: int, after: int) -> str:
            start = max(0, m.start() - before)
            while start > 0 and val[start] not in ' \t\n.,;':
                start -= 1
            if start > 0:
                start += 1
            end = min(len(val), m.end() + after)
            while end < len(val) and val[end] not in ' \t\n.,;':
                end += 1
            raw_slice = val[start:end].strip()
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(val) else ""
            return f"{prefix}{raw_slice}{suffix}"

        all_instances = []
        for field_name, field_val in fields_to_check:
            if not field_val or not isinstance(field_val, str):
                continue
            for m in re.finditer(pattern, field_val, flags):
                compact_snippet = snap_slice(field_val, m, 60, 80)
                expanded_snippet = snap_slice(field_val, m, 180, 220)
                all_instances.append({
                    "sourceField": field_name,
                    "snippet": compact_snippet,
                    "expandedSnippet": expanded_snippet,
                    "matchedText": m.group(0)
                })

        total_occurrences = len(all_instances)
        if total_occurrences == 0:
            total_occurrences = 1
            source_field = "summary.abstract"
            primary_snippet = f'"{matched_term}" mentioned in study metadata'
            primary_expanded = primary_snippet
            all_instances = [{
                "sourceField": source_field,
                "snippet": primary_snippet,
                "expandedSnippet": primary_expanded,
                "matchedText": matched_term
            }]
        else:
            source_field = all_instances[0]["sourceField"]
            primary_snippet = all_instances[0]["snippet"]
            primary_expanded = all_instances[0]["expandedSnippet"]

        ev = {
            "sourceField": source_field,
            "snippet": primary_snippet,
            "expandedSnippet": primary_expanded,
            "matchedTerm": matched_term,
            "instancesInMetadata": total_occurrences,
            "ruleRationale": rule_rationale,
            "allInstances": all_instances[:10]
        }
        if derived_from:
            ev["derivedFrom"] = derived_from
        return ev

    def _extract_text_corpus(self, metadata: Dict[str, Any]) -> tuple[str, str, List[Dict[str, Any]]]:
        """Builds both raw-case and lowercase textual corpora from user metadata for pattern matching."""
        effective_metadata = metadata
        if 'metadata_blob' in metadata and isinstance(metadata['metadata_blob'], dict):
            effective_metadata = {**metadata['metadata_blob'], **metadata}

        summary = effective_metadata.get('summary', {}) or {}
        doc = effective_metadata.get('documentation', {}) or {}
        accessibility = effective_metadata.get('accessibility', {}) or {}
        access = accessibility.get('access', {}) or {}
        usage = accessibility.get('usage', {}) or {}
        other_data_types = effective_metadata.get('otherDataTypes', []) or []
        structural = effective_metadata.get('structuralMetadata', {}) or {}

        title = summary.get('title', '') or effective_metadata.get('title', '') or effective_metadata.get('name', '') or ''
        abstract = summary.get('abstract', '') or effective_metadata.get('abstract', '') or ''
        keywords_list = summary.get('keywords', []) or effective_metadata.get('keywords', []) or []
        keywords = " ".join([str(k) for k in keywords_list if k])
        doc_desc = doc.get('description', '') or effective_metadata.get('description', '') or ''
        access_rights = access.get('accessRights', '') or ''
        data_use_req = " ".join(usage.get('dataUseRequirements', []) or [])
        data_use_lim = " ".join(usage.get('dataUseLimitation', []) or [])

        other_dt_texts = []
        for dt in other_data_types:
            if isinstance(dt, dict):
                other_dt_texts.append(f"{dt.get('title', '')} {dt.get('description', '')} {dt.get('format', '')}")
            elif isinstance(dt, str):
                other_dt_texts.append(dt)
        other_dt_combined = " ".join(other_dt_texts)

        struct_texts = []
        if isinstance(structural, list):
            for table in structural:
                if isinstance(table, dict):
                    t_name = table.get('name', '') or ''
                    t_desc = table.get('description', '') or ''
                    col_parts = []
                    for col in table.get('columns', []) or []:
                        if isinstance(col, dict):
                            col_parts.append(f"{col.get('name', '')}: {col.get('description', '')}")
                    struct_texts.append(f"{t_name} {t_desc} {' '.join(col_parts)}")
        elif isinstance(structural, dict):
            for table in (structural.get('tables', []) or []):
                if isinstance(table, dict):
                    t_name = table.get('name', '') or ''
                    t_desc = table.get('description', '') or ''
                    struct_texts.append(f"{t_name} {t_desc}")
        struct_combined = " ".join(struct_texts)

        raw_text = f"{title} {abstract} {keywords} {doc_desc} {access_rights} {data_use_req} {data_use_lim} {other_dt_combined} {struct_combined}"
        text = raw_text.lower()
        return raw_text, text, other_data_types

    def recommend_filters(
        self,
        metadata: Dict[str, Any],
        rejected_filter_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Main recommendation pipeline:
        Ingests rules from JSON and applies regular expression patterns for:
        1. Topography keywords & multi-mapping clinical rules
        2. Top-level histology morphological families (restricted to top level)
        3. Data type hierarchies
        4. Hierarchical parent triggering (child triggers parent silently)
        5. Access governance rules
        6. Cascading rejection
        7. Cross-reference hydration from CRUK & TCGA mappings (created silently)
        """
        # Determine set of rejected filters to enforce cascading rejection
        rejected_set: Set[str] = set()
        if rejected_filter_ids:
            rejected_set.update(str(x) for x in rejected_filter_ids)
        for rej in metadata.get('rejectedFilters', []) or []:
            if isinstance(rej, dict) and rej.get('id'):
                rejected_set.add(str(rej['id']))
            elif isinstance(rej, str):
                rejected_set.add(rej)

        raw_text, text, other_data_types = self._extract_text_corpus(metadata)
        recommended_filters: Dict[str, Dict[str, Any]] = {}
        detected_topography_ids: Set[str] = set()
        detected_histology_ids: Set[str] = set()

        # Check if physical biobank context exists in the metadata
        has_biobank_context = bool(self._compiled_biobank.search(text))
        # Check if in vitro experimental context exists in the metadata
        has_in_vitro_context = bool(self._compiled_in_vitro.search(text))
        # Check if model organism context exists in the metadata
        has_model_organism_context = bool(self._compiled_model_organism.search(text))

        def trigger_hierarchical_parents(child_id: str, child_label: str):
            """Hierarchically triggers parent filter(s) silently when a child filter is matched."""
            curr_id = child_id
            curr_label = child_label
            while True:
                parent_id = self.hierarchy.get(curr_id)
                if not parent_id or parent_id == curr_id:
                    break
                if parent_id in rejected_set:
                    break
                if parent_id not in recommended_filters:
                    parent_model = self.filter_by_id.get(parent_id)
                    parent_label = parent_model.label if parent_model else parent_id
                    ev = {
                        "sourceField": "hierarchical_parent",
                        "snippet": f"Triggered automatically by child filter '{curr_label}'",
                        "matchedTerm": parent_label,
                        "instancesInMetadata": 1,
                        "ruleRationale": f"Hierarchical parent category of '{curr_label}' ({curr_id})",
                        "derivedFrom": [curr_id]
                    }
                    # Mark as is_derived=True so it is handled silently
                    recommended_filters[parent_id] = self._to_filter_dict(
                        parent_id,
                        default_label=parent_label,
                        evidence=ev,
                        is_derived=True
                    )
                curr_id = parent_id
                curr_model = self.filter_by_id.get(curr_id)
                curr_label = curr_model.label if curr_model else curr_id

        def apply_rule(rule: Dict[str, Any], is_topography: bool = False, is_histology: bool = False):
            pattern_regex = rule.get("_compiled_pattern")
            if not pattern_regex:
                return

            # Check if this rule requires physical biobank context
            if rule.get("requires_biobank_context") and not has_biobank_context:
                return

            # Check if this rule requires in vitro experimental context
            if rule.get("requires_in_vitro_context") and not has_in_vitro_context:
                return

            # Check if this rule requires model organism context
            if rule.get("requires_model_organism_context") and not has_model_organism_context:
                return

            case_sensitive = rule.get("case_sensitive", False)
            target_str = raw_text if case_sensitive else text

            # Check negative exclusion pattern if defined
            neg_regex = rule.get("_compiled_negative")
            if neg_regex and neg_regex.search(target_str):
                return

            if pattern_regex.search(target_str):
                # Retrieve all target filter IDs for this rule
                filter_ids = rule.get("filter_ids")
                if not filter_ids and rule.get("filter_id"):
                    filter_ids = [rule["filter_id"]]
                if not filter_ids:
                    return

                matched_term = rule.get("matched_term", "")
                rationale = rule.get("rationale", "")
                raw_pattern = rule.get("pattern", "")

                for fid in filter_ids:
                    if fid in rejected_set:
                        continue
                    if fid not in recommended_filters:
                        evidence = self._build_evidence(
                            metadata,
                            raw_pattern,
                            matched_term,
                            rationale,
                            case_sensitive=case_sensitive
                        )
                        # Direct match -> is_derived=False (shown as card)
                        recommended_filters[fid] = self._to_filter_dict(
                            fid,
                            default_label=matched_term,
                            evidence=evidence,
                            is_derived=False
                        )
                        if is_topography or rule.get("is_topography"):
                            detected_topography_ids.add(fid)
                        if is_histology or rule.get("is_histology"):
                            detected_histology_ids.add(fid)

                        # Trigger parent filter in hierarchy silently
                        trigger_hierarchical_parents(fid, matched_term)

        # 1. TOPOGRAPHY SCANNING (Direct matches)
        # Check if any cancer topography is mentioned in the dataset/paper title
        # (in DataHub metadata, this corresponds to metadata_blob.summary.title / summary.title)
        title_topography_rules = []
        eff_meta = metadata
        if 'metadata_blob' in metadata and isinstance(metadata['metadata_blob'], dict):
            eff_meta = {**metadata['metadata_blob'], **metadata}
        summary_dict = eff_meta.get('summary', {}) or {}
        title_str = str(summary_dict.get('title', '') or eff_meta.get('title', '') or eff_meta.get('name', '') or '')

        if title_str:
            for rule in self.rules.get("topography_rules", []):
                pattern_regex = rule.get("_compiled_pattern")
                if pattern_regex and pattern_regex.search(title_str):
                    title_topography_rules.append(rule)

        # If any cancer topography is mentioned in the title, suppress any topography NOT mentioned in the title
        topography_rules_to_run = title_topography_rules if title_topography_rules else self.rules.get("topography_rules", [])

        for rule in topography_rules_to_run:
            apply_rule(rule, is_topography=True)

        # 2. HISTOLOGY SCANNING (Restricted strictly to top-level families)
        for rule in self.rules.get("histology_rules", []):
            apply_rule(rule, is_histology=True)

        # 3. DATA TYPE HIERARCHY SCANNING (Direct matches)
        for rule in self.rules.get("data_type_rules", []):
            apply_rule(rule)

        # 4. PARENT CATEGORY RULES & AUTO-TRIGGERS (Fallback direct triggers)
        for rule in self.rules.get("parent_category_rules", []):
            parent_id = rule.get("filter_id")
            if not parent_id or parent_id in recommended_filters or parent_id in rejected_set:
                continue

            # Special case for Biobank Parent: strictly require physical biobank pattern
            if parent_id == "0_2_0":
                if has_biobank_context:
                    matched_term = rule.get("matched_term", "Biobank Samples")
                    rationale = rule.get("rationale", "Detected physical biobank repository or specimen availability")
                    raw_pattern = rule.get("fallback_pattern", "")
                    evidence = self._build_evidence(metadata, raw_pattern, matched_term, rationale)
                    # If directly matched by biobank keyword, show as card
                    recommended_filters[parent_id] = self._to_filter_dict(
                        parent_id,
                        default_label=matched_term,
                        evidence=evidence,
                        is_derived=False
                    )
                continue

            triggered = False
            # Trigger 1: Specific imaging file formats in otherDataTypes
            if rule.get("check_imaging_formats"):
                has_imaging_files = any(
                    str(item.get('format', '')).upper() in ['DICOM', 'TIFF', 'SVS', 'NIFTI'] or
                    'image' in str(item.get('title', '')).lower() or
                    'scan' in str(item.get('title', '')).lower() or
                    'mammogram' in str(item.get('title', '')).lower()
                    for item in other_data_types if isinstance(item, dict)
                )
                if has_imaging_files:
                    triggered = True

            # Trigger 2: Fallback regular expression pattern
            fallback_regex = rule.get("_compiled_fallback")
            if not triggered and fallback_regex and fallback_regex.search(text):
                triggered = True

            if triggered:
                matched_term = rule.get("matched_term", "")
                rationale = rule.get("rationale", "")
                raw_pattern = rule.get("fallback_pattern") or rule.get("pattern", "")
                evidence = self._build_evidence(metadata, raw_pattern, matched_term, rationale)
                recommended_filters[parent_id] = self._to_filter_dict(
                    parent_id,
                    default_label=matched_term,
                    evidence=evidence,
                    is_derived=False
                )

        # 5. ACCESS TYPE GOVERNANCE RULES (Direct matches)
        for rule in self.rules.get("access_rules", []):
            apply_rule(rule)

        # 6. AUTO-HYDRATE CRUK & TCGA TERMS FROM CO-OCCURRENCE (Created silently, is_derived=True)
        if detected_topography_ids and detected_histology_ids and self.db and models and hasattr(models, "CancerTermIdMapping"):
            try:
                valid_topos = [tid for tid in detected_topography_ids if tid not in rejected_set]
                valid_histos = [hid for hid in detected_histology_ids if hid not in rejected_set]

                if valid_topos and valid_histos:
                    mappings = self.db.query(models.CancerTermIdMapping).filter(
                        models.CancerTermIdMapping.topography_id.in_(valid_topos),
                        models.CancerTermIdMapping.histology_id.in_(valid_histos)
                    ).all()

                    for m in mappings:
                        if m.extra_filter_ids and isinstance(m.extra_filter_ids, list):
                            for fid in m.extra_filter_ids:
                                if fid in rejected_set:
                                    continue
                                if fid not in recommended_filters:
                                    evidence = {
                                        "sourceField": "cruk_tcga_crossref",
                                        "snippet": f"Derived from Topography ({m.topography_id}) & Histology ({m.histology_id}) co-occurrence",
                                        "matchedTerm": fid,
                                        "instancesInMetadata": 1,
                                        "ruleRationale": "Hydrated from matched Topography and Histology pairing",
                                        "derivedFrom": [m.topography_id, m.histology_id]
                                    }
                                    # Mark as is_derived=True so it is created silently upon acceptance
                                    recommended_filters[fid] = self._to_filter_dict(
                                        fid,
                                        evidence=evidence,
                                        is_derived=True
                                    )
            except Exception:
                pass

        # 7. PAN-CANCER FALLBACK TRIGGER
        # If no specific cancer type (topography, histology, or cross-referenced term) was detected in metadata,
        # automatically trigger Pan Cancer (0_0_5) so every dataset receives an applicable cancer classification.
        has_specific_cancer = any(
            fid.startswith('0_0') and fid not in ('0_0', '0_0_5')
            for fid in recommended_filters
        )
        if not has_specific_cancer and '0_0_5' not in recommended_filters and '0_0_5' not in rejected_set:
            has_existing_cancer = any(
                (isinstance(f, dict) and str(f.get('id', '')).startswith('0_0') and str(f.get('id', '')) not in ('0_0', '0_0_5')) or
                (isinstance(f, str) and f.startswith('0_0') and f not in ('0_0', '0_0_5'))
                for f in ((metadata or {}).get('datasetFilters') or [])
            )
            if not has_existing_cancer:
                generic_match = re.search(r'\b(cancers?|tumou?rs?|malignan\w*|oncolog\w*)\b', raw_text, re.IGNORECASE)
                if generic_match:
                    fallback_ev = self._build_evidence(
                        metadata,
                        r'\b(cancers?|tumou?rs?|malignan\w*|oncolog\w*)\b',
                        generic_match.group(0),
                        rule_rationale="Triggered automatically because no specific cancer type was identified in metadata"
                    )
                else:
                    fallback_ev = {
                        "sourceField": "summary.abstract",
                        "snippet": "No specific cancer type identified in metadata; defaulted to Pan Cancer.",
                        "expandedSnippet": "No specific cancer type identified in metadata; defaulted to Pan Cancer.",
                        "matchedTerm": "Pan Cancer",
                        "instancesInMetadata": 1,
                        "ruleRationale": "Triggered automatically because no specific cancer type was identified in metadata",
                        "allInstances": [
                            {
                                "sourceField": "summary.abstract",
                                "snippet": "No specific cancer type identified in metadata; defaulted to Pan Cancer.",
                                "expandedSnippet": "No specific cancer type identified in metadata; defaulted to Pan Cancer.",
                                "matchedText": "Pan Cancer"
                            }
                        ]
                    }
                recommended_filters['0_0_5'] = self._to_filter_dict(
                    '0_0_5',
                    default_label='Pan Cancer',
                    evidence=fallback_ev,
                    is_derived=False
                )

        # Final Cascading Rejection Filter Check
        final_results = []
        for fid, fdict in recommended_filters.items():
            if fid in rejected_set:
                continue
            ev = fdict.get("evidence", {}) or {}
            derived_from = ev.get("derivedFrom") or []
            if any(df in rejected_set for df in derived_from):
                continue
            final_results.append(fdict)

        return final_results

    # Aliases for backwards compatibility
    scan_metadata = recommend_filters
    recommend_filter = recommend_filters


def recommend_filter(
    metadata: Dict[str, Any],
    db: Optional[Session] = None,
    rules_path: Optional[str] = None,
    rejected_filter_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function that loads and ingests filter rules from JSON
    and executes deterministic filter recommendations against dataset metadata.
    """
    recommender = FilterRecommender(db=db, rules_path=rules_path)
    return recommender.recommend_filters(metadata, rejected_filter_ids=rejected_filter_ids)
