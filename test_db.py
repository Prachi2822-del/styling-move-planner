import tomllib
from supabase import create_client

s = tomllib.load(open(".streamlit/secrets.toml", "rb"))
sb = create_client(s["SUPABASE_URL"], s["SUPABASE_KEY"])

for table in ["projects", "photos", "furniture_items", "required_items"]:
    r = sb.table(table).select("*").limit(1).execute()
    print(table, "OK, rows found:", len(r.data))