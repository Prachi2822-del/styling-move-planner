import hmac
from datetime import date
import pandas as pd
import streamlit as st
import ai
import db
from compare import compare, totals
from config import (LABEL_TO_TYPE, MAX_BEDROOMS, MAX_LIVING_AREAS, MAX_PHOTOS_PER_ROOM,
                    STAGES, STYLED_INDEX, TYPES, rooms_for)

st.set_page_config(page_title="Styling Move Planner", layout="centered")

# Login
def gate():
    if st.session_state.get("authed"):
        return
    st.title("Styling Move Planner")
    pw = st.text_input("Team Password", type = "password")
    if pw:
        if hmac.compare_digest(pw, st.secrets["APP_PASSWORD"]):
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Invalid password")
    st.stop()

# Helpers
def to_date(value):
    return date.fromisoformat(value) if value else None

def editor_frame(rows, with_photo = False):
    """Turn database rows into the table shown in the editor (labels, not ids)"""
    cols = ["photo_id", "item_type", "qty", "detail"] if with_photo else ["item_type", "qty"]
    data = [{**{c: r.get(c) for c in cols}, "item_type": TYPES.get(r["item_type"], r["item_type"])} for r in rows]
    df = pd.DataFrame(data, columns=cols)
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    return df

def editor_rows(df, with_photo = False):
    """Turn the edited table back into clean database rows"""
    rows =[]
    for _, r in df.iterrows():
        label = r["item_type"]
        if not isinstance(label, str) or label not in LABEL_TO_TYPE:
            continue  # Blank or half filled row
        qty = r["qty"]
        row = {"item_type": LABEL_TO_TYPE[label], "qty": int(qty) if pd.notna(qty) and qty >= 1 else 1}
        if with_photo:
            detail, photo_id = r.get("detail"), r.get("photo_id")
            row["detail"] = detail if isinstance(detail, str) and detail.strip() else None
            row["photo_id"] = photo_id if isinstance(photo_id, str) else None
        rows.append(row)
    return rows

ITEM_COLUMN = st.column_config.SelectboxColumn("Item", options=list(TYPES.values()), required = True)
QTY_COLUMN = st.column_config.NumberColumn("Qty", min_value=1, max_value=99, step=1, default=1, format="%d")

def go_compare(pid):
    """Runs as a button callback, which is the safe place to change widget values."""
    st.session_state.cmp_a = pid
    st.session_state.page = "Compare"

# AI Helpers
def analyze_room(pid, room, label):
    """photos of one room -> Claude -> saved furniture list. Returns the AI's note."""
    photos = db.list_photos(pid, room)
    found, note = ai.identity_furniture(label, [db.photo_bytes(p["path"]) for p in photos])
    rows =[]
    for f in found:
        idx = f.pop("photo_index")
        f["photo_id"] = photos[idx]["id"] if idx is not None else None
        rows.append(f)
    db.replace_items(pid, room, rows)
    ver_key = f"ver_{pid}_{room}"  # makes the review table reload with the new list
    st.session_state[ver_key] = st.session_state.get(ver_key, 0) + 1
    return note

def run_batch(pid, rooms, todo):
    """ Count furniture in several rooms one after another (big houses have many roons)."""
    bar = st.progress(0.0)
    failed =[]
    for i, room in enumerate(todo):
        bar.progress(i / len(todo), text = f"Counting furniture: {rooms[room]} ({ i + 1} of {len(todo)})...")
        try:
            analyze_room(pid, room, rooms[room])
        except Exception:
            failed.append(rooms[room])
    bar.progress(1.0)
    text = f"Counted {len(todo) - len(failed)} room(s)."
    text += f" These failed, open them and try again: {', '.json(failed)}." if failed else " Open each room to check the list."
    st.session_state[f"batch_msg_{pid}"] = {"text": text, "failed": bool(failed)}
    st.rerun()


# Projects
def projects_page():
    pid = st.session_state.get("pid")
    if pid:
        project_detail(pid)
        return 

    projects = db.list_projects()
    with st.expander("New projects", expanded=not projects):
        with st.form("new_projects", clear_on_submit=True):
            address = st.text_input("Property address *")
            customer = st.text_input("Customer name")
            c1, c2 = st.columns(2)
            phone = c1.text_input("Customer phone")
            agent = c2.text_input("Agent name")
            agent_contact = st.text_input("Agent contact")
            c3, c4 = st.columns(2)
            styling_date = c3.date_input("Styling date", value=None)
            dstage_date = c4.date_input("D-stage date", value=None)
            amount = st.number_input("Amount ($)", min_value=0.0, step=100.0)
            c5, c6, c7 = st.columns(3)
            bedrooms = c5.number_input("Bedrooms", min_value=0, max_value=MAX_BEDROOMS, step=1)
            bathrooms = c6.number_input("Bathrooms", min_value=0, max_value=12, step=1)
            living = c7.number_input("Living areas", min_value=0, max_value=MAX_LIVING_AREAS, step=1)
            notes = st.text_area("Notes")
            if st.form_submit_button("Create project", type="primary"):
                if not address.strip():
                    st.error("Add the property address first.")
                else:
                    row = db.create_project({
                        "address": address.strip(), "customer": customer or None, "phone": phone or None,
                        "agent": agent or None, "agent_contact": agent_contact or None,
                        "styling_date": styling_date.isoformat() if styling_date else None,
                        "dstage_date": dstage_date.isoformat() if dstage_date else None,
                        "amount": amount or None, "bedrooms": int(bedrooms), "bathrooms": int(bathrooms), "living_areas": int(living),
                        "notes": notes or None, "status": STAGES[0],
                    })
                    st.session_state.pid = row["id"]
                    st.rerun()

    if not projects:
        st.info("No projects yet. Create the first one above.")
    for p in projects:
        with st.container(border=True):
            st.markdown(f"**{p['address']}**")
            st.caption(" · ".join(x for x in [p.get("customer"), p["status"]] if x))
            if st.button("Open", key=f"open_{p['id']}"):
                st.session_state.pid = p["id"]
                st.rerun()


def project_detail(pid):
    p = db.get_project(pid)
    if st.button(" <- All projects"):
        st.session_state.pid = None
        st.rerun()
    st.header(p["address"])

    status = st.selectbox("Status", STAGES, index=STAGES.index(p["status"]), key=f"status_{pid}")
    if status != p["status"]:
        db.update_project(pid,{"status": status})
        st.rerun()

    st.subheader("Furniture at this property")
    have = totals(db.list_items(pid))
    if have:
        st.table(pd.DataFrame([{"Item": TYPES.get(k, k), "Qty": v} for k, v in have.items()]).set_index("Item"))
    else:
        st.caption("Nothing recorded yet.")
    st.button("Compare with next property", on_click=go_compare, args=(pid,))

    st.subheader("Rooms and photos")
    if STAGES.index(status) < STYLED_INDEX:
        st.info("Photos open once this project reaches **Styled**.")
    else:
        counts = db.room_counts(pid)
        rooms = rooms_for(p.get("bedrooms"), p.get("Living_areas"), keep = counts)
        if not p.get("bedrooms"):
            st.caption("Tip: add the number of bedrooms under Details so only this property's rooms are listed")
        msg = st.session_state.pop(f"batch_msg_{pid}", None)
        if msg:
            (st.warning if msg["failed"] else st.success)(msg["text"])
        todo =[r for r in rooms if counts.get(r, {}).get("photos") and not counts.get(r, {}).get("items")]
        if todo and st.button(f"Identity furniture in {len(todo)} room(s) with photos and no list yet", key =f"batch_{pid}"):
            run_batch(pid, rooms, todo)

        def room_name(r):
            c = counts.get(r)
            return rooms[r] + (f" ({c['photos']} photos, {c['items']} items,)" if c else "")

        room = st.selectbox("Room", list(rooms), format_func = room_name, key = f"room_{pid}")
        room_section(pid, room, rooms[room])

    with st.expander("Details"):
        with st.form(f"edit_{pid}"):
            address = st.text_input("Property address", p["address"])
            customer = st.text_input("Customer name", p.get("customer") or "")
            phone = st.text_input("Customer phone", p.get("phone") or "")
            agent = st.text_input("Agent name", p.get("agent") or "")
            agent_contact = st.text_input("Agent contact", p.get("agent_contact") or "")
            c1, c2 = st.columns(2)
            styling_date = c1.date_input("Styling date", value=to_date(p.get("styling_date")))
            dstage_date = c2.date_input("D-stage date", value=to_date(p.get("dstage_date")))
            amount = st.number_input("Amount ($)", min_value=0.0, step=100.0, value=float(p.get("amount") or 0))
            c3, c4, c5 = st.columns(3)
            bedrooms = c3.number_input("Bedrooms", min_value=0, max_value=MAX_BEDROOMS, step=1, value=int(p.get("bedrooms") or 0))
            bathrooms = c4.number_input("Bathrooms", min_value=0, max_value=12, step=1, value=int(p.get("bathrooms") or 0))
            living = c5.number_input("Living areas", min_value=0, max_value=MAX_LIVING_AREAS, step=1, value=int(p.get("living_areas") or 0))
            notes = st.text_area("Notes", p.get("notes") or "")
            if st.form_submit_button("Save details"):
                db.update_project(pid, {
                    "address": address.strip() or p["address"], "customer": customer or None, "phone": phone or None,
                    "agent": agent or None, "agent_contact": agent_contact or None,
                    "styling_date": styling_date.isoformat() if styling_date else None,
                    "dstage_date": dstage_date.isoformat() if dstage_date else None,
                    "amount": amount or None, "bedrooms": int(bedrooms), "bathrooms": int(bathrooms), "living_areas": int(living),
                    "notes": notes or None,
                })
                st.rerun()

    with st.expander("Delete project"):
        sure = st.checkbox("Yes, delete this project, its photos and its furniture list", key=f"sure_{pid}")
        if st.button("Delete project", disabled=not sure):
            db.delete_project(pid)
            st.session_state.pid = None
            st.rerun()


def room_section(pid, room, label):
    photos = db.list_photos(pid,room)
    state = st.session_state
    upload_n = state.setdefault("upload_n, 0") #Changing the key empties the uploader
    ver_key = f"ver_{pid}_{room}"
    ver = state.setdefault(ver_key, 0) # Changing it refreshes th editor

    # Photos 
    if photos:
        cols = st.columns(3)
        for i, ph in enumerate(photos):
            with cols[i % 3]:
                st.image(db.photo_bytes(ph["path"]), width="stretch")
                if st.button("Remove", key=f"rm_{ph['id']}"):
                    db.delete_photo(ph)
                    st.rerun()
    else:
        st.caption("No photos yet. Take a few from different corners of the room. ")

    left = MAX_PHOTOS_PER_ROOM - len(photos)
    if left > 0:
        files = st.file_uploader(
            "Add photos (on phone, choose Take photo)", type =["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True, key = f"up_{pid}_{room}_{upload_n}")
        if files and st.button(f"Save {min(len(files), left)} photo(s)"):
            with st.spinner("Saving Photos... "):
                for f in files[:left]:
                    db.add_photo(pid, room, f.getvalue())
            state.upload_n += 1
            st.rerun()
    else:
        st.caption(f"Up to {MAX_PHOTOS_PER_ROOM} photos per room. ")

    # AI
    st.caption("Running the AI replaces this room's furniture list below.")
    if st.button("Identify furniture from photos", type="primary", disabled=not photos, key=f"ai_{pid}_{room}"):
        with st.spinner("Counting furniture. This takes 10 to 40 seconds..."):
            try:
                analyze_room(pid, room, label)
            except Exception as e:  # show a friendly message, keep the details for debugging
                st.error("The AI step failed. Check your API key and try again.")
                st.caption(f"Details: {e}")
                st.stop()
        st.rerun()
    if state.get(f"note_{pid}_{room}"):
        st.info(f"AI note: {state[f'note_{pid}_{room}']}") 

    # Review and correct
    st.markdown("** Furniture in this room. ** Fix anything wrong, add rows at the bottom, then save.")
    edited = st.data_editor(
        editor_frame(db.list_items(pid,room), with_photo = True),
        key = f"items_{pid}_{room}_{ver}", num_rows = "dynamic", hide_index = True, width = 'stretch',
        column_order= ["item_type", "qty", "detail"],
        column_config = {"item_type": ITEM_COLUMN, "qty": QTY_COLUMN, "detail": st.column_config.TextColumn("Note")})
    if st.button("Save furniture list", key = f"save_{pid}_{room}"):
        db.replace_items(pid, room, editor_rows(edited, with_photo=True))
        state[ver_key] += 1
        st.success("saved. ")
        st.rerun()


# Compare
def compare_page():
    projects = db.list_projects()
    if len(projects) < 2:
        st.info("Creates at least two projects to compare them. ")
        return
    names = {p["id"]: p["address"] for p in projects}

    a = st.selectbox("Current property (furniture is here now)", list(names), format_func=names.get,
                     index=None, placeholder="Choose a property", key="cmp_a")
    b = st.selectbox("Next property (furniture is needed here)", [i for i in names if i != a],
                     format_func=names.get, index=None, placeholder ="Choose a property", key = "cmp_b")

    if not a:
        return

    have = totals(db.list_items(a))
    st.subheader("At the current property")
    if have:
        st.writer(", ".join(f"**{v}** {TYPES.get(k, k)}" for k, v in have.items()))
    else:
        st.caption("No furniture recorded here yet. Open the projects, add room photos and run the AI. ")
    if not b:
        return

    st.subheader("Needed at the next property")
    required = db.get_required(b)
    ver = st.session_state.setdefault(f"req_ver_{b}", 0)
    edited = st.data_editor(
        editor_frame(required), key= f"req_{b}_{ver}", num_rows= "dynamic", hide_index = True, width = "stretch",
        column_config = {"item_type": ITEM_COLUMN, "qty": QTY_COLUMN})
    if st.button("Save needed list"):
        db.set_required(b, editor_rows(edited))
        st.session_state[f"req_ver{b}"] += 1
        st.rerun()

        need = totals(required)
        rows = compare(have, need)
        if not rows:
            st.caption("Add furniture to either property to see the comparison. ")
            return

        st.subheader("Result")
        summary_lines =[f"Moves from {names[a]} to {names[b]}"]
        for title, key, note in[
            ("Available to move", "move", "At the current property and needed at the next one. "),
            ("Required from warehouse", "missing", "Needed at the next property but not avai;able at the current one. "),
            ("Left over", "left_over", "Stays at the current property: back to the warehouse or free for another job. "),

        ]:
            picked = [ r for r in rows if r[key]]
            with st.container(border=True):
                st.markdown(f"### {title}: {sum(r[key] for r in picked)}")
                st.caption(note)
                for r in picked:
                    st.write(f"**({r[key]} *** {TYPES.get(r['item_type'], r['item_type'])})")
                if not picked:
                    st.write("None")
                summary_lines += ["", f"{title}:"] + ([f"- {r[key]} × {TYPES.get(r['item_type'], r['item_type'])}" for r in picked] or ["- None"])

        st.markdown("** Line by line**")
        table = pd.DataFrame(rows)
        table["items_type"] = table["iten_type"].map(lambda t: TYPES.get(t, t))
        st.dataframe(table.rename(columns={"iten_type": "Item", "have": "Have", "need": "Need", "move": "Move", "missing": "Missing", "left_over": "Left over"}),
                     hide_index=True, width = "Stretch")
        st.markdown("** Share with the team** (Use the copy icon)")
        st.code("\n".json(summary_lines), language=None)


# Main
gate()
st.title("Styling Move Planner")
page = st.radio("Go to", ["Projects", "Compare"], horizontal=True, label_visibility="collapsed", key="page")
if page == "Projects":
    projects_page()
else:
    compare_page()
