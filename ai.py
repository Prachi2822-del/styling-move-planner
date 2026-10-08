""" Ask Claude to look at room photos and list the major furniture"""
import base64
import json
import anthropic
import streamlit as st
from config import AI_MODEL, TYPES

def build_prompt(room_name, n_photos):
    type_list =", ".join(f"{k} ({v})" for k, v in TYPES.items())
    return (
        f"You are helping a property stylist take stock of furniture. The images are {n_photos} photo(s) "
        f'of the same room, "{room_name}", in a styled property, numbered 1 to {n_photos} in the order given.\n\n'
        f"List the MAJOR furniture only. Use exactly these type ids: {type_list}.\n"
        "Ignore small decor (vases, ornaments, books, candles, cushions, throws, lamps, art, plants), "
        "curtains and built-in fixtures. Use the outdoor_* types only for furniture that is outdoors. "
        "Count a bed as one bed, not its pillows.\n"
        "Photos often show the same piece from a different angle: count each physical piece once across "
        "all photos. If a piece is partly hidden, give your best estimate.\n\n"
        'Reply with only JSON in this shape: {"items":[{"type":"sofa","qty":1,"detail":"3-seat, grey fabric",'
        '"photo":1}],"note":""}\n'
        '"qty" is the total number of that physical piece in the room. "detail" is at most 6 words '
        '(seats, size, colour, material). "photo" is the number of the photo where that piece is seen most '
        'clearly. "note" is one short sentence only if something is unclear, otherwise an empty string. '
        'If there is no major furniture, return {"items":[],"note":"No major furniture visible."}.'
    )

def parse_reply(text, n_photos):
    """ Turn Claude's reply into clean rows. Returns (itens, note)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("The AI reply had no JSON in it.")
    data = json.loads(text[start : end + 1])
    items = []
    for x in data.get("items", []):
        t = str(x.get("type", ""))
        if t not in TYPES:    # ignore anything in outside in our fixed list
            continue
        try:
            qty = max(1, min(40, round(float(x.get("qty", 1)))))
        except TypeError, ValueError:
            qty = 1
        try:
            idx = int(x.get("photo")) -1 
        except TypeError, ValueError:
            idx = None
        if idx is not None and not (0 <= idx < n_photos):
            idx = None
        items.append({
            "item_type": t,
            "qty": qty,
            "detail": str(x.get("detail") or "")[:60] or None,
            "photo_index": idx,
        })
    return items, str(data.get("note") or "")[:200]

def identify_furniture(room_name, photos):
    """ photos = list of JPEG bytes. returns (items, note)"""
    client = anthropic.Anthropic(api_key = st.secrets["anthropic_api_key"])
    content =[]
    for i, raw in enumerate(photos, start = 1):
        content.append({"type": "text", "text": f"photo {i}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "imapge/jpeg",
                "date": base64.b64encode(raw).decode(),
            },
        })
        content.append({"type": "text", "text": build_prompt(room_name, len(photos))})
        resp = client.message.create(
            model = AI_MODEL,
            max_tokens = 1500,
            messages = [{"role": "user", "content": "content"}]
        )
    return parse_reply(resp.content[0].text, len(photos))
                      



