""" The comparison logic: What can move, what is missing, what is left over."""
from collections import Counter

def totals(rows):
    """ [{'item_type' : 'sofa', 'qty': 2} ...] -> Counter({'sofa': 2}"""
    c = Counter()
    for r in rows or []:
        c[r["item_type"]] += int(r["qty"])
    return c

def compare(have, need):
    """ Compare what is at property A (have) with what property B (needs).
    
    move = the smaller of the two (A has it and B needs it)
    missing = B needs more than A has -> Bring from the warehouse
    left_over = A has more than B needs -> Stayes behind 
    """
    out =[]
    for t in sorted(set(have) | set(need)):
        a, b = have.get(t, 0), need.get(t, 0)
        out.append({
            "item_type": t,
            "have": a,
            "need": b,
            "move": min(a, b),
            "missing": max(b - a, 0),
            "left_over": max(a - b, 0)
        })
    return out

