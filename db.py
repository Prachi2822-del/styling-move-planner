""" Everything that talks to supabase (database + storage photos)"""
import io
import uuid
import streamlit as st
from PIL import Image, ImageOps
from supabase import create_client

BUCKET = "photos"

@st.cache_resource
def _sb():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


# Projects
def list_projects():
    return _sb().table("projects").select("*").order("created_at", desc = True).execute().data or []

def get_project(pid):
    return _sb().table("projects").select("*").eq("id", pid).single().execute().data

def create_project(fields):
    return _sb().table("projects").insert(fields).execute().data[0]

def update_project(pid, fields):
    return _sb().table("projects").update(fields).eq("id", pid).execute()

def delete_project(pid):
    paths = [p["path"] for p in _sb().table("photos").select("path").eq("project_id", pid).execute().data]
    if paths:
        _sb().storage.from_(BUCKET).remove(paths)
    _sb().table("projects").delete().eq("id", pid).execute()  # photos/items cascade


# Photos
def _shrink(raw, max_side = 1280, quality = 82):
    """ Phone photos are huge. Shrink them faster uploads, cheaper AI cals"""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality)
    return out.getvalue()

def list_photos(pid, room):
    return (_sb().table("photos").select("*").eq("project_id", pid).eq("room", room)
            .order("created_at").execute().data or [])


def add_photo(pid, room, raw):
    path = f"{pid}/{room}/{uuid.uuid4().hex}.jpg"
    _sb().storage.from_(BUCKET).upload(path, _shrink(raw), {"content-type": "image/jpeg"})
    return _sb().table("photos").insert({"project_id": pid, "room": room, "path": path}).execute().data[0]


@st.cache_data(max_entries=300, show_spinner=False)
def photo_bytes(path):
    return _sb().storage.from_(BUCKET).download(path)


def delete_photo(photo):
    _sb().storage.from_(BUCKET).remove([photo["path"]])
    _sb().table("photos").delete().eq("id", photo["id"]).execute()


# Furniture Found at the property
def list_items(pid, room=None):
    q = _sb().table("furniture_items").select("*").eq("project_id", pid)
    if room:
        q = q.eq("room", room)
        return q.order("created_at").execute().data or []

def replace_items(pid, room, raws):
    """ Replace the whole furniture list from one room"""
    _sb().table("furniture_items").delete().eq("project_id", pid).eq("room", room).execute()
    if raws:
        _sb().table("furniture_items").insert(
            [{**r, "project_id": pid, "room": room} for r in raws]
        ).execute()

def room_counts(pid):
    """{'living': {'photos': 3, 'items': 5}, ...} so we can show progress per room."""
    counts = {}
    for table, key in (("photos", "photos"), ("furniture_items", "items")):
        cols = "room, qty" if key == "items" else "room"
        for r in _sb().table(table).select(cols).eq("project_id", pid).execute().data or []:
            c = counts.setdefault(r["room"], {"photos": 0, "items": 0})
            c[key] += r["qty"] if key == "items" else 1
    return counts


# Furniture a property needs 
def get_required(pid):
    return _sb().table("required_items").select("*").eq("project_id", pid).order("item_type").execute().data or []


def set_required(pid, rows):
    merged = {}
    for r in rows:  # same type twice -> add the quantities
        merged[r["item_type"]] = merged.get(r["item_type"], 0) + r["qty"]
    _sb().table("required_items").delete().eq("project_id", pid).execute()
    if merged:
        _sb().table("required_items").insert(
            [{"project_id": pid, "item_type": k, "qty": v} for k, v in merged.items()]
        ).execute()