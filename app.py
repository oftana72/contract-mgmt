import os
import sys
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, Date, Text, ForeignKey, func, or_, distinct
from dateutil import parser as dateparser
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'contract-mgmt-secret-key')
db_url = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:@localhost:3306/contract_mgmt')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(80), unique=True, nullable=False)
    password_hash = db.Column(String(200), nullable=False)
    is_admin = db.Column(Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False)
    country = db.Column(String(100))

class LocalAgent(db.Model):
    __tablename__ = 'local_agents'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False, unique=True)

class BudgetSource(db.Model):
    __tablename__ = 'budget_sources'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False, unique=True)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(Integer, primary_key=True)
    serial_number = db.Column(Integer)
    received_date = db.Column(Date)
    tender_reference = db.Column(String(200))
    po_number = db.Column(String(100), index=True)
    supplier_id = db.Column(Integer, ForeignKey('suppliers.id'))
    supplier_name_raw = db.Column(String(300))
    country_raw = db.Column(String(100))
    local_agent_id = db.Column(Integer, ForeignKey('local_agents.id'))
    local_agent_raw = db.Column(String(300))
    total_po_amount = db.Column(Float)
    currency = db.Column(String(10))
    budget_source_id = db.Column(Integer, ForeignKey('budget_sources.id'))
    mode_of_shipment = db.Column(String(50))
    po_transferred_date = db.Column(Date)
    remark = db.Column(Text)
    biofficer_id = db.Column(Integer, ForeignKey('bi_officers.id'))
    shipment_officer_id = db.Column(Integer, ForeignKey('shipment_officers.id'))
    status_id = db.Column(Integer, ForeignKey('po_statuses.id'))

    supplier = db.relationship('Supplier', backref='orders')
    local_agent = db.relationship('LocalAgent', backref='orders')
    budget_source = db.relationship('BudgetSource', backref='orders')
    biofficer = db.relationship('BIOfficer', backref='orders')
    shipment_officer = db.relationship('ShipmentOfficer', backref='orders')
    po_status = db.relationship('POStatus', backref='orders')
    line_items = db.relationship('LineItem', backref='po', lazy='dynamic', cascade='all, delete-orphan')
    performance_guarantees = db.relationship('PerformanceGuarantee', backref='po', lazy='dynamic', cascade='all, delete-orphan')
    letter_of_credits = db.relationship('LetterOfCredit', backref='po', lazy='dynamic', cascade='all, delete-orphan')
    shipments = db.relationship('Shipment', backref='po', lazy='dynamic', cascade='all, delete-orphan')
    pg_expiry_date = db.Column(Date)
    pg_status = db.Column(String(20))
    pg_release_date = db.Column(Date)
    pg_received_by = db.Column(String(200))
    pg_confiscation_reason = db.Column(Text)
    status_changed_by = db.Column(String(80))
    status_changed_at = db.Column(Date)

    @property
    def pg_days_left(self):
        if not self.pg_expiry_date:
            return None
        delta = (self.pg_expiry_date - date.today()).days
        return delta

    @property
    def lc_age_days(self):
        lc = self.letter_of_credits.first()
        if not lc or not lc.opened_date:
            return None
        delta = (date.today() - lc.opened_date).days
        return delta

class LineItem(db.Model):
    __tablename__ = 'line_items'
    id = db.Column(Integer, primary_key=True)
    po_id = db.Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    description = db.Column(Text)
    unit = db.Column(String(20))
    quantity = db.Column(Float)
    unit_price = db.Column(Float)
    total_price = db.Column(Float)

class PerformanceGuarantee(db.Model):
    __tablename__ = 'performance_guarantees'
    id = db.Column(Integer, primary_key=True)
    po_id = db.Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    requested_date = db.Column(Date)
    received_date = db.Column(Date)
    confirmed_date = db.Column(Date)
    bank_name = db.Column(String(200))
    pg_reference = db.Column(String(200))
    expiry_date = db.Column(Date)
    remaining_days = db.Column(Integer)
    submit_pg = db.Column(String(50))
    status = db.Column(String(50))
    status_date = db.Column(Date)
    pg_receiver_name = db.Column(String(200))
    bi_officer = db.Column(String(100))

class LetterOfCredit(db.Model):
    __tablename__ = 'letter_of_credits'
    id = db.Column(Integer, primary_key=True)
    po_id = db.Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    opening_status = db.Column(String(50))
    opened_date = db.Column(Date)
    expiry_date = db.Column(Date)
    age_days = db.Column(Integer)

class Shipment(db.Model):
    __tablename__ = 'shipments'
    id = db.Column(Integer, primary_key=True)
    po_id = db.Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    shipment_officer = db.Column(String(100))
    shipment_status = db.Column(String(100))
    order_closure = db.Column(String(50))

class BIOfficer(db.Model):
    __tablename__ = 'bi_officers'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False, unique=True)

class ShipmentOfficer(db.Model):
    __tablename__ = 'shipment_officers'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False, unique=True)

class POStatus(db.Model):
    __tablename__ = 'po_statuses'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(50), nullable=False, unique=True)

def parse_date(val):
    if not val or str(val).strip() in ('', 'ENTER DATE', 'NM', '#REF!'):
        return None
    try:
        if isinstance(val, (int, float)):
            from datetime import timedelta
            base = datetime(1899, 12, 30)
            return (base + timedelta(days=float(val))).date()
        s = str(val).strip()
        return dateparser.parse(s).date()
    except:
        return None

def parse_float(val):
    if not val:
        return None
    s = str(val).replace(',', '').replace(' ', '')
    try:
        return float(s)
    except:
        return None

def ensure_admin():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', is_admin=1)
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        return True
    return False

with app.app_context():
    db.create_all()
    ensure_admin()
    # Migration: add missing columns, backfill
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('purchase_orders')]
        for col, coltype in [('pg_expiry_date', 'DATE'), ('pg_status', 'VARCHAR(20)'), ('pg_release_date', 'DATE'), ('pg_received_by', 'VARCHAR(200)'), ('pg_confiscation_reason', 'TEXT'), ('status_changed_by', 'VARCHAR(80)'), ('status_changed_at', 'DATE')]:
            if col not in cols:
                db.session.execute(db.text(f'ALTER TABLE purchase_orders ADD COLUMN {col} {coltype}'))
                print(f'Added {col} column')
    except Exception as e:
        print('Migration (add columns): ' + str(e))
    try:
        from sqlalchemy import text
        is_pg = 'postgresql' in str(db.engine.url)
        if is_pg:
            db.session.execute(text(
                'UPDATE purchase_orders po '
                'SET pg_expiry_date = pg.expiry_date '
                'FROM performance_guarantees pg '
                'WHERE po.id = pg.po_id '
                'AND pg.expiry_date IS NOT NULL '
                'AND po.pg_expiry_date IS NULL'
            ))
        else:
            db.session.execute(text(
                'UPDATE purchase_orders po '
                'SET pg_expiry_date = ('
                '  SELECT pg.expiry_date FROM performance_guarantees pg '
                '  WHERE po.id = pg.po_id AND pg.expiry_date IS NOT NULL '
                '  LIMIT 1)'
                'WHERE po.pg_expiry_date IS NULL '
                'AND EXISTS ('
                '  SELECT 1 FROM performance_guarantees pg '
                '  WHERE po.id = pg.po_id AND pg.expiry_date IS NOT NULL)'
            ))
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        print('Migration (backfill): ' + str(e))
    # Startup: dedup + cleanup + conditional import (PostgreSQL/Render only)
    try:
        is_pg = 'postgresql' in str(db.engine.url)
        if is_pg:
            # ---- Dedup: keep latest PO per serial_number ----
            from sqlalchemy import select, func
            dup_sns = db.session.query(
                PurchaseOrder.serial_number,
                func.count(PurchaseOrder.id)
            ).group_by(PurchaseOrder.serial_number).having(func.count(PurchaseOrder.id) > 1).all()
            for sn, cnt in dup_sns:
                dup_pos = PurchaseOrder.query.filter_by(serial_number=sn).order_by(PurchaseOrder.id.desc()).all()
                for po in dup_pos[1:]:
                    PerformanceGuarantee.query.filter_by(po_id=po.id).delete()
                    LetterOfCredit.query.filter_by(po_id=po.id).delete()
                    Shipment.query.filter_by(po_id=po.id).delete()
                    LineItem.query.filter_by(po_id=po.id).delete()
                    db.session.delete(po)
                if dup_pos:
                    print(f'  Dedup: kept SN={sn} (removed {cnt-1} dupes)')
            if dup_sns:
                db.session.commit()

            # ---- Remove POs with no PO number (plus any orphans) ----
            no_po = PurchaseOrder.query.filter(
                (PurchaseOrder.po_number == None) | (PurchaseOrder.po_number == '')
            ).all()
            for po in no_po:
                PerformanceGuarantee.query.filter_by(po_id=po.id).delete()
                LetterOfCredit.query.filter_by(po_id=po.id).delete()
                Shipment.query.filter_by(po_id=po.id).delete()
                LineItem.query.filter_by(po_id=po.id).delete()
                db.session.delete(po)
            if no_po:
                db.session.commit()
                print(f'  Cleanup: removed {len(no_po)} POs with no PO number')

            # ---- Remove specific serials ----
            remove_sns = [3051,3037,3036,3035,3033,3032,3031,3029,3028,3026,3025,3024,3023,3022,3015,3014,3013,3012,3011,3010,3009,3008,3007,3006,3005,3004,3003,3001,3000,2999,2998,2997,2996,2995,2994,2993,2992,2991,2990,2988,2987,2986,2985,2984,2983,2982,2981,2980,2979,2978,2977,2976,2975,2974,2973,2972,2971,2967,2961,2960,2958,2957,2954,2953,2952,2951,2950,2949,2948,2947,2946,2945,2944,2943,2942,2941,2940,2939,2938,2937,2936,2934,2933,2932,2931,2930,2929,2928,2927,2926,2925,2924,2923,2922,2921,2920,2919,2918,2917,2916,2776,2769,2759,2758,2757,2698,2648,2647,2644,2029,1454,1453,1452,1451,1450,1449,1448,1447,1446,1348,1337,895,243]
            to_remove = PurchaseOrder.query.filter(PurchaseOrder.serial_number.in_(remove_sns)).all()
            for po in to_remove:
                PerformanceGuarantee.query.filter_by(po_id=po.id).delete()
                LetterOfCredit.query.filter_by(po_id=po.id).delete()
                Shipment.query.filter_by(po_id=po.id).delete()
                LineItem.query.filter_by(po_id=po.id).delete()
                db.session.delete(po)
            if to_remove:
                db.session.commit()
                print(f'  Cleanup: removed {len(to_remove)} POs by serial number')

            # ---- Import CSVs if total POs is below expected count ----
            csv_2017 = os.path.join(os.path.dirname(__file__), '2017.csv')
            csv_2016 = os.path.join(os.path.dirname(__file__), '2016.csv')
            po_count = PurchaseOrder.query.count()
            if po_count < 1700:
                sys.path.insert(0, os.path.dirname(__file__))
                if os.path.exists(csv_2017):
                    from import_csv_data import import_csv
                    import_csv(csv_2017)
                if os.path.exists(csv_2016):
                    from import_csv_data import import_csv
                    import_csv(csv_2016)
    except Exception as e:
        print(f'Startup init error: {e}')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    total_pos = PurchaseOrder.query.count()
    total_items = LineItem.query.count()
    total_suppliers = Supplier.query.count()
    total_amount = db.session.query(func.sum(PurchaseOrder.total_po_amount)).scalar() or 0
    recent_pos = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).limit(5).all()
    return render_template('index.html', total_pos=total_pos, total_items=total_items,
                          total_suppliers=total_suppliers, total_amount=total_amount,
                          recent_pos=recent_pos)

@app.route('/pos')
@login_required
def po_list():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    year_filter = request.args.get('year', '').strip()
    budget_filter = request.args.get('budget', '').strip()

    query = PurchaseOrder.query

    if search:
        q = '%' + search + '%'
        query = query.join(Supplier, PurchaseOrder.supplier_id == Supplier.id, isouter=True)
        query = query.filter(
            db.or_(
                PurchaseOrder.po_number.like(q),
                PurchaseOrder.tender_reference.like(q),
                Supplier.name.like(q),
                PurchaseOrder.supplier_name_raw.like(q)
            )
        )

    if status_filter:
        query = query.join(POStatus, PurchaseOrder.status_id == POStatus.id, isouter=True)
        query = query.filter(POStatus.name == status_filter)

    if year_filter:
        try:
            y = int(year_filter)
            query = query.filter(db.extract('year', PurchaseOrder.received_date) == y)
        except ValueError:
            pass

    query = query.order_by(PurchaseOrder.received_date.desc(), PurchaseOrder.serial_number.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    pos = pagination.items

    years = db.session.query(db.extract('year', PurchaseOrder.received_date).label('y')) \
        .filter(PurchaseOrder.received_date.isnot(None)) \
        .distinct().order_by(db.text('y desc')).all()
    years = [r[0] for r in years]

    budget_sources = BudgetSource.query.order_by(BudgetSource.name).all()
    all_statuses = POStatus.query.order_by(POStatus.name).all()

    year_summary = db.session.query(
        db.extract('year', PurchaseOrder.received_date).label('y'),
        func.count(PurchaseOrder.id),
        func.sum(PurchaseOrder.total_po_amount)
    ).filter(PurchaseOrder.received_date.isnot(None)) \
     .group_by(db.text('y')).order_by(db.text('y desc')).all()

    return render_template('po_list.html', pos=pos, pagination=pagination,
                          search=search, budget_sources=budget_sources,
                          all_statuses=all_statuses, status_filter=status_filter,
                          year_filter=year_filter, years=years, year_summary=year_summary)

@app.route('/pos/<int:po_id>')
@login_required
def po_detail(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    return render_template('po_detail.html', po=po)

@app.route('/admin/cleanup', methods=['GET'])
@login_required
def admin_cleanup():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    remove_sns = [3051,3037,3036,3035,3033,3032,3031,3029,3028,3026,3025,3024,3023,3022,3015,3014,3013,3012,3011,3010,3009,3008,3007,3006,3005,3004,3003,3001,3000,2999,2998,2997,2996,2995,2994,2993,2992,2991,2990,2988,2987,2986,2985,2984,2983,2982,2981,2980,2979,2978,2977,2976,2975,2974,2973,2972,2971,2967,2961,2960,2958,2957,2954,2953,2952,2951,2950,2949,2948,2947,2946,2945,2944,2943,2942,2941,2940,2939,2938,2937,2936,2934,2933,2932,2931,2930,2929,2928,2927,2926,2925,2924,2923,2922,2921,2920,2919,2918,2917,2916,2776,2769,2759,2758,2757,2698,2648,2647,2644,2029,1454,1453,1452,1451,1450,1449,1448,1447,1446,1348,1337,895,243]
    to_remove = PurchaseOrder.query.filter(PurchaseOrder.serial_number.in_(remove_sns)).all()
    count = len(to_remove)
    for po in to_remove:
        PerformanceGuarantee.query.filter_by(po_id=po.id).delete()
        LetterOfCredit.query.filter_by(po_id=po.id).delete()
        Shipment.query.filter_by(po_id=po.id).delete()
        LineItem.query.filter_by(po_id=po.id).delete()
        db.session.delete(po)
    db.session.commit()
    flash(f'Cleanup: removed {count} POs', 'success')
    return redirect(url_for('index'))

@app.route('/pos/<int:po_id>/delete', methods=['POST'])
@login_required
def po_delete(po_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('po_detail', po_id=po_id))
    po = PurchaseOrder.query.get_or_404(po_id)
    po_number = po.po_number or str(po.id)
    db.session.delete(po)
    db.session.commit()
    flash(f'PO {po_number} and all associated data deleted', 'success')
    return redirect(url_for('po_list'))

@app.route('/pos/<int:po_id>/edit', methods=['GET', 'POST'])
@login_required
def po_edit(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if request.method == 'POST':
        po.received_date = parse_date(request.form.get('received_date'))
        po.tender_reference = request.form.get('tender_reference', '').strip()
        po.mode_of_shipment = request.form.get('mode_of_shipment', '').strip()
        po.po_transferred_date = parse_date(request.form.get('po_transferred_date'))
        po.total_po_amount = parse_float(request.form.get('total_po_amount'))
        po.currency = request.form.get('currency', '').strip()
        po.remark = request.form.get('remark', '')
        po.pg_expiry_date = parse_date(request.form.get('pg_expiry_date'))
        po.pg_status = request.form.get('pg_status', '').strip() or None
        po.pg_release_date = parse_date(request.form.get('pg_release_date'))
        po.pg_received_by = request.form.get('pg_received_by', '').strip() or None
        po.pg_confiscation_reason = request.form.get('pg_confiscation_reason', '').strip() or None

        bi_name = request.form.get('bi_officer_name', '').strip()
        if bi_name:
            bi = BIOfficer.query.filter_by(name=bi_name).first()
            if not bi:
                bi = BIOfficer(name=bi_name)
                db.session.add(bi)
                db.session.flush()
            po.biofficer_id = bi.id
        else:
            po.biofficer_id = None

        sh_name = request.form.get('shipment_officer_name', '').strip()
        if sh_name:
            sh = ShipmentOfficer.query.filter_by(name=sh_name).first()
            if not sh:
                sh = ShipmentOfficer(name=sh_name)
                db.session.add(sh)
                db.session.flush()
            po.shipment_officer_id = sh.id
        else:
            po.shipment_officer_id = None

        st_name = request.form.get('po_status', '').strip()
        old_status = po.po_status.name if po.po_status else None
        if st_name:
            st = POStatus.query.filter_by(name=st_name).first()
            if not st:
                st = POStatus(name=st_name)
                db.session.add(st)
                db.session.flush()
            po.status_id = st.id
        else:
            po.status_id = None
        new_status = st_name if st_name else None
        if old_status != new_status:
            po.status_changed_by = current_user.username
            po.status_changed_at = date.today()

        lc = po.letter_of_credits.first()
        lc_status = request.form.get('lc_status', '').strip()
        if lc_status:
            if not lc:
                lc = LetterOfCredit(po_id=po.id)
                db.session.add(lc)
                db.session.flush()
            lc.opening_status = lc_status
            lc.opened_date = parse_date(request.form.get('lc_opened_date'))
            lc.expiry_date = parse_date(request.form.get('lc_expiry_date'))

        # Handle line items
        delete_items = request.form.getlist('delete_item')
        for item_id in delete_items:
            item = LineItem.query.get(int(item_id))
            if item and item.po_id == po.id:
                db.session.delete(item)

        existing_ids = set()
        for item in po.line_items.all():
            desc = request.form.get('item_desc_' + str(item.id), '').strip()
            unit = request.form.get('item_unit_' + str(item.id), '').strip()
            qty = parse_float(request.form.get('item_qty_' + str(item.id)))
            up = parse_float(request.form.get('item_up_' + str(item.id)))
            if str(item.id) not in delete_items and desc:
                item.description = desc
                item.unit = unit
                item.quantity = qty
                item.unit_price = up
                item.total_price = (qty * up) if qty and up else None
                existing_ids.add(item.id)

        new_descs = request.form.getlist('new_item_desc')
        new_units = request.form.getlist('new_item_unit')
        new_qtys = request.form.getlist('new_item_qty')
        new_ups = request.form.getlist('new_item_up')
        for i in range(len(new_descs)):
            desc = new_descs[i].strip()
            if desc:
                unit = new_units[i].strip() if i < len(new_units) else ''
                qty = parse_float(new_qtys[i]) if i < len(new_qtys) else None
                up = parse_float(new_ups[i]) if i < len(new_ups) else None
                tp = (qty * up) if qty and up else None
                db.session.add(LineItem(po_id=po.id, description=desc, unit=unit,
                    quantity=qty, unit_price=up, total_price=tp))

        db.session.commit()
        flash('PO updated', 'success')
        return redirect(url_for('po_detail', po_id=po.id))
    return render_template('po_edit.html', po=po,
        bi_officers=BIOfficer.query.order_by(BIOfficer.name).all(),
        shipment_officers=ShipmentOfficer.query.order_by(ShipmentOfficer.name).all(),
        po_statuses=POStatus.query.order_by(POStatus.name).all())

@app.route('/reports')
@login_required
def reports():
    budget_data = db.session.query(
        BudgetSource.name, func.count(PurchaseOrder.id), func.sum(PurchaseOrder.total_po_amount)
    ).join(BudgetSource, PurchaseOrder.budget_source_id == BudgetSource.id, isouter=True
    ).group_by(BudgetSource.name).all()

    supplier_data = db.session.query(
        Supplier.name, func.count(PurchaseOrder.id)
    ).join(Supplier, PurchaseOrder.supplier_id == Supplier.id, isouter=True
    ).group_by(Supplier.name).order_by(func.count(PurchaseOrder.id).desc()).limit(20).all()

    currency_data = db.session.query(
        PurchaseOrder.currency, func.count(PurchaseOrder.id), func.sum(PurchaseOrder.total_po_amount)
    ).group_by(PurchaseOrder.currency).all()

    po_year = db.session.query(
        db.extract('year', PurchaseOrder.received_date).label('y'),
        PurchaseOrder.id, PurchaseOrder.total_po_amount
    ).filter(PurchaseOrder.received_date.isnot(None)).subquery()

    item_counts = db.session.query(
        LineItem.po_id, func.count(LineItem.id).label('ic')
    ).group_by(LineItem.po_id).subquery()

    year_data = db.session.query(
        po_year.c.y,
        func.count(distinct(po_year.c.id)),
        func.sum(po_year.c.total_po_amount),
        func.coalesce(func.sum(item_counts.c.ic), 0)
    ).outerjoin(item_counts, po_year.c.id == item_counts.c.po_id
    ).group_by(po_year.c.y).order_by(po_year.c.y.desc()).all()

    budget_year_data = db.session.query(
        BudgetSource.name,
        db.extract('year', PurchaseOrder.received_date).label('y'),
        func.sum(PurchaseOrder.total_po_amount)
    ).join(BudgetSource, PurchaseOrder.budget_source_id == BudgetSource.id, isouter=True
    ).filter(PurchaseOrder.received_date.isnot(None)
    ).group_by(BudgetSource.name, db.text('y')).order_by(BudgetSource.name, db.text('y desc')).all()

    return render_template('reports.html', budget_data=budget_data,
                          supplier_data=supplier_data, currency_data=currency_data,
                          year_data=year_data, budget_year_data=budget_year_data)

@app.route('/api/pos')
@login_required
def api_pos():
    pos = PurchaseOrder.query.order_by(PurchaseOrder.serial_number).all()
    result = []
    for po in pos:
        items = [{'description': li.description, 'unit': li.unit,
                  'quantity': li.quantity, 'unit_price': li.unit_price,
                  'total_price': li.total_price} for li in po.line_items]
        pgs = [{'bank_name': pg.bank_name, 'status': pg.status,
                'requested_date': str(pg.requested_date) if pg.requested_date else None}
               for pg in po.performance_guarantees]
        lcs = [{'opening_status': lc.opening_status,
                'opened_date': str(lc.opened_date) if lc.opened_date else None}
               for lc in po.letter_of_credits]
        result.append({
            'id': po.id, 'serial': po.serial_number, 'po_number': po.po_number,
            'supplier': po.supplier.name if po.supplier else po.supplier_name_raw,
            'total_amount': po.total_po_amount, 'currency': po.currency,
            'line_items': items, 'pgs': pgs, 'lcs': lcs
        })
    return jsonify(result)

@app.route('/pos/new', methods=['GET', 'POST'])
@login_required
def po_create():
    if request.method == 'POST':
        po_number = request.form.get('po_number', '').strip()
        if not po_number:
            flash('PO Number is required', 'danger')
            item_descriptions = [r[0] for r in db.session.query(distinct(LineItem.description)).filter(LineItem.description.isnot(None), LineItem.description != '').order_by(LineItem.description).all()]
            return render_template('po_create.html',
                suppliers=Supplier.query.order_by(Supplier.name).all(),
                agents=LocalAgent.query.order_by(LocalAgent.name).all(),
                budgets=BudgetSource.query.order_by(BudgetSource.name).all(),
                item_descriptions=item_descriptions)

        supplier_name = request.form.get('supplier_name', '').strip()
        supplier_country = request.form.get('supplier_country', '').strip()
        local_agent_name = request.form.get('local_agent_name', '').strip()
        budget_name = request.form.get('budget_source', '').strip()

        supplier = None
        if supplier_name:
            supplier = Supplier.query.filter_by(name=supplier_name).first()
            if not supplier:
                supplier = Supplier(name=supplier_name, country=supplier_country)
                db.session.add(supplier)
                db.session.flush()

        local_agent = None
        if local_agent_name:
            local_agent = LocalAgent.query.filter_by(name=local_agent_name).first()
            if not local_agent:
                local_agent = LocalAgent(name=local_agent_name)
                db.session.add(local_agent)
                db.session.flush()

        budget_source = None
        if budget_name:
            budget_source = BudgetSource.query.filter_by(name=budget_name).first()
            if not budget_source:
                budget_source = BudgetSource(name=budget_name)
                db.session.add(budget_source)
                db.session.flush()

        bi_officer_name = request.form.get('bi_officer_name', '').strip()
        bi_officer = None
        if bi_officer_name:
            bi_officer = BIOfficer.query.filter_by(name=bi_officer_name).first()
            if not bi_officer:
                bi_officer = BIOfficer(name=bi_officer_name)
                db.session.add(bi_officer)
                db.session.flush()

        sh_officer_name = request.form.get('shipment_officer_name', '').strip()
        sh_officer = None
        if sh_officer_name:
            sh_officer = ShipmentOfficer.query.filter_by(name=sh_officer_name).first()
            if not sh_officer:
                sh_officer = ShipmentOfficer(name=sh_officer_name)
                db.session.add(sh_officer)
                db.session.flush()

        po_status_name = request.form.get('po_status', '').strip()
        po_status = None
        if po_status_name:
            po_status = POStatus.query.filter_by(name=po_status_name).first()
            if not po_status:
                po_status = POStatus(name=po_status_name)
                db.session.add(po_status)
                db.session.flush()

        max_sn = db.session.query(func.max(PurchaseOrder.serial_number)).scalar() or 0

        po = PurchaseOrder(
            serial_number=max_sn + 1,
            received_date=parse_date(request.form.get('received_date')),
            tender_reference=request.form.get('tender_reference', '').strip(),
            po_number=po_number,
            supplier_id=supplier.id if supplier else None,
            supplier_name_raw=supplier_name if not supplier else None,
            country_raw=supplier_country if not supplier else None,
            local_agent_id=local_agent.id if local_agent else None,
            local_agent_raw=local_agent_name if not local_agent else None,
            total_po_amount=parse_float(request.form.get('total_po_amount')),
            currency=request.form.get('currency', '').strip(),
            budget_source_id=budget_source.id if budget_source else None,
            mode_of_shipment=request.form.get('mode_of_shipment', '').strip(),
            po_transferred_date=parse_date(request.form.get('po_transferred_date')),
            remark=request.form.get('remark', '').strip(),
            biofficer_id=bi_officer.id if bi_officer else None,
            shipment_officer_id=sh_officer.id if sh_officer else None,
            status_id=po_status.id if po_status else None,
            pg_expiry_date=parse_date(request.form.get('pg_expiry_date')),
            pg_status=request.form.get('pg_status', '').strip() or None,
            pg_release_date=parse_date(request.form.get('pg_release_date')),
            pg_received_by=request.form.get('pg_received_by', '').strip() or None,
            pg_confiscation_reason=request.form.get('pg_confiscation_reason', '').strip() or None
        )
        db.session.add(po)
        db.session.flush()

        descs = request.form.getlist('item_description[]')
        units = request.form.getlist('item_unit[]')
        qtys = request.form.getlist('item_quantity[]')
        prices = request.form.getlist('item_unit_price[]')

        for i, desc in enumerate(descs):
            if desc.strip():
                li = LineItem(
                    po_id=po.id,
                    description=desc.strip(),
                    unit=units[i].strip() if i < len(units) else '',
                    quantity=parse_float(qtys[i]) if i < len(qtys) else None,
                    unit_price=parse_float(prices[i]) if i < len(prices) else None,
                    total_price=parse_float(qtys[i]) * parse_float(prices[i]) if i < len(qtys) and i < len(prices) and parse_float(qtys[i]) and parse_float(prices[i]) else None
                )
                db.session.add(li)

        lc_status = request.form.get('lc_status', '').strip()
        if lc_status:
            lc = LetterOfCredit(
                po_id=po.id,
                opening_status=lc_status,
                opened_date=parse_date(request.form.get('lc_opened_date')),
                expiry_date=parse_date(request.form.get('lc_expiry_date'))
            )
            db.session.add(lc)

        shipment_officer = request.form.get('shipment_officer', '').strip()
        if shipment_officer:
            sh = Shipment(
                po_id=po.id,
                shipment_officer=shipment_officer,
                shipment_status=request.form.get('shipment_status', '').strip(),
                order_closure=request.form.get('order_closure', '').strip()
            )
            db.session.add(sh)

        db.session.commit()
        flash(f'Contract {po_number} created successfully!', 'success')
        return redirect(url_for('po_detail', po_id=po.id))

    item_descriptions = [r[0] for r in db.session.query(distinct(LineItem.description)).filter(LineItem.description.isnot(None), LineItem.description != '').order_by(LineItem.description).all()]
    return render_template('po_create.html',
        suppliers=Supplier.query.order_by(Supplier.name).all(),
        agents=LocalAgent.query.order_by(LocalAgent.name).all(),
        budgets=BudgetSource.query.order_by(BudgetSource.name).all(),
        bi_officers=BIOfficer.query.order_by(BIOfficer.name).all(),
        shipment_officers=ShipmentOfficer.query.order_by(ShipmentOfficer.name).all(),
        po_statuses=POStatus.query.order_by(POStatus.name).all(),
        item_descriptions=item_descriptions)

@app.route('/items')
@login_required
def line_items():
    page = request.args.get('page', 1, type=int)
    per_page = 100
    search = request.args.get('search', '').strip()
    query = LineItem.query.join(PurchaseOrder)
    if search:
        q = f'%{search}%'
        query = query.filter(db.or_(LineItem.description.like(q), PurchaseOrder.po_number.like(q)))
    query = query.order_by(LineItem.po_id.desc(), LineItem.id)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('items.html', items=pagination.items, pagination=pagination, search=search)

@app.route('/api/pos/<int:po_id>/items')
@login_required
def api_po_items(po_id):
    items = LineItem.query.filter_by(po_id=po_id).order_by(LineItem.id).all()
    return jsonify([{
        'description': i.description,
        'unit': i.unit,
        'quantity': i.quantity,
        'unit_price': i.unit_price
    } for i in items])

@app.route('/api/suppliers')
@login_required
def api_suppliers():
    q = request.args.get('q', '').strip()
    query = Supplier.query
    if q:
        query = query.filter(Supplier.name.like(f'%{q}%'))
    suppliers = query.order_by(Supplier.name).limit(20).all()
    return jsonify([{'id': s.id, 'name': s.name, 'country': s.country} for s in suppliers])

@app.route('/api/agents')
@login_required
def api_agents():
    q = request.args.get('q', '').strip()
    query = LocalAgent.query
    if q:
        query = query.filter(LocalAgent.name.like(f'%{q}%'))
    agents = query.order_by(LocalAgent.name).limit(20).all()
    return jsonify([{'id': a.id, 'name': a.name} for a in agents])

@app.route('/settings/bi-officers', methods=['GET', 'POST'])
@login_required
def bi_officers():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            if not BIOfficer.query.filter_by(name=name).first():
                db.session.add(BIOfficer(name=name))
                db.session.commit()
                flash('BI Officer added', 'success')
            else:
                flash('Already exists', 'warning')
        return redirect(url_for('bi_officers'))
    officers = BIOfficer.query.order_by(BIOfficer.name).all()
    return render_template('officers.html', title='BI Officers', officers=officers, endpoint='bi_officers')

@app.route('/settings/bi-officers/<int:id>/delete', methods=['POST'])
@login_required
def bi_officer_delete(id):
    officer = BIOfficer.query.get_or_404(id)
    db.session.delete(officer)
    db.session.commit()
    flash('Deleted', 'success')
    return redirect(url_for('bi_officers'))

@app.route('/settings/shipment-officers', methods=['GET', 'POST'])
@login_required
def shipment_officers():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            if not ShipmentOfficer.query.filter_by(name=name).first():
                db.session.add(ShipmentOfficer(name=name))
                db.session.commit()
                flash('Shipment Officer added', 'success')
            else:
                flash('Already exists', 'warning')
        return redirect(url_for('shipment_officers'))
    officers = ShipmentOfficer.query.order_by(ShipmentOfficer.name).all()
    return render_template('officers.html', title='Shipment Officers', officers=officers, endpoint='shipment_officers')

@app.route('/settings/shipment-officers/<int:id>/delete', methods=['POST'])
@login_required
def shipment_officer_delete(id):
    officer = ShipmentOfficer.query.get_or_404(id)
    db.session.delete(officer)
    db.session.commit()
    flash('Deleted', 'success')
    return redirect(url_for('shipment_officers'))

@app.route('/settings/statuses', methods=['GET', 'POST'])
@login_required
def po_statuses():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            if not POStatus.query.filter_by(name=name).first():
                db.session.add(POStatus(name=name))
                db.session.commit()
                flash('Status added', 'success')
            else:
                flash('Already exists', 'warning')
        return redirect(url_for('po_statuses'))
    statuses = POStatus.query.order_by(POStatus.name).all()
    return render_template('officers.html', title='PO Statuses', officers=statuses, endpoint='po_statuses')

@app.route('/settings/statuses/<int:id>/delete', methods=['POST'])
@login_required
def po_statuses_delete(id):
    status = POStatus.query.get_or_404(id)
    db.session.delete(status)
    db.session.commit()
    flash('Deleted', 'success')
    return redirect(url_for('po_statuses'))

@app.route('/settings/users')
@login_required
def users_list():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    users = User.query.order_by(User.username).all()
    return render_template('users.html', users=users)

@app.route('/settings/users/create', methods=['POST'])
@login_required
def user_create():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    is_admin = 1 if request.form.get('is_admin') else 0
    if not username or not password:
        flash('Username and password required', 'danger')
        return redirect(url_for('users_list'))
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'warning')
        return redirect(url_for('users_list'))
    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash('User created', 'success')
    return redirect(url_for('users_list'))

@app.route('/settings/users/<int:id>/toggle-admin', methods=['POST'])
@login_required
def user_toggle_admin(id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot change your own admin status', 'warning')
        return redirect(url_for('users_list'))
    user.is_admin = 0 if user.is_admin else 1
    db.session.commit()
    flash('Updated', 'success')
    return redirect(url_for('users_list'))

@app.route('/settings/users/<int:id>/reset-password', methods=['POST'])
@login_required
def user_reset_password(id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    user = User.query.get_or_404(id)
    password = request.form.get('password', '').strip()
    if not password:
        flash('Password required', 'danger')
        return redirect(url_for('users_list'))
    user.set_password(password)
    db.session.commit()
    flash('Password reset', 'success')
    return redirect(url_for('users_list'))

@app.route('/settings/users/<int:id>/delete', methods=['POST'])
@login_required
def user_delete(id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot delete yourself', 'warning')
        return redirect(url_for('users_list'))
    db.session.delete(user)
    db.session.commit()
    flash('User deleted', 'success')
    return redirect(url_for('users_list'))

@app.route('/import', methods=['GET', 'POST'])
def import_route():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file selected', 'danger')
            return render_template('import.html')
        file = request.files['csv_file']
        if not file.filename.endswith('.csv'):
            flash('Please upload a .csv file', 'danger')
            return render_template('import.html')
        import csv, io
        stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
        reader = csv.reader(stream)
        rows = list(reader)
        ensure_admin()
        from import_data import process_rows
        process_rows(rows)
        flash(f'Import complete: {len(rows)} CSV rows processed', 'success')
        return render_template('import.html', imported=True)
    return render_template('import.html')


@app.route('/clean-po/<po_number>')
def clean_po(po_number):
    keep_desc = 'Chemical gadolinium chelate 1mmol/ml solution for injection of 7.5ml'
    token = request.args.get('token', '')
    if token != 'clean123':
        return jsonify({'error': 'invalid token'}), 403
    po = PurchaseOrder.query.filter_by(po_number=po_number).first()
    if not po:
        return jsonify({'error': 'PO not found'}), 404
    items = LineItem.query.filter_by(po_id=po.id).all()
    deleted = 0
    for item in items:
        if item.description.strip() != keep_desc:
            db.session.delete(item)
            deleted += 1
    db.session.commit()
    remaining = LineItem.query.filter_by(po_id=po.id).count()
    return jsonify({'po': po_number, 'deleted': deleted, 'remaining': remaining})

@app.route('/export/pos')
@login_required
def export_pos():
    import csv, io
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    year_filter = request.args.get('year', '').strip()

    query = PurchaseOrder.query
    if search:
        q = '%' + search + '%'
        query = query.join(Supplier, PurchaseOrder.supplier_id == Supplier.id, isouter=True)
        query = query.filter(db.or_(
            PurchaseOrder.po_number.like(q), PurchaseOrder.tender_reference.like(q),
            Supplier.name.like(q), PurchaseOrder.supplier_name_raw.like(q)))
    if status_filter:
        query = query.join(POStatus, PurchaseOrder.status_id == POStatus.id, isouter=True)
        query = query.filter(POStatus.name == status_filter)
    if year_filter:
        try:
            query = query.filter(db.extract('year', PurchaseOrder.received_date) == int(year_filter))
        except ValueError:
            pass
    query = query.order_by(PurchaseOrder.received_date.desc(), PurchaseOrder.serial_number.desc())
    pos = query.all()

    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(['Serial', 'PO Number', 'Tender Reference', 'Supplier', 'Country', 'Items Count',
                'Total Amount', 'Currency', 'Budget Source', 'Status', 'Received Date',
                'Transferred Date', 'Mode of Shipment', 'Remark'])
    for po in pos:
        items_cnt = po.line_items.count()
        w.writerow([
            po.serial_number, po.po_number, po.tender_reference,
            po.supplier.name if po.supplier else po.supplier_name_raw,
            po.supplier.country if po.supplier else po.country_raw,
            items_cnt,
            po.total_po_amount, po.currency,
            po.budget_source.name if po.budget_source else '',
            po.po_status.name if po.po_status else '',
            po.received_date.strftime('%Y-%m-%d') if po.received_date else '',
            po.po_transferred_date.strftime('%Y-%m-%d') if po.po_transferred_date else '',
            po.mode_of_shipment or '', po.remark or ''
        ])
    resp = app.response_class(si.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename=purchase_orders.csv'
    return resp

@app.route('/export/items')
@login_required
def export_items():
    import csv, io
    items = LineItem.query.join(PurchaseOrder).order_by(PurchaseOrder.po_number, LineItem.id).all()
    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(['PO Number', 'Description', 'Unit', 'Quantity', 'Unit Price', 'Total Price'])
    for item in items:
        w.writerow([item.po.po_number, item.description, item.unit,
                    item.quantity, item.unit_price, item.total_price])
    resp = app.response_class(si.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename=line_items.csv'
    return resp

@app.route('/export/reports')
@login_required
def export_reports():
    import csv, io
    section = request.args.get('section', 'years')

    si = io.StringIO()
    w = csv.writer(si)

    if section == 'years':
        po_year = db.session.query(
            db.extract('year', PurchaseOrder.received_date).label('y'),
            PurchaseOrder.id, PurchaseOrder.total_po_amount
        ).filter(PurchaseOrder.received_date.isnot(None)).subquery()
        item_counts = db.session.query(
            LineItem.po_id, func.count(LineItem.id).label('ic')
        ).group_by(LineItem.po_id).subquery()
        data = db.session.query(
            po_year.c.y, func.count(distinct(po_year.c.id)),
            func.sum(po_year.c.total_po_amount),
            func.coalesce(func.sum(item_counts.c.ic), 0)
        ).outerjoin(item_counts, po_year.c.id == item_counts.c.po_id
        ).group_by(po_year.c.y).order_by(po_year.c.y.desc()).all()
        w.writerow(['Year', 'PO Count', 'Total Amount', 'Line Items'])
        for y, cnt, amt, itm in data:
            w.writerow([y, cnt, amt if amt else 0, itm])

    elif section == 'budget':
        data = db.session.query(
            BudgetSource.name, func.count(PurchaseOrder.id), func.sum(PurchaseOrder.total_po_amount)
        ).join(BudgetSource, PurchaseOrder.budget_source_id == BudgetSource.id, isouter=True
        ).group_by(BudgetSource.name).all()
        w.writerow(['Budget Source', 'PO Count', 'Total Amount'])
        for name, cnt, amt in data:
            w.writerow([name or 'Unspecified', cnt, amt if amt else 0])

    elif section == 'currency':
        data = db.session.query(
            PurchaseOrder.currency, func.count(PurchaseOrder.id), func.sum(PurchaseOrder.total_po_amount)
        ).group_by(PurchaseOrder.currency).all()
        w.writerow(['Currency', 'PO Count', 'Total Amount'])
        for curr, cnt, amt in data:
            w.writerow([curr or 'Unspecified', cnt, amt if amt else 0])

    elif section == 'suppliers':
        data = db.session.query(
            Supplier.name, func.count(PurchaseOrder.id)
        ).join(Supplier, PurchaseOrder.supplier_id == Supplier.id, isouter=True
        ).group_by(Supplier.name).order_by(func.count(PurchaseOrder.id).desc()).all()
        w.writerow(['Supplier', 'PO Count'])
        for name, cnt in data:
            w.writerow([name or 'Unspecified', cnt])

    resp = app.response_class(si.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename=report_{}.csv'.format(section)
    return resp

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
