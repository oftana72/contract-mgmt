"""
Deduplicate suppliers and local agents by merging near-duplicate names.
Run: python deduplicate.py
"""
import sys, os, re
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, PurchaseOrder

def normalize(name):
    if not name:
        return ''
    n = name.lower().strip()
    n = re.sub(r'[^\w\s]', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    replacements = {
        'ltd': 'limited', 'pharma': 'pharmaceutical',
        'plc': 'plc', 'fzc': 'fzc', 'fz': 'fz', 'fzllc': 'fz-llc',
        'int': 'international', 'co': 'company',
        'pvt': 'private', 'dept': 'department',
        'lab': 'laboratory', 'labs': 'laboratory',
        'mfg': 'manufacturing', 'mfr': 'manufacturing',
        'const': 'construction', 'constraction': 'construction',
        'consractyion': 'construction', 'consract': 'construction',
        'equip': 'equipment', 'equpment': 'equipment',
        'deliverd': 'delivered', 'deliv': 'delivered',
        'utd': 'united', 'ermir': 'emirates', 'ermi': 'emirates',
        'emir': 'emirates', 'switherland': 'switzerland',
        'healhcare': 'healthcare', 'healh': 'health',
        'pharmacutical': 'pharmaceutical',
        'phaemaceutical': 'pharmaceutical',
        'pharmaceuguticals': 'pharmaceutical',
        'biotech': 'biotechnology',
        'diagnotics': 'diagnostics',
        'laboratoriys': 'laboratory',
        'laboratoris': 'laboratory',
        'bussiness': 'business',
        'buziness': 'business',
        'bussines': 'business',
        'manufaturing': 'manufacturing',
        'pharmamanufacturing': 'pharmaceutical manufacturing',
        'gmbh': 'gmbh',
        'ind': 'industries',
        'industria': 'industries',
        'instrumnt': 'instruments',
        'intruments': 'instruments',
    }
    words = n.split()
    result = []
    for w in words:
        w2 = w.strip('.,')
        if w2 in replacements:
            result.append(replacements[w2])
        else:
            result.append(w2)
    return ' '.join(result)

def build_groups(items, name_attr):
    """Group items by similarity."""
    groups = defaultdict(list)
    for item in items:
        key = normalize(getattr(item, name_attr))
        groups[key].append(item)
    return groups

def merge_groups(groups):
    """Merge groups, returning {canonical_id: [duplicate_ids]}"""
    merges = {}
    for norm, items in groups.items():
        if len(items) <= 1:
            continue
        items_sorted = sorted(items, key=lambda x: len(getattr(x, 'name', '') or ''), reverse=True)
        keep = items_sorted[0]
        dup_ids = [item.id for item in items_sorted[1:]]
        merges[keep.id] = {'keep': keep, 'duplicate_ids': dup_ids}
    return merges

def run():
    with app.app_context():
        print("=== Suppliers ===")
        suppliers = Supplier.query.all()
        groups = build_groups(suppliers, 'name')
        merges = merge_groups(groups)
        total_merged = 0

        for keep_id, info in sorted(merges.items(), key=lambda x: -len(x[1]['duplicate_ids'])):
            keep = info['keep']
            dup_ids = info['duplicate_ids']
            dups = Supplier.query.filter(Supplier.id.in_(dup_ids)).all()
            print(f"  Keep [{keep.id}] '{keep.name}' ({keep.country})")
            for d in dups:
                print(f"    Merge [{d.id}] '{d.name}' ({d.country})")
                PurchaseOrder.query.filter(PurchaseOrder.supplier_id == d.id).update(
                    {PurchaseOrder.supplier_id: keep.id}, synchronize_session=False
                )
                PurchaseOrder.query.filter(PurchaseOrder.supplier_name_raw == d.name).update(
                    {PurchaseOrder.supplier_id: keep.id, PurchaseOrder.supplier_name_raw: None},
                    synchronize_session=False
                )
                db.session.delete(d)
                total_merged += 1

        db.session.commit()
        print(f"\nMerged {total_merged} suppliers")

        remaining = Supplier.query.count()
        print(f"Remaining suppliers: {remaining}")

        print("\n=== Local Agents ===")
        agents = LocalAgent.query.all()
        groups = build_groups(agents, 'name')
        merges = merge_groups(groups)
        total_merged = 0

        for keep_id, info in sorted(merges.items(), key=lambda x: -len(x[1]['duplicate_ids'])):
            keep = info['keep']
            dup_ids = info['duplicate_ids']
            dups = LocalAgent.query.filter(LocalAgent.id.in_(dup_ids)).all()
            print(f"  Keep [{keep.id}] '{keep.name}'")
            for d in dups:
                print(f"    Merge [{d.id}] '{d.name}'")
                PurchaseOrder.query.filter(PurchaseOrder.local_agent_id == d.id).update(
                    {PurchaseOrder.local_agent_id: keep.id}, synchronize_session=False
                )
                PurchaseOrder.query.filter(PurchaseOrder.local_agent_raw == d.name).update(
                    {PurchaseOrder.local_agent_id: keep.id, PurchaseOrder.local_agent_raw: None},
                    synchronize_session=False
                )
                db.session.delete(d)
                total_merged += 1

        db.session.commit()
        print(f"\nMerged {total_merged} local agents")

        remaining = LocalAgent.query.count()
        print(f"Remaining local agents: {remaining}")

if __name__ == '__main__':
    run()
