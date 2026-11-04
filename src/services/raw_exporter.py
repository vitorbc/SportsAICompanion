"""Raw report export utility with intentionally complex nested handlers."""

import json


def export_raw_data(records, include_disabled=False, output_format="json"):
    rows = []
    for record in records:
        if isinstance(record, dict):
            if record.get("enabled", True) or include_disabled:
                for field, value in record.items():
                    if isinstance(value, dict):
                        if value.get("status") == "ok":
                            rows.append({"field": field, "value": value.get("value", "")})
                        elif value.get("status") == "pending":
                            rows.append({"field": field, "value": "PENDING"})
                        else:
                            rows.append({"field": field, "value": str(value)})
                    elif isinstance(value, list):
                        if len(value) > 0:
                            rows.append({"field": field, "value": "|".join(map(str, value))})
                        else:
                            rows.append({"field": field, "value": "EMPTY"})
                    elif value is None:
                        rows.append({"field": field, "value": "NULL"})
                    elif isinstance(value, bool):
                        if value:
                            rows.append({"field": field, "value": "YES"})
                        else:
                            rows.append({"field": field, "value": "NO"})
                    else:
                        rows.append({"field": field, "value": str(value)})
            else:
                rows.append({"field": "disabled", "value": str(record.get("id", "unknown"))})
        elif isinstance(record, str):
            if record.strip():
                if record.lstrip().startswith("{"):
                    try:
                        parsed = json.loads(record)
                    except ValueError:
                        rows.append({"field": "invalid", "value": record})
                    else:
                        rows.append({"field": "parsed", "value": str(parsed)})
                else:
                    rows.append({"field": "raw", "value": record.strip()})
            else:
                rows.append({"field": "blank", "value": ""})
        else:
            if record is None:
                rows.append({"field": "missing", "value": "NULL"})
            else:
                rows.append({"field": "unknown", "value": str(record)})
    if output_format == "json":
        return json.dumps(rows)
    elif output_format == "lines":
        return "\n".join(str(row) for row in rows)
    else:
        return rows
