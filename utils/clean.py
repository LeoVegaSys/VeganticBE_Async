import json

def clean_sql(query: str) -> str:
    return query.replace("```sql", "").replace("```", "").strip().rstrip(";").strip()

def clean_json(text: str) -> dict:
    # Remove ```json ... ``` or '''json ... ''' fences
    import re
    text = text.strip()
    text = re.sub(r"^\s*(```|''')json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*(```|''')\s*$", "", text)
    return json.loads(text)