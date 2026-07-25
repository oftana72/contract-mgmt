"""
Fix issues from sheet2 import:
1. "BR" currency → "ETB"
2. Budget sources with newlines → normalize and merge
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, BudgetSource, PurchaseOrder

def run_fixes():
    # 1. Fix BR currency
    fixed = PurchaseOrder.query.filter(PurchaseOrder.currency == 'BR').all()
    for po in fixed:
        po.currency = 'ETB'
    if fixed:
        db.session.commit()

    # 2. Fix budget sources with newlines
    weird_bs = BudgetSource.query.filter(BudgetSource.name.like('%\n%')).all()
    for bs in weird_bs:
        clean_name = bs.name.replace('\n', '').strip()
        canonical = BudgetSource.query.filter_by(name=clean_name).first()
        if not canonical:
            bs.name = clean_name
        else:
            PurchaseOrder.query.filter_by(budget_source_id=bs.id).update(
                {'budget_source_id': canonical.id}
            )
            db.session.delete(bs)
    if weird_bs:
        db.session.commit()

    # 3. Normalize "FW/PIMA CD4/Analyzer/" → None
    fw = BudgetSource.query.filter(BudgetSource.name.like('FW/PIMA%')).first()
    if fw:
        PurchaseOrder.query.filter_by(budget_source_id=fw.id).update({'budget_source_id': None})
        db.session.delete(fw)
        db.session.commit()

    # 4. Normalize Ministry of Finance → Treasury
    mof = BudgetSource.query.filter(BudgetSource.name.like('Ministry%Finance%')).first()
    if mof:
        treasury = BudgetSource.query.filter_by(name='Treasury').first()
        if treasury:
            PurchaseOrder.query.filter_by(budget_source_id=mof.id).update({'budget_source_id': treasury.id})
            db.session.delete(mof)
            db.session.commit()

    # 5. Normalize GF-AHPCO/NFMIII/ARV/OI → GF
    gf_ahpco = BudgetSource.query.filter(BudgetSource.name.like('GF-AHPCO%')).first()
    if gf_ahpco:
        gf = BudgetSource.query.filter_by(name='GF').first()
        if gf:
            PurchaseOrder.query.filter_by(budget_source_id=gf_ahpco.id).update({'budget_source_id': gf.id})
            db.session.delete(gf_ahpco)
            db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        run_fixes()
        # Verify
        from sqlalchemy import text
        currs = db.session.execute(text("SELECT currency, COUNT(*) FROM purchase_orders WHERE serial_number >= 1725 GROUP BY currency ORDER BY COUNT(*) DESC")).fetchall()
        print(f'\nCurrency dist after fix: {currs}')
        sources = db.session.execute(text("SELECT bs.name, COUNT(*) FROM purchase_orders po LEFT JOIN budget_sources bs ON po.budget_source_id=bs.id WHERE po.serial_number >= 1725 GROUP BY bs.name ORDER BY COUNT(*) DESC")).fetchall()
        print(f'Budget sources after fix: {sources}')
        print('Done')
