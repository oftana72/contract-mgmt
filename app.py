import os
import sys
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, Date, Text, ForeignKey, func, or_, distinct, case as sa_case
from sqlalchemy.orm import foreign
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

CANONICAL_BUDGET = {
    'GF': 'GF', 'GF/HIV': 'GF', 'GF-HAPCO/HIV-RTK/': 'GF', 'GF-HIV': 'GF',
    'GF-HIV- GC7-0001-011': 'GF', 'GF-HIV-GC7': 'GF', 'GF-HIV-GC7-0001-011': 'GF',
    'GF-LAB-23-001-011': 'GF', 'GF-MAL': 'GF', 'GF-MAL-GC7': 'GF', 'GF-MH': 'GF',
    'GF-CBHIV': 'GF', 'GF-NFM': 'GF', 'GF-NFM2': 'GF',
    'GF-OTH-23': 'GF', 'GF-OTH-23-001-011': 'GF', 'GF-TB': 'GF', 'GF-TB-GC': 'GF',
    'GF-TB-GC7': 'GF', 'Global Fund': 'GF',
    'HP': 'SDG', 'HP/ SDG': 'SDG', 'MOH': 'SDG', 'MOH - RMNCH': 'SDG',
    'MOH-CH': 'SDG', 'MOH-CH-23': 'SDG', 'MOH-FH': 'SDG', 'MOH-HIV': 'SDG',
    'MOH-IA4DC-': 'SDG', 'MOH-MAL': 'SDG', 'MOH-Mal': 'SDG', 'MOH-ME': 'SDG',
    'MOH-MVD-25-001-011': 'SDG', 'MOH-RMNCH': 'SDG', 'MOH-RMNCH-CMPT': 'SDG',
    'MOH-RMNCH-CMPT-26': 'SDG', 'MOH-RMNCH-CPT': 'SDG', 'MOH-RNMCH-CMPT': 'SDG',
    'MOH-NCD-TREASU -RE-26': 'Treasury', 'MOH-TB-TREASURE': 'Treasury',
    'MOH-HIV-TREASURE': 'Treasury', 'MOH-HIV-TREASURE- RE-26': 'Treasury',
    'MOH-Yellow': 'Treasury', 'MOH-YELLOWWFVAC': 'Treasury',
    'MOH-MOF-OTHER': 'Treasury',
    'Ministry of Finance': 'Treasury', 'MOF': 'Treasury', 'MOF -MH': 'Treasury',
    'MOF-HP': 'Treasury', 'MOF-MAL': 'Treasury', 'MOF-ME': 'Treasury',
    'MOF-ME-23': 'Treasury', 'MOF-ME- 23-001-011': 'Treasury', 'MOF-MH': 'Treasury',
    'MOF-MH-23': 'Treasury', 'MOF-MH-24': 'Treasury', 'MOF-NUT': 'Treasury',
    'MOF-NUT-23': 'Treasury', 'MOF-OTH': 'Treasury', 'MOF-OTH-23-001-011': 'Treasury',
    'Treasury': 'Treasury', 'TREASURY': 'Treasury', 'Unspecified': 'Treasury',
    'rdf': 'RDF', 'RDF': 'RDF', 'RDF-Local': 'RDF', 'void RDF': 'RDF',
    'SDG': 'SDG', 'SDG (Blood Bank)': 'SDG', 'SDG -TB': 'SDG', 'SDG/ME': 'SDG',
    'SDG-BB-24-0001-011': 'SDG', 'SDG-FH': 'SDG', 'SDG-FH-23': 'SDG',
    'SDG-FH-23-001-011': 'SDG', 'SDG-HEP-23': 'SDG', 'SDG-LAB': 'SDG',
    'SDG-LAB-23-001-011': 'SDG', 'SDG-Local': 'SDG', 'SDG-LSB': 'SDG',
    'SDG-MAL-23': 'SDG', 'SDG-ME': 'SDG', 'SDG-ME-23': 'SDG',
    'SDG-ME-23-001-011': 'SDG', 'SDG-MH': 'SDG', 'SDG-MH-23': 'SDG',
    'SDG-MH-23-001-011': 'SDG', 'SDG-MH-24': 'SDG', 'SDG-NUT': 'SDG',
    'SDG-TB-23': 'SDG',
    'WB': 'WB',
}
BUDGET_CANONICALS = ['GF', 'SDG', 'Treasury', 'RDF', 'WB']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

user_permissions = db.Table('user_permissions',
    db.Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    db.Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True)
)

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    codename = db.Column(String(100), unique=True, nullable=False)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(80), unique=True, nullable=False)
    password_hash = db.Column(String(200), nullable=False)
    is_admin = db.Column(Integer, default=0)
    permissions = db.relationship('Permission', secondary=user_permissions, lazy='subquery')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, codename):
        if self.is_admin:
            return True
        return any(p.codename == codename for p in self.permissions)

class ExchangeRate(db.Model):
    __tablename__ = 'exchange_rates'
    id = db.Column(Integer, primary_key=True)
    rate = db.Column(Float, nullable=False, default=1)
    updated_at = db.Column(Date, default=date.today)

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
    budget_year = db.Column(Integer)

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
    item_shipment_details = db.relationship('ItemShipmentDetail', backref='po', lazy='dynamic', cascade='all, delete-orphan',
        primaryjoin='PurchaseOrder.id == foreign(ItemShipmentDetail.po_id)')
    pg_expiry_date = db.Column(Date)
    pg_status = db.Column(String(20))
    pg_days_left_frozen = db.Column(Integer)
    pg_release_date = db.Column(Date)
    pg_received_by = db.Column(String(200))
    pg_confiscation_reason = db.Column(Text)
    status_changed_by = db.Column(String(80))
    status_changed_at = db.Column(Date)

    @property
    def pg_days_left(self):
        if self.pg_status in ('Released', 'Confiscated') and self.pg_days_left_frozen is not None:
            return self.pg_days_left_frozen
        if not self.pg_expiry_date:
            return None
        delta = (self.pg_expiry_date - date.today()).days
        return delta

    @property
    def sg_status(self):
        if self.pg_status in ('Released', 'Confiscated'):
            return self.pg_status
        po_status_name = self.po_status.name if self.po_status else None
        if not self.pg_expiry_date and (po_status_name in ('Awaiting PG', 'Awaiting Budget') or not po_status_name):
            return 'PG not Received'
        if not self.pg_expiry_date:
            return 'Active'
        return 'Expired' if self.pg_expiry_date < date.today() else 'Active'

    @property
    def lc_age_days(self):
        lc = self.letter_of_credits.first()
        if not lc or not lc.opened_date:
            return None
        delta = (date.today() - lc.opened_date).days
        return delta

    @property
    def pg_submit_days(self):
        pg = self.performance_guarantees.first()
        if not pg or not pg.requested_date:
            return None
        end = pg.received_date if pg.received_date else date.today()
        delta = (end - pg.requested_date).days
        return delta

class LineItem(db.Model):
    __tablename__ = 'line_items'
    id = db.Column(Integer, primary_key=True)
    po_id = db.Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    description = db.Column(Text)
    unit = db.Column(String(100))
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

class ItemShipmentDetail(db.Model):
    __tablename__ = 'item_shipment_details'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    id = db.Column(Integer, primary_key=True)
    po_id = db.Column(Integer, nullable=False)
    item_id = db.Column(Integer, nullable=True)
    mode = db.Column(String(10))
    bill_of_lading = db.Column(String(200))
    bill_on_board_date = db.Column(Date)
    container_40_qty = db.Column(Integer)
    container_20_qty = db.Column(Integer)
    port_arrival_date = db.Column(Date)
    pre_arrival_customs_date = db.Column(Date)
    original_doc_received_date = db.Column(Date)
    customs_assessment_date = db.Column(Date)
    efda_inspection_date = db.Column(Date)
    customs_release_date = db.Column(Date)
    efda_release_date = db.Column(Date)
    cleared_to_wh_date = db.Column(Date)
    airway_bill = db.Column(String(200))
    airway_bill_date = db.Column(Date)
    carton_qty = db.Column(Integer)
    pallet_qty = db.Column(Integer)
    shipping_doc_received_date = db.Column(Date)
    vehicle_requested_date = db.Column(Date)
    created_at = db.Column(Date, default=date.today)
    item = db.relationship('LineItem', backref='shipment_details',
        primaryjoin='foreign(ItemShipmentDetail.item_id) == LineItem.id')

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    id = db.Column(Integer, primary_key=True)
    table_name = db.Column(String(50), nullable=False)
    record_id = db.Column(Integer, nullable=False)
    field_name = db.Column(String(100))
    old_value = db.Column(Text)
    new_value = db.Column(Text)
    changed_by = db.Column(String(80))
    changed_at = db.Column(db.DateTime, default=datetime.now)

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

AWAITING_LC_STATUS = 'Awaiting LC opening'

# Statuses that may be kept on a Truck-shipment PO even when LC is not yet opened.
TRUCK_LC_EXEMPT_STATUSES = {
    'Replaced by Other PO', 'Cancelled', 'Awaiting PG', 'Awaiting Budget',
    'On LC Opening Process',
}

def get_or_create_po_status(name):
    if not name:
        return None
    st = POStatus.query.filter_by(name=name).first()
    if not st:
        st = POStatus(name=name)
        db.session.add(st)
        db.session.flush()
    return st

def po_awaiting_lc(po):
    lc = po.letter_of_credits.first()
    if lc and lc.opening_status and lc.opening_status.strip().lower() == 'no lc needed':
        return False
    pg_received = po.pg_expiry_date is not None or any(
        pg.received_date for pg in po.performance_guarantees.all()
    )
    if not pg_received:
        return False
    return not (lc and lc.opened_date)

def apply_awaiting_lc_status(po, selected_status=None):
    if po_awaiting_lc(po):
        # Keep a manually selected status on Truck-shipment POs even if LC is not
        # opened, for statuses that don't depend on LC opening.
        if po.mode_of_shipment and po.mode_of_shipment.strip().lower() == 'truck':
            cur = selected_status or (po.po_status.name if po.po_status else None)
            if cur in TRUCK_LC_EXEMPT_STATUSES:
                return
        st = get_or_create_po_status(AWAITING_LC_STATUS)
        po.status_id = st.id

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

def budget_year(dt):
    if dt is None:
        return None
    gy = dt.year
    if dt.month > 7 or (dt.month == 7 and dt.day >= 8):
        return gy - 7
    return gy - 1 - 7

def get_usd_rate():
    er = ExchangeRate.query.order_by(ExchangeRate.id.desc()).first()
    return er.rate if er else 1

def usd_amount_expr():
    rate = get_usd_rate()
    return sa_case(
        (PurchaseOrder.currency == 'ETB', PurchaseOrder.total_po_amount / rate),
        else_=PurchaseOrder.total_po_amount
    )

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
    # ---- Seed permissions ----
    default_permissions = [
        ('PO Create', 'po_create'), ('PO Edit', 'po_edit'),
        ('PO Delete', 'po_delete'), ('View Reports', 'view_reports'),
        ('Manage Settings', 'manage_settings'), ('Manage Users', 'manage_users'),
    ]
    for pname, pcodename in default_permissions:
        if not Permission.query.filter_by(codename=pcodename).first():
            db.session.add(Permission(name=pname, codename=pcodename))
    db.session.commit()
    # ---- Seed default exchange rate ----
    if not ExchangeRate.query.first():
        db.session.add(ExchangeRate(rate=1))
        db.session.commit()
    # Migration: add missing columns, backfill
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('purchase_orders')]
        for col, coltype in [('pg_expiry_date', 'DATE'), ('pg_status', 'VARCHAR(20)'), ('pg_days_left_frozen', 'INTEGER'), ('pg_release_date', 'DATE'), ('pg_received_by', 'VARCHAR(200)'), ('pg_confiscation_reason', 'TEXT'), ('status_changed_by', 'VARCHAR(80)'), ('status_changed_at', 'DATE'), ('budget_year', 'INTEGER')]:
            if col not in cols:
                db.session.execute(db.text(f'ALTER TABLE purchase_orders ADD COLUMN {col} {coltype}'))
                print(f'Added {col} column')
    except Exception as e:
        print('Migration (add columns): ' + str(e))
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        li_cols = [c['name'] for c in inspector.get_columns('line_items')]
        li_unit = next((c for c in inspector.get_columns('line_items') if c['name'] == 'unit'), None)
        if li_unit and li_unit.get('type') and 'VARCHAR(20)' in str(li_unit['type']):
            is_pg2 = 'postgresql' in str(db.engine.url)
            if is_pg2:
                db.session.execute(db.text('ALTER TABLE line_items ALTER COLUMN unit TYPE VARCHAR(100)'))
            else:
                db.session.execute(db.text('ALTER TABLE line_items MODIFY COLUMN unit VARCHAR(100)'))
            db.session.commit()
            print('Migration: line_items.unit extended to VARCHAR(100)')
    except Exception as e:
        try: db.session.rollback()
        except: pass
        print('Migration (unit column): ' + str(e))
    # Migration: item_shipment_details carton/pallet qty (renamed 2026-07-29)
    try:
        from sqlalchemy import inspect as sa_inspect
        from sqlalchemy import text
        inspector = sa_inspect(db.engine)
        sd_cols = [c['name'] for c in inspector.get_columns('item_shipment_details')]
        is_pg = 'postgresql' in str(db.engine.url)
        if 'carton_qty' not in sd_cols:
            if 'carton_pallet_qty' in sd_cols:
                if is_pg:
                    db.session.execute(text('ALTER TABLE item_shipment_details RENAME COLUMN carton_pallet_qty TO carton_qty'))
                else:
                    db.session.execute(text('ALTER TABLE item_shipment_details CHANGE COLUMN carton_pallet_qty carton_qty INTEGER'))
                db.session.execute(text('ALTER TABLE item_shipment_details ADD COLUMN pallet_qty INTEGER'))
            else:
                db.session.execute(text('ALTER TABLE item_shipment_details ADD COLUMN carton_qty INTEGER'))
                db.session.execute(text('ALTER TABLE item_shipment_details ADD COLUMN pallet_qty INTEGER'))
            db.session.commit()
            print('Migration: item_shipment_details carton_qty/pallet_qty fixed')
    except Exception as e:
        try: db.session.rollback()
        except: pass
        print('Migration (item_shipment_details carton/pallet): ' + str(e))
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
    # Backfill budget_year for POs with received_date
    try:
        from sqlalchemy import text
        is_pg = 'postgresql' in str(db.engine.url)
        if is_pg:
            db.session.execute(text(
                "UPDATE purchase_orders SET budget_year = "
                "CASE WHEN EXTRACT(MONTH FROM received_date) > 7 OR (EXTRACT(MONTH FROM received_date) = 7 AND EXTRACT(DAY FROM received_date) >= 8) "
                "THEN EXTRACT(YEAR FROM received_date)::integer - 7 "
                "ELSE EXTRACT(YEAR FROM received_date)::integer - 1 - 7 END "
                "WHERE received_date IS NOT NULL AND budget_year IS NULL"
            ))
        else:
            db.session.execute(text(
                "UPDATE purchase_orders SET budget_year = "
                "CASE WHEN MONTH(received_date) > 7 OR (MONTH(received_date) = 7 AND DAY(received_date) >= 8) "
                "THEN YEAR(received_date) - 7 "
                "ELSE YEAR(received_date) - 1 - 7 END "
                "WHERE received_date IS NOT NULL AND budget_year IS NULL"
            ))
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        print('Migration (budget_year backfill): ' + str(e))
    # Startup: single-execution guard + import + cleanup + resequence (PostgreSQL/Render only)
    def _run_startup():
        is_pg = 'postgresql' in str(db.engine.url)
        if not is_pg:
            return

        # ---- Guard: advisory lock + flag prevents concurrent worker execution ----
        try:
            locked = db.session.execute(db.text("SELECT pg_try_advisory_lock(123456789)")).scalar()
        except Exception:
            locked = False
        if not locked:
            print('  Startup lock not acquired (another worker running it)')
            return

        # ---- Backfill 'Awaiting LC opening' status for existing POs ----
        try:
            db.session.execute(db.text("""
                CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)
            """))
            db.session.commit()
            await_lc_done = db.session.execute(db.text("SELECT value FROM _meta WHERE key='awaiting_lc_v1'")).scalar()
            if not await_lc_done or await_lc_done != '1':
                backfilled = 0
                matching = PurchaseOrder.query.all()
                for po in matching:
                    if po_awaiting_lc(po):
                        st = get_or_create_po_status(AWAITING_LC_STATUS)
                        if po.status_id != st.id:
                            po.status_id = st.id
                            backfilled += 1
                db.session.commit()
                db.session.execute(db.text("INSERT INTO _meta (key, value) VALUES ('awaiting_lc_v1', '1') ON CONFLICT (key) DO UPDATE SET value = '1'"))
                db.session.commit()
                print(f'  Awaiting LC opening backfill: {backfilled} POs updated')
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            print(f'  Awaiting LC opening backfill error: {e}')

        try:
            started = db.session.query(db.text("SELECT 1 FROM information_schema.tables WHERE table_name='_meta'")).scalar()
            if started:
                done = db.session.execute(db.text("SELECT value FROM _meta WHERE key='startup_done_v4'")).scalar()
                if done and done == '1':
                    print('  Startup already done (by another worker)')
                    return

            db.session.execute(db.text("""
                CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)
            """))
            db.session.commit()
            db.session.execute(db.text("INSERT INTO _meta (key, value) VALUES ('startup_done_v4', '0') ON CONFLICT (key) DO UPDATE SET value = '0'"))
            db.session.commit()

            # ---- Import CSVs (skip dups by po_number) ----

            csv_2017 = os.path.join(os.path.dirname(__file__), '2017.csv')
            csv_2016 = os.path.join(os.path.dirname(__file__), '2016.csv')
            existing_pnos = set()
            for p in db.session.query(PurchaseOrder.po_number).filter(PurchaseOrder.po_number != None, PurchaseOrder.po_number != '').all():
                existing_pnos.add(p[0])
            for csv_path in [csv_2017, csv_2016]:
                if os.path.exists(csv_path):
                    sys.path.insert(0, os.path.dirname(__file__))
                    from import_csv_data import import_csv
                    import_csv(csv_path, skip_pnos=existing_pnos)
                    for p in db.session.query(PurchaseOrder.po_number).filter(PurchaseOrder.po_number != None, PurchaseOrder.po_number != '').all():
                        existing_pnos.add(p[0])

            # ---- Import Google Sheet ----
            try:
                sys.path.insert(0, os.path.dirname(__file__))
                from import_gsheet import import_gsheet
                po_added, items_added = import_gsheet(skip_pnos=existing_pnos)
                if po_added:
                    print(f'  Google Sheet: {po_added} POs, {items_added} items imported')
            except Exception as e:
                print(f'  Google Sheet import error: {e}')

            # ---- Import new_data.tsv ----
            new_data_path = os.path.join(os.path.dirname(__file__), 'new_data.tsv')
            if os.path.exists(new_data_path):
                try:
                    from import_new_data import import_tsv
                    po_added2, items_added2 = import_tsv(new_data_path)
                    if po_added2:
                        print(f'  new_data.tsv: {po_added2} POs, {items_added2} items imported')
                except Exception as e:
                    print(f'  new_data.tsv import error: {e}')

            # ---- Import Google Sheet tab 2 (Contract Admin / BI / Shipment) ----
            try:
                from import_sheet2 import import_sheet
                po_added3, items_added3 = import_sheet()
                if po_added3:
                    print(f'  Sheet2: {po_added3} POs, {items_added3} items imported')
            except Exception as e:
                print(f'  Sheet2 import error: {e}')

            # ---- Fix budget sources and currencies from Sheet2 import ----
            try:
                from fix_sheet2 import run_fixes
                run_fixes()
                print(f'  Sheet2 fixes applied')
            except Exception as e:
                print(f'  Sheet2 fix error: {e}')

            # ---- Dedup by serial_number (skip 0/NULL) ----
            dup_sns = db.session.query(
                PurchaseOrder.serial_number,
                func.count(PurchaseOrder.id)
            ).filter(
                PurchaseOrder.serial_number != None,
                PurchaseOrder.serial_number != 0
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
                    print(f'  Dedup serial: kept SN={sn} (removed {cnt-1})')
            if dup_sns:
                db.session.commit()

            # ---- Remove POs with no PO number ----
            no_po = PurchaseOrder.query.filter(
                db.or_(
                    PurchaseOrder.po_number == None,
                    PurchaseOrder.po_number == '',
                    func.trim(PurchaseOrder.po_number) == ''
                )
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

            # ---- Remove redundant POs (no line items, no received_date, zero amount) ----
            redundant = PurchaseOrder.query.filter(
                ~PurchaseOrder.id.in_(db.session.query(LineItem.po_id)),
                PurchaseOrder.received_date == None,
                (PurchaseOrder.total_po_amount == None) | (PurchaseOrder.total_po_amount == 0)
            ).all()
            for po in redundant:
                PerformanceGuarantee.query.filter_by(po_id=po.id).delete()
                LetterOfCredit.query.filter_by(po_id=po.id).delete()
                Shipment.query.filter_by(po_id=po.id).delete()
                db.session.delete(po)
            if redundant:
                db.session.commit()
                print(f'  Cleanup: removed {len(redundant)} redundant POs')

            # ---- Remove specific serials ----
            remove_sns = [3051,3037,3036,3035,3033,3032,3031,3029,3028,3026,3025,3024,3023,3022,3015,3014,3013,3012,3011,3010,3009,3008,3007,3006,3005,3004,3003,3001,3000,2999,2998,2997,2996,2995,2994,2993,2992,2991,2990,2988,2987,2986,2985,2984,2983,2982,2981,2980,2979,2978,2977,2976,2975,2974,2973,2972,2971,2967,2961,2960,2958,2957,2954,2953,2952,2951,2950,2949,2948,2947,2946,2945,2944,2943,2942,2941,2940,2939,2938,2937,2936,2934,2933,2932,2931,2930,2929,2928,2927,2926,2925,2924,2923,2922,2921,2920,2919,2918,2917,2916,2776,2769,2759,2758,2757,2704,2698,2648,2647,2644,2029,1454,1453,1452,1451,1450,1449,1448,1447,1446,1348,1337,895,243]
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

            # ---- Dedup by PO number (keep most complete) ----
            dup_po_nums = db.session.query(
                PurchaseOrder.po_number,
                func.count(PurchaseOrder.id)
            ).filter(
                PurchaseOrder.po_number != None,
                PurchaseOrder.po_number != ''
            ).group_by(PurchaseOrder.po_number).having(func.count(PurchaseOrder.id) > 1).all()
            total_dup_removed = 0
            for po_num, cnt in dup_po_nums:
                dup_pos = PurchaseOrder.query.filter_by(po_number=po_num).order_by(PurchaseOrder.id.desc()).all()
                for p in dup_pos[1:]:
                    LineItem.query.filter_by(po_id=p.id).delete()
                    PerformanceGuarantee.query.filter_by(po_id=p.id).delete()
                    LetterOfCredit.query.filter_by(po_id=p.id).delete()
                    Shipment.query.filter_by(po_id=p.id).delete()
                    db.session.delete(p)
                    total_dup_removed += 1
            if total_dup_removed:
                db.session.commit()
                print(f'  Dedup PO numbers: removed {total_dup_removed} duplicates')

            # ---- Resequence serial numbers from 1 ----
            all_pos = PurchaseOrder.query.order_by(PurchaseOrder.received_date.asc(), PurchaseOrder.id.asc()).all()
            for i, po in enumerate(all_pos, start=1):
                po.serial_number = i
            db.session.commit()
            print(f'  Resequenced {len(all_pos)} serial numbers from 1')

            # ---- Freeze pg_days_left for Released/Confiscated POs ----
            from datetime import date as dt_date
            today = dt_date.today()
            frozen = 0
            for po in PurchaseOrder.query.filter(PurchaseOrder.pg_status.in_(['Released', 'Confiscated']), PurchaseOrder.pg_days_left_frozen.is_(None)).all():
                if po.pg_expiry_date:
                    po.pg_days_left_frozen = (po.pg_expiry_date - today).days
                    frozen += 1
            if frozen:
                db.session.commit()
                print(f'  Frozen pg_days_left for {frozen} Released/Confiscated POs')

            # ---- Auto-update PG Status ----
            updated = 0
            for po in PurchaseOrder.query.filter(
                ~PurchaseOrder.pg_status.in_(['Released', 'Confiscated'])
            ).all():
                po_st = po.po_status.name if po.po_status else None
                if not po.pg_expiry_date and (po_st in ('Awaiting PG', 'Awaiting Budget') or not po_st):
                    new_status = 'PG not Received'
                elif po.pg_expiry_date and po.pg_expiry_date < today:
                    new_status = 'Expired'
                else:
                    new_status = 'Active'
                if po.pg_status != new_status:
                    po.pg_status = new_status
                    updated += 1
            if updated:
                db.session.commit()
                print(f'  PG Status auto-updated: {updated} POs set to Active/Expired/PG not Received')

            # ---- Mark startup complete ----
            db.session.execute(db.text("UPDATE _meta SET value='1' WHERE key='startup_done_v4'"))
            db.session.commit()
        finally:
            try:
                db.session.execute(db.text("SELECT pg_advisory_unlock(123456789)"))
            except Exception:
                pass

    try:
        _run_startup()
    except Exception as e:
        import traceback
        print(f'Startup init error: {e}')
        traceback.print_exc()

def log_audit(table_name, record_id, field_name, old_value, new_value, changed_by=None):
    try:
        a = AuditLog(table_name=table_name, record_id=record_id, field_name=field_name,
                     old_value=str(old_value) if old_value is not None else None,
                     new_value=str(new_value) if new_value is not None else None,
                     changed_by=changed_by or (current_user.username if hasattr(current_user, 'username') else 'system'),
                     changed_at=datetime.now())
        db.session.add(a)
    except:
        pass

@app.context_processor
def inject_alerts():
    pg_alerts = []
    lc_alerts = []
    try:
        if current_user.is_authenticated:
            today = date.today()
            exclude_statuses = {'Fully Delivered', 'Cleared to Warehouse', 'Confiscated', 'Released',
                                'Performed & Closed', 'Delivered', 'Cancelled & Replaced by Other PO',
                                'Cancelled', 'Replaced by Other PO'}
            exclude_ids = [s.id for s in POStatus.query.filter(POStatus.name.in_(exclude_statuses)).all()]
            filters = [
                PurchaseOrder.pg_expiry_date.isnot(None),
                db.or_(PurchaseOrder.pg_status.is_(None), ~PurchaseOrder.pg_status.in_(['Released', 'Confiscated']))
            ]
            if exclude_ids:
                filters.append(db.or_(PurchaseOrder.status_id.is_(None), ~PurchaseOrder.status_id.in_(exclude_ids)))
            soon = PurchaseOrder.query.filter(*filters).all()
            for po in soon:
                d = (po.pg_expiry_date - today).days
                if 0 < d <= 60:
                    pg_alerts.append((po.id, po.po_number, d))
            lc_recs = LetterOfCredit.query.filter(LetterOfCredit.expiry_date.isnot(None)).all()
            for lc in lc_recs:
                d = (lc.expiry_date - today).days
                if 0 < d <= 21:
                    po = PurchaseOrder.query.get(lc.po_id)
                    if po and po.status_id not in exclude_ids:
                        lc_alerts.append((po.id, po.po_number, d))
    except:
        pass
    return dict(pg_alerts=pg_alerts, lc_alerts=lc_alerts)

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
    usd_rate_ix = get_usd_rate()
    usd_amt_ix = sa_case(
        (PurchaseOrder.currency == 'ETB', PurchaseOrder.total_po_amount / usd_rate_ix),
        else_=PurchaseOrder.total_po_amount
    )
    total_amount = db.session.query(func.sum(usd_amt_ix)).scalar() or 0
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
            query = query.filter(PurchaseOrder.budget_year == y)
        except ValueError:
            pass

    query = query.order_by(PurchaseOrder.received_date.desc(), PurchaseOrder.serial_number.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    pos = pagination.items

    years = db.session.query(PurchaseOrder.budget_year.label('y')) \
        .filter(PurchaseOrder.budget_year.isnot(None)) \
        .distinct().order_by(db.text('y desc')).all()
    years = [r[0] for r in years]

    budget_sources = BudgetSource.query.order_by(BudgetSource.name).all()
    all_statuses = POStatus.query.order_by(POStatus.name).all()

    usd_rate_pl = get_usd_rate()
    usd_amt_pl = sa_case(
        (PurchaseOrder.currency == 'ETB', PurchaseOrder.total_po_amount / usd_rate_pl),
        else_=PurchaseOrder.total_po_amount
    )
    year_summary = db.session.query(
        PurchaseOrder.budget_year.label('y'),
        func.count(PurchaseOrder.id),
        func.sum(usd_amt_pl)
    ).filter(PurchaseOrder.budget_year.isnot(None)) \
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

    total = 0

    # Remove POs with no/empty PO number
    no_po = PurchaseOrder.query.filter(
        db.or_(
            PurchaseOrder.po_number == None,
            PurchaseOrder.po_number == '',
            func.trim(PurchaseOrder.po_number) == ''
        )
    ).all()
    for po in no_po:
        PerformanceGuarantee.query.filter_by(po_id=po.id).delete()
        LetterOfCredit.query.filter_by(po_id=po.id).delete()
        Shipment.query.filter_by(po_id=po.id).delete()
        LineItem.query.filter_by(po_id=po.id).delete()
        db.session.delete(po)
    total += len(no_po)

    db.session.commit()

    # Dedup by PO number (keep highest ID)
    dup_po_nums = db.session.query(
        PurchaseOrder.po_number,
        func.count(PurchaseOrder.id)
    ).filter(
        PurchaseOrder.po_number != None,
        PurchaseOrder.po_number != ''
    ).group_by(PurchaseOrder.po_number).having(func.count(PurchaseOrder.id) > 1).all()
    dup_removed = 0
    for po_num, cnt in dup_po_nums:
        dup_pos = PurchaseOrder.query.filter_by(po_number=po_num).order_by(PurchaseOrder.id.desc()).all()

        for p in dup_pos[1:]:
            PerformanceGuarantee.query.filter_by(po_id=p.id).delete()
            LetterOfCredit.query.filter_by(po_id=p.id).delete()
            Shipment.query.filter_by(po_id=p.id).delete()
            LineItem.query.filter_by(po_id=p.id).delete()
            db.session.delete(p)
            dup_removed += 1
    if dup_removed:
        db.session.commit()

    # Resequence serial numbers from 1
    all_pos = PurchaseOrder.query.order_by(PurchaseOrder.received_date.asc(), PurchaseOrder.id.asc()).all()
    for i, po in enumerate(all_pos, start=1):
        po.serial_number = i
    db.session.commit()

    flash(f'Cleanup: removed {total} empty-PO, deduped {dup_removed} PO numbers, resequenced {len(all_pos)}', 'success')
    return redirect(url_for('index'))

@app.route('/pos/<int:po_id>/delete', methods=['POST'])
@login_required
def po_delete(po_id):
    if not current_user.has_permission('po_delete'):
        flash('Permission denied', 'danger')
        return redirect(url_for('po_list'))
    po = PurchaseOrder.query.get_or_404(po_id)
    po_number = po.po_number or str(po.id)
    db.session.delete(po)
    db.session.commit()
    flash(f'PO {po_number} and all associated data deleted', 'success')
    return redirect(url_for('po_list'))

@app.route('/admin/dedup-pos', methods=['GET'])
@login_required
def admin_dedup_pos():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    import traceback
    try:
        dup_po_nums = db.session.query(
            PurchaseOrder.po_number,
            func.count(PurchaseOrder.id)
        ).filter(
            PurchaseOrder.po_number != None,
            PurchaseOrder.po_number != ''
        ).group_by(PurchaseOrder.po_number).having(func.count(PurchaseOrder.id) > 1).all()
        app.logger.error(f'DEDUP: found {len(dup_po_nums)} duplicate groups')
        removed = 0
        for po_num, cnt in dup_po_nums:
            dup_pos = PurchaseOrder.query.filter_by(po_number=po_num).order_by(PurchaseOrder.id.desc()).all()
            for p in dup_pos[1:]:
                for child_model in [LineItem, PerformanceGuarantee, LetterOfCredit, Shipment]:
                    child_model.query.filter_by(po_id=p.id).delete()
                db.session.delete(p)
                removed += 1
        if removed:
            db.session.commit()
        app.logger.error(f'DEDUP: removed {removed} duplicates')
        flash(f'Dedup: removed {removed} duplicate POs by PO number', 'success')
    except Exception as e:
        app.logger.error(f'DEDUP ERROR: {e}\n{traceback.format_exc()}')
        flash(f'Dedup error: {e}', 'danger')
    return redirect(url_for('index'))

@app.route('/admin/resequence', methods=['GET'])
@login_required
def admin_resequence():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    import traceback
    try:
        all_pos = PurchaseOrder.query.order_by(PurchaseOrder.received_date.asc(), PurchaseOrder.id.asc()).all()
        for i, po in enumerate(all_pos, start=1):
            po.serial_number = i
        db.session.commit()
        flash(f'Resequenced {len(all_pos)} serial numbers from 1', 'success')
    except Exception as e:
        app.logger.error(f'RESEQUENCE ERROR: {e}\n{traceback.format_exc()}')
        flash(f'Resequence error: {e}', 'danger')
    return redirect(url_for('index'))

@app.route('/admin/fix-suppliers', methods=['GET'])
@login_required
def admin_fix_suppliers():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    import traceback
    try:
        target = Supplier.query.filter_by(name='Rise Global GMBH').first()
        if not target:
            target = Supplier(name='Rise Global GMBH')
            db.session.add(target)
            db.session.flush()
        for old_name in ['RISE GLOBAL GMBH', 'Rise GLOBAL GMBH']:
            dup = Supplier.query.filter_by(name=old_name).first()
            if dup and dup.id != target.id:
                PurchaseOrder.query.filter_by(supplier_id=dup.id).update({'supplier_id': target.id, 'supplier_name_raw': 'Rise Global GMBH'})
                db.session.delete(dup)

        target2 = Supplier.query.filter_by(name='Macleods Pharmaceuticals Ltd').first()
        if not target2:
            target2 = Supplier(name='Macleods Pharmaceuticals Ltd')
            db.session.add(target2)
            db.session.flush()
        for old_name in ['Macleods pharmaceuticals Ltd.', 'Macleods pharmaceuticals Ltd', 'Macleods Pharmaceutical Ltd', 'Macleods Phamaceuticals Ltd']:
            dup = Supplier.query.filter_by(name=old_name).first()
            if dup and dup.id != target2.id:
                PurchaseOrder.query.filter_by(supplier_id=dup.id).update({'supplier_id': target2.id, 'supplier_name_raw': 'Macleods Pharmaceuticals Ltd'})
                db.session.delete(dup)

        target3 = Supplier.query.filter_by(name='Scott-Edil Pharmacia Ltd').first()
        if not target3:
            target3 = Supplier(name='Scott-Edil Pharmacia Ltd')
            db.session.add(target3)
            db.session.flush()
        for old_name in ['Scott Edil Pharmacia Ltd', 'Scott Edil pharmacia Ltd']:
            dup = Supplier.query.filter_by(name=old_name).first()
            if dup and dup.id != target3.id:
                PurchaseOrder.query.filter_by(supplier_id=dup.id).update({'supplier_id': target3.id, 'supplier_name_raw': 'Scott-Edil Pharmacia Ltd'})
                db.session.delete(dup)

        db.session.commit()
        flash('Supplier names normalized', 'success')
    except Exception as e:
        app.logger.error(f'FIX SUPPLIERS ERROR: {e}\n{traceback.format_exc()}')
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('index'))

@app.route('/admin/fix-budget-sources', methods=['GET'])
@login_required
def admin_fix_budget_sources():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    import traceback
    try:
        mapping = {
            'EPH-': 'EPHI', 'EPH-EM': 'EPHI', 'EPH-EM-23': 'EPHI', 'EPH-GF': 'EPHI',
            'EPHI - GF - 5457': 'EPHI',
            'GF': 'GF', 'GF/HIV': 'GF', 'GF-HAPCO/HIV-RTK/': 'GF', 'GF-HIV': 'GF',
            'GF-HIV- GC7-0001-011': 'GF', 'GF-HIV-GC7': 'GF', 'GF-HIV-GC7-0001-011': 'GF',
            'GF-LAB-23-001-011': 'GF', 'GF-MAL': 'GF', 'GF-MAL-GC7': 'GF', 'GF-MH': 'GF',
            'GF-CBHIV': 'GF', 'GF-NFM': 'GF', 'GF-NFM2': 'GF',
            'GF-OTH-23': 'GF', 'GF-OTH-23-001-011': 'GF', 'GF-TB': 'GF', 'GF-TB-GC': 'GF',
            'GF-TB-GC7': 'GF', 'Global Fund': 'GF',
            'HP': 'SDG', 'HP/ SDG': 'SDG',
            'Ministry of Finance': 'Treasury',
            'MOF': 'Treasury', 'MOF -MH': 'Treasury', 'MOF-HP': 'Treasury', 'MOF-MAL': 'Treasury',
            'MOF-ME': 'Treasury', 'MOF-ME-23': 'Treasury', 'MOF-ME- 23-001-011': 'Treasury',
            'MOF-MH': 'Treasury', 'MOF-MH-23': 'Treasury', 'MOF-MH-24': 'Treasury',
            'MOF-NUT': 'Treasury', 'MOF-NUT-23': 'Treasury', 'MOF-OTH': 'Treasury',
            'MOF-OTH-23-001-011': 'Treasury',
            'MOH-MOF-OTHER': 'Treasury',
            'MOH-HIV-TREASURE': 'Treasury', 'MOH-HIV-TREASURE- RE-26': 'Treasury',
            'MOH-NCD-TREASU -RE-26': 'Treasury', 'MOH-TB-TREASURE': 'Treasury',
            'MOH-Yellow': 'Treasury', 'MOH-YELLOWWFVAC': 'Treasury',
            'MOH': 'SDG', 'MOH - RMNCH': 'SDG', 'MOH-CH': 'SDG', 'MOH-CH-23': 'SDG',
            'MOH-FH': 'SDG', 'MOH-HIV': 'SDG', 'MOH-IA4DC-': 'SDG', 'MOH-MAL': 'SDG',
            'MOH-Mal': 'SDG', 'MOH-ME': 'SDG', 'MOH-MVD-25-001-011': 'SDG',
            'MOH-RMNCH': 'SDG', 'MOH-RMNCH-CMPT': 'SDG', 'MOH-RMNCH-CMPT-26': 'SDG',
            'MOH-RMNCH-CPT': 'SDG', 'MOH-RNMCH-CMPT': 'SDG',
            'rdf': 'RDF', 'RDF': 'RDF', 'RDF-Local': 'RDF', 'void RDF': 'RDF',
            'RTI': 'RTI', 'RTI-NTD': 'RTI', 'RTI-NTD-23': 'RTI',
            'SDG': 'SDG', 'SDG (Blood Bank)': 'SDG', 'SDG -TB': 'SDG', 'SDG/ME': 'SDG',
            'SDG-BB-24-0001-011': 'SDG', 'SDG-FH': 'SDG', 'SDG-FH-23': 'SDG',
            'SDG-FH-23-001-011': 'SDG', 'SDG-HEP-23': 'SDG', 'SDG-LAB': 'SDG',
            'SDG-LAB-23-001-011': 'SDG', 'SDG-Local': 'SDG', 'SDG-LSB': 'SDG',
            'SDG-MAL-23': 'SDG', 'SDG-ME': 'SDG', 'SDG-ME-23': 'SDG',
            'SDG-ME-23-001-011': 'SDG', 'SDG-MH': 'SDG', 'SDG-MH-23': 'SDG',
            'SDG-MH-23-001-011': 'SDG', 'SDG-MH-24': 'SDG', 'SDG-NUT': 'SDG',
            'SDG-TB-23': 'SDG',
            'Spanish Gov.t': 'Spanish Gov.t', "Spanish Gov't": 'Spanish Gov.t',
            'STBF': 'STBF', 'STBF-ME-24': 'STBF',
            'Susan Thompson Buffett Foundation': 'Susan Thompson Buffett Foundation',
            'Treasury': 'Treasury', 'TREASURY': 'Treasury',
            'Unspecified': 'Treasury',
            'WB': 'WB',
        }
        # Handle newline variants that exist in the database
        for nl_name, target in [
            ('Ministry\nof Finance', 'Treasury'),
            ('Susan Thompson \nBuffett Foundation', 'Susan Thompson Buffett Foundation'),
        ]:
            src = BudgetSource.query.filter_by(name=nl_name).first()
            if src:
                mapping[nl_name] = target

        # Build reverse mapping: target_name -> list of old names
        from collections import defaultdict
        target_to_old = defaultdict(list)
        for old, new in mapping.items():
            if old == new:
                continue
            target_to_old[new].append(old)

        changes = 0
        for target_name, old_names in target_to_old.items():
            canonical = BudgetSource.query.filter_by(name=target_name).first()
            if not canonical:
                canonical = BudgetSource(name=target_name)
                db.session.add(canonical)
                db.session.flush()
            for old_name in old_names:
                src = BudgetSource.query.filter_by(name=old_name).first()
                if not src or src.id == canonical.id:
                    continue
                cnt = PurchaseOrder.query.filter_by(budget_source_id=src.id).update({'budget_source_id': canonical.id})
                changes += cnt
                db.session.delete(src)

        db.session.commit()
        flash(f'Budget sources normalized: {changes} POs updated', 'success')
    except Exception as e:
        app.logger.error(f'FIX BUDGET SOURCES ERROR: {e}\n{traceback.format_exc()}')
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('index'))

@app.route('/admin/backfill-awaiting-lc', methods=['GET'])
@login_required
def admin_backfill_awaiting_lc():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    try:
        st = get_or_create_po_status(AWAITING_LC_STATUS)
        db.session.commit()
        backfilled = 0
        for po in PurchaseOrder.query.all():
            if po_awaiting_lc(po):
                if po.status_id != st.id:
                    po.status_id = st.id
                    backfilled += 1
        db.session.commit()
        flash(f'Backfilled {backfilled} POs to "{AWAITING_LC_STATUS}"', 'success')
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        app.logger.error(f'BACKFILL AWAITING LC ERROR: {e}\n{traceback.format_exc()}')
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('index'))

@app.route('/pos/<int:po_id>/edit', methods=['GET', 'POST'])
@login_required
def po_edit(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if not current_user.has_permission('po_edit'):
        flash('Permission denied', 'danger')
        return redirect(url_for('po_detail', po_id=po_id))
    if request.method == 'POST':
        # Capture old values for audit
        _old = {
            'received_date': po.received_date,
            'mode_of_shipment': po.mode_of_shipment,
            'po_transferred_date': po.po_transferred_date,
            'total_po_amount': po.total_po_amount,
            'currency': po.currency,
            'pg_status': po.pg_status,
            'pg_expiry_date': po.pg_expiry_date,
        }
        _old_pg = {}
        for pg in po.performance_guarantees.all():
            _old_pg[pg.id] = {f: getattr(pg, f) for f in ['requested_date', 'received_date', 'confirmed_date']}
        po.received_date = parse_date(request.form.get('received_date'))
        po.budget_year = budget_year(po.received_date)
        po.tender_reference = request.form.get('tender_reference', '').strip()
        po.mode_of_shipment = request.form.get('mode_of_shipment', '').strip()
        po.po_transferred_date = parse_date(request.form.get('po_transferred_date'))
        po.total_po_amount = parse_float(request.form.get('total_po_amount'))
        po.currency = request.form.get('currency', '').strip()
        po.remark = request.form.get('remark', '')
        po.pg_expiry_date = parse_date(request.form.get('pg_expiry_date'))
        new_pg_status = request.form.get('pg_status', '').strip() or None
        if new_pg_status in ('Released', 'Confiscated') and new_pg_status != po.pg_status:
            if po.pg_expiry_date:
                po.pg_days_left_frozen = (po.pg_expiry_date - date.today()).days
            else:
                po.pg_days_left_frozen = None
        elif new_pg_status not in ('Released', 'Confiscated'):
            po.pg_days_left_frozen = None
        po.pg_status = new_pg_status
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

        # Handle Performance Guarantee
        delete_pgs = request.form.getlist('delete_pg')
        for pg_id in delete_pgs:
            pg = PerformanceGuarantee.query.get(int(pg_id))
            if pg and pg.po_id == po.id:
                db.session.delete(pg)

        pg_ids_updated = set()
        # Update existing PGs
        for pg in po.performance_guarantees.all():
            pg_str_id = str(pg.id)
            if pg_str_id in delete_pgs:
                continue
            pg.requested_date = parse_date(request.form.get('pg_requested_date_' + pg_str_id))
            pg.received_date = parse_date(request.form.get('pg_received_date_' + pg_str_id))
            pg.confirmed_date = parse_date(request.form.get('pg_confirmed_date_' + pg_str_id))
            pg.bank_name = request.form.get('pg_bank_name_' + pg_str_id, '').strip() or None
            pg.pg_reference = request.form.get('pg_reference_' + pg_str_id, '').strip() or None
            pg.expiry_date = parse_date(request.form.get('pg_expiry_date_' + pg_str_id))
            pg.status = request.form.get('pg_status_' + pg_str_id, '').strip() or None
            pg.status_date = parse_date(request.form.get('pg_status_date_' + pg_str_id))
            pg.pg_receiver_name = request.form.get('pg_receiver_name_' + pg_str_id, '').strip() or None
            pg.bi_officer = request.form.get('pg_bi_officer_' + pg_str_id, '').strip() or None
            pg_ids_updated.add(pg.id)

        # New PG
        new_pg_bank = request.form.get('new_pg_bank_name', '').strip()
        new_pg_req = request.form.get('new_pg_requested_date', '').strip()
        new_pg_recv = request.form.get('new_pg_received_date', '').strip()
        if new_pg_bank or new_pg_req or new_pg_recv:
            db.session.add(PerformanceGuarantee(
                po_id=po.id,
                bank_name=new_pg_bank,
                requested_date=parse_date(request.form.get('new_pg_requested_date')),
                received_date=parse_date(request.form.get('new_pg_received_date')),
                confirmed_date=parse_date(request.form.get('new_pg_confirmed_date')),
                pg_reference=request.form.get('new_pg_reference', '').strip() or None,
                expiry_date=parse_date(request.form.get('new_pg_expiry_date')),
                status=request.form.get('new_pg_status', '').strip() or None,
                status_date=parse_date(request.form.get('new_pg_status_date')),
                pg_receiver_name=request.form.get('new_pg_receiver_name', '').strip() or None,
                bi_officer=request.form.get('new_pg_bi_officer', '').strip() or None,
            ))

        # Handle Letter of Credit
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

        apply_awaiting_lc_status(po, selected_status=new_status)

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

        # Audit log key changes
        username = current_user.username
        for field, new_val in _old.items():
            cur = getattr(po, field)
            if str(_old[field] or '') != str(cur or ''):
                log_audit('purchase_orders', po.id, field, str(_old[field] or ''), str(cur or ''), username)
        for pg in po.performance_guarantees.all():
            if pg.id in _old_pg:
                for f in ['requested_date', 'received_date', 'confirmed_date']:
                    if str(_old_pg[pg.id][f] or '') != str(getattr(pg, f) or ''):
                        log_audit('performance_guarantees', pg.id, f, str(_old_pg[pg.id][f] or ''), str(getattr(pg, f) or ''), username)
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
    if not current_user.has_permission('view_reports'):
        flash('Permission denied', 'danger')
        return redirect(url_for('index'))
    usd_rate = get_usd_rate()
    usd_amt = sa_case(
        (PurchaseOrder.currency == 'ETB', PurchaseOrder.total_po_amount / usd_rate),
        else_=PurchaseOrder.total_po_amount
    )

    raw_budget = db.session.query(
        BudgetSource.name, func.count(PurchaseOrder.id), func.sum(usd_amt)
    ).join(BudgetSource, PurchaseOrder.budget_source_id == BudgetSource.id, isouter=True
    ).group_by(BudgetSource.name).all()
    budget_agg = {}
    for name, cnt, amt in raw_budget:
        grp = CANONICAL_BUDGET.get(name, name or 'Unspecified')
        c, a = budget_agg.get(grp, (0, 0))
        budget_agg[grp] = (c + cnt, (a or 0) + (amt or 0))
    budget_data = [(g, budget_agg[g][0], budget_agg[g][1]) for g in BUDGET_CANONICALS if g in budget_agg]

    supplier_data = db.session.query(
        Supplier.name, func.count(PurchaseOrder.id)
    ).join(Supplier, PurchaseOrder.supplier_id == Supplier.id, isouter=True
    ).group_by(Supplier.name).order_by(func.count(PurchaseOrder.id).desc()).limit(20).all()

    currency_data = db.session.query(
        PurchaseOrder.currency, func.count(PurchaseOrder.id), func.sum(usd_amt)
    ).group_by(PurchaseOrder.currency).all()

    po_year = db.session.query(
        PurchaseOrder.budget_year.label('y'),
        PurchaseOrder.id, usd_amt.label('usd_amt')
    ).filter(PurchaseOrder.budget_year.isnot(None)).subquery()

    item_counts = db.session.query(
        LineItem.po_id, func.count(LineItem.id).label('ic')
    ).group_by(LineItem.po_id).subquery()

    year_data = db.session.query(
        po_year.c.y,
        func.count(distinct(po_year.c.id)),
        func.sum(po_year.c.usd_amt),
        func.coalesce(func.sum(item_counts.c.ic), 0)
    ).outerjoin(item_counts, po_year.c.id == item_counts.c.po_id
    ).group_by(po_year.c.y).order_by(po_year.c.y.desc()).all()

    raw_status = db.session.query(
        POStatus.name,
        PurchaseOrder.budget_year,
        func.count(PurchaseOrder.id)
    ).join(POStatus, PurchaseOrder.status_id == POStatus.id, isouter=True
    ).filter(PurchaseOrder.budget_year.isnot(None)
    ).group_by(POStatus.name, PurchaseOrder.budget_year
    ).order_by(PurchaseOrder.budget_year).all()

    status_names = ['Released', 'Confiscated', 'Replaced by Other PO']
    status_by_year = {}
    years_set = set()
    for name, y, cnt in raw_status:
        years_set.add(y)
        status_by_year.setdefault(y, {})[name or ''] = cnt
    years = sorted(years_set)
    status_year_data = []
    for y in years:
        row = {'year': y}
        for s in status_names:
            row[s] = status_by_year.get(y, {}).get(s, 0)
        row['no_status'] = status_by_year.get(y, {}).get('', 0)
        status_year_data.append(row)

    lc_opened = db.session.query(
        PurchaseOrder.budget_year,
        func.count(distinct(LetterOfCredit.po_id))
    ).join(LetterOfCredit, PurchaseOrder.id == LetterOfCredit.po_id
    ).filter(PurchaseOrder.budget_year.isnot(None), LetterOfCredit.opening_status == 'Opened'
    ).group_by(PurchaseOrder.budget_year).all()
    lc_opened_by_year = dict(lc_opened)

    total_by_year = dict(db.session.query(
        PurchaseOrder.budget_year, func.count(PurchaseOrder.id)
    ).filter(PurchaseOrder.budget_year.isnot(None)
    ).group_by(PurchaseOrder.budget_year).all())

    lc_summary_years = sorted(total_by_year)
    lc_summary_data = []
    for y in lc_summary_years:
        opened = lc_opened_by_year.get(y, 0)
        total = total_by_year.get(y, 0)
        lc_summary_data.append({'year': y, 'opened': opened, 'not_opened': total - opened})

    lc_age_data = db.session.query(
        sa_case(
            (LetterOfCredit.age_days <= 69, 'Green (<=69d)'),
            (LetterOfCredit.age_days <= 90, 'Yellow (70-90d)'),
            else_='Red (>90d)'
        ).label('category'),
        func.count(LetterOfCredit.id)
    ).filter(LetterOfCredit.age_days.isnot(None)
    ).group_by('category').all()
    lc_age_order = ['Green (<=69d)', 'Yellow (70-90d)', 'Red (>90d)']
    lc_age_map = {k: 0 for k in lc_age_order}
    for cat, cnt in lc_age_data:
        lc_age_map[cat] = cnt

    pg_status_data = db.session.query(
        sa_case((PerformanceGuarantee.status == 'Released', 'Released'),
                (PerformanceGuarantee.status == 'Confiscated', 'Confiscated'),
                else_='Other').label('status'),
        func.count(PerformanceGuarantee.id)
    ).group_by('status').all()
    pg_status_map = dict(pg_status_data)

    # KPI: PG Submission Lead Time = Received - Requested (days) by budget year
    pg_lead_raw = db.session.query(
        PurchaseOrder.budget_year,
        PerformanceGuarantee.received_date,
        PerformanceGuarantee.requested_date
    ).join(PurchaseOrder, PerformanceGuarantee.po_id == PurchaseOrder.id
    ).filter(
        PerformanceGuarantee.received_date.isnot(None),
        PerformanceGuarantee.requested_date.isnot(None),
        PurchaseOrder.budget_year.isnot(None)
    ).all()
    pg_lead_by_year = {}
    for y, rec, req in pg_lead_raw:
        if rec and req:
            days = (rec - req).days
            pg_lead_by_year.setdefault(y, []).append(days)
    pg_lead_data = {}
    for y in sorted(pg_lead_by_year):
        days = pg_lead_by_year[y]
        entry = {
            'count': len(days),
            'avg': sum(days) / len(days),
            'min': min(days),
            'max': max(days),
            'bins': {'0-7 days': 0, '8-14 days': 0, '15-30 days': 0, '31-60 days': 0, '>60 days': 0}
        }
        for d in days:
            if d <= 7: entry['bins']['0-7 days'] += 1
            elif d <= 14: entry['bins']['8-14 days'] += 1
            elif d <= 30: entry['bins']['15-30 days'] += 1
            elif d <= 60: entry['bins']['31-60 days'] += 1
            else: entry['bins']['>60 days'] += 1
        pg_lead_data[y] = entry

    # KPI: Contract Dwelling at CAT = PO Transferred - Received (days) by budget year
    dwell_raw = db.session.query(
        PurchaseOrder.budget_year,
        PurchaseOrder.po_transferred_date,
        PurchaseOrder.received_date
    ).filter(
        PurchaseOrder.po_transferred_date.isnot(None),
        PurchaseOrder.received_date.isnot(None),
        PurchaseOrder.budget_year.isnot(None)
    ).all()
    dwell_by_year = {}
    for y, trans, rec in dwell_raw:
        if trans and rec:
            days = (trans - rec).days
            dwell_by_year.setdefault(y, []).append(days)
    dwell_data = {}
    for y in sorted(dwell_by_year):
        days = dwell_by_year[y]
        entry = {
            'count': len(days),
            'avg': sum(days) / len(days),
            'min': min(days),
            'max': max(days),
            'bins': {'0-30 days': 0, '31-60 days': 0, '61-90 days': 0, '91-180 days': 0, '>180 days': 0}
        }
        for d in days:
            if d <= 30: entry['bins']['0-30 days'] += 1
            elif d <= 60: entry['bins']['31-60 days'] += 1
            elif d <= 90: entry['bins']['61-90 days'] += 1
            elif d <= 180: entry['bins']['91-180 days'] += 1
            else: entry['bins']['>180 days'] += 1
        dwell_data[y] = entry

    # KPI: LC Opening Lead Time = LC Opened - PO Transferred (days) by budget year
    lc_open_raw = db.session.query(
        PurchaseOrder.budget_year,
        LetterOfCredit.opened_date,
        PurchaseOrder.po_transferred_date
    ).join(LetterOfCredit, PurchaseOrder.id == LetterOfCredit.po_id
    ).filter(
        LetterOfCredit.opened_date.isnot(None),
        PurchaseOrder.po_transferred_date.isnot(None),
        PurchaseOrder.budget_year.isnot(None)
    ).all()
    lc_open_by_year = {}
    for y, opened, trans in lc_open_raw:
        if opened and trans:
            days = (opened - trans).days
            lc_open_by_year.setdefault(y, []).append(days)
    lc_open_data = {}
    for y in sorted(lc_open_by_year):
        days = lc_open_by_year[y]
        entry = {
            'count': len(days),
            'avg': sum(days) / len(days),
            'min': min(days),
            'max': max(days),
            'bins': {'0-30 days': 0, '31-60 days': 0, '61-90 days': 0, '91-180 days': 0, '>180 days': 0}
        }
        for d in days:
            if d <= 30: entry['bins']['0-30 days'] += 1
            elif d <= 60: entry['bins']['31-60 days'] += 1
            elif d <= 90: entry['bins']['61-90 days'] += 1
            elif d <= 180: entry['bins']['91-180 days'] += 1
            else: entry['bins']['>180 days'] += 1
        lc_open_data[y] = entry

    # KPI: Supplier Lead Time = Shipped (BoB/AWB) - LC Opened (days) by budget year
    ship_raw = db.session.query(
        PurchaseOrder.budget_year,
        LetterOfCredit.opened_date,
        ItemShipmentDetail.bill_on_board_date,
        ItemShipmentDetail.airway_bill_date
    ).join(LetterOfCredit, PurchaseOrder.id == LetterOfCredit.po_id
    ).join(ItemShipmentDetail, PurchaseOrder.id == ItemShipmentDetail.po_id, isouter=True
    ).filter(
        LetterOfCredit.opened_date.isnot(None),
        PurchaseOrder.budget_year.isnot(None)
    ).all()
    ship_by_year = {}
    seen = set()
    for y, opened, bob, awb in ship_raw:
        shipped = bob or awb
        if opened and shipped:
            key = (opened, shipped, y)
            if key in seen:
                continue
            seen.add(key)
            days = (shipped - opened).days
            ship_by_year.setdefault(y, []).append(days)
    ship_data = {}
    for y in sorted(ship_by_year):
        days = ship_by_year[y]
        entry = {
            'count': len(days),
            'avg': sum(days) / len(days),
            'min': min(days),
            'max': max(days),
            'bins': {'0-30 days': 0, '31-60 days': 0, '61-90 days': 0, '91-180 days': 0, '>180 days': 0}
        }
        for d in days:
            if d <= 30: entry['bins']['0-30 days'] += 1
            elif d <= 60: entry['bins']['31-60 days'] += 1
            elif d <= 90: entry['bins']['61-90 days'] += 1
            elif d <= 180: entry['bins']['91-180 days'] += 1
            else: entry['bins']['>180 days'] += 1
        ship_data[y] = entry

    # KPI: Port Clearance Lead Time = Cleared to WH - Port Arrival (days) by budget year (Sea & Air)
    clearance_raw = db.session.query(
        PurchaseOrder.budget_year,
        ItemShipmentDetail.cleared_to_wh_date,
        ItemShipmentDetail.port_arrival_date,
        ItemShipmentDetail.mode
    ).join(PurchaseOrder, ItemShipmentDetail.po_id == PurchaseOrder.id
    ).filter(
        ItemShipmentDetail.cleared_to_wh_date.isnot(None),
        ItemShipmentDetail.port_arrival_date.isnot(None),
        PurchaseOrder.budget_year.isnot(None)
    ).all()
    clearance_by_year = {}
    for y, cleared, arrival, mode in clearance_raw:
        if cleared and arrival:
            days = (cleared - arrival).days
            clearance_by_year.setdefault(y, []).append(days)
    clearance_data = {}
    for y in sorted(clearance_by_year):
        days = clearance_by_year[y]
        entry = {
            'count': len(days),
            'avg': sum(days) / len(days),
            'min': min(days),
            'max': max(days),
            'bins': {'0-7 days': 0, '8-14 days': 0, '15-30 days': 0, '31-60 days': 0, '>60 days': 0}
        }
        for d in days:
            if d <= 7: entry['bins']['0-7 days'] += 1
            elif d <= 14: entry['bins']['8-14 days'] += 1
            elif d <= 30: entry['bins']['15-30 days'] += 1
            elif d <= 60: entry['bins']['31-60 days'] += 1
            else: entry['bins']['>60 days'] += 1
        clearance_data[y] = entry

    closure_data = db.session.query(
        Shipment.order_closure,
        func.count(Shipment.id)
    ).group_by(Shipment.order_closure).order_by(func.count(Shipment.id).desc()).all()

    raw_source_year = db.session.query(
        BudgetSource.name,
        PurchaseOrder.budget_year,
        func.count(PurchaseOrder.id),
        func.sum(usd_amt)
    ).join(BudgetSource, PurchaseOrder.budget_source_id == BudgetSource.id, isouter=True
    ).filter(PurchaseOrder.budget_year.isnot(None)
    ).group_by(BudgetSource.name, PurchaseOrder.budget_year
    ).order_by(BudgetSource.name, PurchaseOrder.budget_year).all()

    source_year_data = {}
    source_year_years = set()
    for name, y, cnt, amt in raw_source_year:
        grp = CANONICAL_BUDGET.get(name, name or 'Unspecified')
        if grp not in BUDGET_CANONICALS:
            continue
        source_year_data.setdefault(grp, {})[y] = {'cnt': cnt, 'amt': amt or 0}
        source_year_years.add(y)
    source_year_names = BUDGET_CANONICALS
    source_year_years = sorted(source_year_years)
    source_year_totals = {}
    for name in source_year_names:
        if name not in source_year_data:
            continue
        tc = sum(source_year_data[name][y]['cnt'] for y in source_year_data[name])
        ta = sum(source_year_data[name][y]['amt'] for y in source_year_data[name])
        source_year_totals[name] = {'cnt': tc, 'amt': ta}

    return render_template('reports.html', budget_data=budget_data,
                          supplier_data=supplier_data, currency_data=currency_data,
                           year_data=year_data,
                          status_year_data=status_year_data, status_names=status_names,
                          lc_summary_data=lc_summary_data, lc_age_map=lc_age_map, lc_age_order=lc_age_order,
                          pg_status_map=pg_status_map, closure_data=closure_data,
                          source_year_data=source_year_data, source_year_names=source_year_names,
                          source_year_years=source_year_years, source_year_totals=source_year_totals,
                          pg_lead_data=pg_lead_data, pg_lead_years=sorted(pg_lead_data),
                          dwell_data=dwell_data, dwell_years=sorted(dwell_data),
                          lc_open_data=lc_open_data, lc_open_years=sorted(lc_open_data),
                          ship_data=ship_data, ship_years=sorted(ship_data),
                          clearance_data=clearance_data, clearance_years=sorted(clearance_data))

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
    if not current_user.has_permission('po_create'):
        flash('Permission denied', 'danger')
        return redirect(url_for('po_list'))
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
            budget_year=budget_year(parse_date(request.form.get('received_date'))),
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

        apply_awaiting_lc_status(po, selected_status=po_status_name)

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

@app.route('/api/pos/<int:po_id>/shipment-detail', methods=['GET', 'POST'])
@login_required
def api_po_shipment_detail(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if request.method == 'GET':
        details = ItemShipmentDetail.query.filter_by(po_id=po_id).order_by(ItemShipmentDetail.id).all()
        return jsonify([{
            'id': d.id,
            'item_id': d.item_id,
            'item_name': d.item.description if d.item else '(All Items)',
            'mode': d.mode,
            'bill_of_lading': d.bill_of_lading,
            'bill_on_board_date': str(d.bill_on_board_date) if d.bill_on_board_date else None,
            'container_40_qty': d.container_40_qty,
            'container_20_qty': d.container_20_qty,
            'port_arrival_date': str(d.port_arrival_date) if d.port_arrival_date else None,
            'pre_arrival_customs_date': str(d.pre_arrival_customs_date) if d.pre_arrival_customs_date else None,
            'original_doc_received_date': str(d.original_doc_received_date) if d.original_doc_received_date else None,
            'customs_assessment_date': str(d.customs_assessment_date) if d.customs_assessment_date else None,
            'efda_inspection_date': str(d.efda_inspection_date) if d.efda_inspection_date else None,
            'customs_release_date': str(d.customs_release_date) if d.customs_release_date else None,
            'efda_release_date': str(d.efda_release_date) if d.efda_release_date else None,
            'cleared_to_wh_date': str(d.cleared_to_wh_date) if d.cleared_to_wh_date else None,
            'airway_bill': d.airway_bill,
            'airway_bill_date': str(d.airway_bill_date) if d.airway_bill_date else None,
            'carton_qty': d.carton_qty,
            'pallet_qty': d.pallet_qty,
            'shipping_doc_received_date': str(d.shipping_doc_received_date) if d.shipping_doc_received_date else None,
            'vehicle_requested_date': str(d.vehicle_requested_date) if d.vehicle_requested_date else None,
        } for d in details])
    data = request.get_json()
    mode = (data.get('mode') or po.mode_of_shipment or '').strip()
    sid = data.get('id')
    if sid:
        d = ItemShipmentDetail.query.get_or_404(sid)
    else:
        d = ItemShipmentDetail(po_id=po_id)
        db.session.add(d)
    def _int(v):
        if v is None or str(v).strip() == '': return None
        try: return int(float(str(v)))
        except: return None
    d.mode = mode
    d.item_id = data.get('item_id') or None
    d.bill_of_lading = (data.get('bill_of_lading') or '').strip()
    d.bill_on_board_date = parse_date(data.get('bill_on_board_date'))
    d.container_40_qty = _int(data.get('container_40_qty'))
    d.container_20_qty = _int(data.get('container_20_qty'))
    d.port_arrival_date = parse_date(data.get('port_arrival_date'))
    d.pre_arrival_customs_date = parse_date(data.get('pre_arrival_customs_date'))
    d.original_doc_received_date = parse_date(data.get('original_doc_received_date'))
    d.customs_assessment_date = parse_date(data.get('customs_assessment_date'))
    d.efda_inspection_date = parse_date(data.get('efda_inspection_date'))
    d.customs_release_date = parse_date(data.get('customs_release_date'))
    d.efda_release_date = parse_date(data.get('efda_release_date'))
    d.cleared_to_wh_date = parse_date(data.get('cleared_to_wh_date'))
    d.airway_bill = (data.get('airway_bill') or '').strip()
    d.airway_bill_date = parse_date(data.get('airway_bill_date'))
    d.carton_qty = _int(data.get('carton_qty'))
    d.pallet_qty = _int(data.get('pallet_qty'))
    d.shipping_doc_received_date = parse_date(data.get('shipping_doc_received_date'))
    d.vehicle_requested_date = parse_date(data.get('vehicle_requested_date'))
    db.session.commit()
    try:
        username = current_user.username if hasattr(current_user, 'username') else 'system'
        for f in ['mode', 'bill_of_lading', 'bill_on_board_date', 'container_40_qty', 'container_20_qty',
                  'port_arrival_date', 'pre_arrival_customs_date', 'original_doc_received_date',
                  'customs_assessment_date', 'efda_inspection_date', 'customs_release_date',
                  'efda_release_date', 'cleared_to_wh_date', 'airway_bill', 'airway_bill_date',
                  'carton_qty', 'pallet_qty', 'shipping_doc_received_date', 'vehicle_requested_date']:
            old = getattr(d, f, None)
            new_raw = data.get(f)
            new_val = str(d.__class__.__table__.c[f].type) if hasattr(d.__class__.__table__.c, f) else None
            if str(old or '') != str(new_raw or ''):
                log_audit('item_shipment_details', d.id, f, str(old or ''), str(new_raw or ''), username)
    except:
        pass
    return jsonify({'ok': True, 'id': d.id})

@app.route('/api/pos/<int:po_id>/shipment-detail/<int:sd_id>', methods=['DELETE'])
@login_required
def api_delete_shipment_detail(po_id, sd_id):
    d = ItemShipmentDetail.query.get_or_404(sd_id)
    db.session.delete(d)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/pos/<int:po_id>/pg-fields', methods=['POST'])
@login_required
def api_update_pg_fields(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    data = request.get_json(force=True)
    changed = 0
    for field in ['pg_expiry_date', 'pg_status', 'pg_release_date', 'pg_received_by', 'pg_confiscation_reason']:
        if field in data:
            raw = data[field]
            if raw is None:
                val = None
            elif field.endswith('_date'):
                val = parse_date(raw)
            else:
                val = str(raw).strip() or None
            old = getattr(po, field)
            if old != val:
                setattr(po, field, val)
                log_audit('purchase_orders', po_id, field, old, val)
                changed += 1
    if 'pg_status' in data:
        ns = data.get('pg_status')
        if ns and ns.strip() in ('Released', 'Confiscated') and po.pg_expiry_date:
            po.pg_days_left_frozen = (po.pg_expiry_date - date.today()).days
        elif ns is not None:
            po.pg_days_left_frozen = None
    apply_awaiting_lc_status(po)
    db.session.commit()
    return jsonify({'ok': True, 'changed': changed})

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

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()
        if not current_user.check_password(old_pw):
            flash('Current password is incorrect', 'danger')
        elif not new_pw:
            flash('New password is required', 'danger')
        elif new_pw != confirm_pw:
            flash('Passwords do not match', 'danger')
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('index'))
    return render_template('change_password.html')

@app.route('/settings/users/<int:id>/permissions', methods=['GET', 'POST'])
@login_required
def user_permissions_edit(id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        selected = request.form.getlist('permissions')
        user.permissions = [Permission.query.get(int(pid)) for pid in selected]
        db.session.commit()
        flash('Permissions updated', 'success')
        return redirect(url_for('users_list'))
    all_permissions = Permission.query.order_by(Permission.name).all()
    user_perm_ids = {p.id for p in user.permissions}
    return render_template('user_permissions.html', user=user, all_permissions=all_permissions, user_perm_ids=user_perm_ids)

@app.route('/admin/import-sheet2', methods=['GET'])
def import_sheet2_route():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
    import traceback, sys
    out = ['Starting import_sheet2...']
    try:
        from import_sheet2 import import_sheet
        out.append('Module imported OK, calling import_sheet()...')
        po_added, items_added = import_sheet()
        out.append(f'Done: {po_added} POs, {items_added} items')
        from fix_sheet2 import run_fixes
        run_fixes()
        out.append('Fixes applied')
    except Exception as e:
        tb = traceback.format_exc()
        out.append(f'ERROR: {e}')
        out.append(tb)
        print(f'Sheet2 error: {e}\n{tb}', file=sys.stderr)
    return '<pre>' + '\n'.join(out) + '</pre>'

@app.route('/admin/import-system-contracts', methods=['GET'])
def import_system_contracts_route():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
    import traceback, sys, os
    out = ['Starting import_system_contracts...']
    try:
        from import_system_contracts import import_system_contracts
        filepath = os.path.join(os.path.dirname(__file__), 'system_contracts.tsv')
        if not os.path.exists(filepath):
            out.append(f'ERROR: {filepath} not found')
        else:
            po_added, items_added = import_system_contracts(filepath)
            out.append(f'Done: {po_added} POs, {items_added} items')
    except Exception as e:
        tb = traceback.format_exc()
        out.append(f'ERROR: {e}')
        out.append(tb)
        print(f'System contracts error: {e}\n{tb}', file=sys.stderr)
    return '<pre>' + '\n'.join(out) + '</pre>'

@app.route('/admin/import-tsv', methods=['GET'])
def import_tsv_route():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
    import traceback, sys, os
    out = ['Starting new_data.tsv import...']
    try:
        from import_new_data import import_tsv
        filepath = os.path.join(os.path.dirname(__file__), 'new_data.tsv')
        if not os.path.exists(filepath):
            out.append(f'ERROR: {filepath} not found')
        else:
            po_added, items_added = import_tsv(filepath)
            out.append(f'Done: {po_added} POs, {items_added} items')
    except Exception as e:
        tb = traceback.format_exc()
        out.append(f'ERROR: {e}')
        out.append(tb)
        print(f'TSV import error: {e}\n{tb}', file=sys.stderr)
    return '<pre>' + '\n'.join(out) + '</pre>'

@app.route('/admin/import-missing-pos', methods=['GET'])
def import_missing_pos_route():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
    import traceback, sys
    out = ['Starting missing PO import from sheet...']
    try:
        from import_missing_pos import import_missing_pos
        added = import_missing_pos()
        out.append(f'Imported POs: {added}')
    except Exception as e:
        tb = traceback.format_exc()
        out.append(f'ERROR: {e}')
        out.append(tb)
        print(f'Missing PO import error: {e}\n{tb}', file=sys.stderr)
    return '<pre>' + '\n'.join(out) + '</pre>'

@app.route('/admin/import-target-rows', methods=['GET'])
def import_target_rows_route():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
    import traceback, sys
    out = ['Starting target rows import...']
    try:
        from import_target_rows import import_target_rows
        created, enriched = import_target_rows()
        out.append(f'Created POs: {created}, Enriched: {enriched}')
    except Exception as e:
        tb = traceback.format_exc()
        out.append(f'ERROR: {e}')
        out.append(tb)
        print(f'Target rows import error: {e}\n{tb}', file=sys.stderr)
    return '<pre>' + '\n'.join(out) + '</pre>'

@app.route('/admin/import-pg-sheet', methods=['GET'])
def import_pg_sheet_route():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
    import traceback, sys
    out = ['Starting PG sheet import...']
    try:
        from import_pg_sheet import import_pg_from_sheet
        updated, errors = import_pg_from_sheet()
        out.append(f'Updated POs: {updated}')
        if errors:
            out.append(f'Errors ({len(errors)}):')
            for e in errors[:20]:
                out.append(f'  {e}')
    except Exception as e:
        tb = traceback.format_exc()
        out.append(f'ERROR: {e}')
        out.append(tb)
        print(f'PG sheet import error: {e}\n{tb}', file=sys.stderr)
    return '<pre>' + '\n'.join(out) + '</pre>'

@app.route('/admin/fix-sheet2', methods=['GET'])
def fix_sheet2_route():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
    import traceback, sys
    try:
        from fix_sheet2 import run_fixes
        run_fixes()
        return 'Fixes applied successfully'
    except Exception as e:
        tb = traceback.format_exc()
        print(f'Fix error: {e}\n{tb}', file=sys.stderr)
        return f'ERROR: {e}\n{tb}'

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

@app.route('/settings/exchange-rate', methods=['GET', 'POST'])
@login_required
def exchange_rate():
    if not current_user.is_admin:
        flash('Permission denied', 'danger')
        return redirect(url_for('settings_users'))
    er = ExchangeRate.query.order_by(ExchangeRate.id.desc()).first()
    if request.method == 'POST':
        rate = parse_float(request.form.get('rate'))
        if rate and rate > 0:
            new_er = ExchangeRate(rate=rate)
            db.session.add(new_er)
            db.session.commit()
            flash(f'Exchange rate updated to {rate} ETB/USD', 'success')
        else:
            flash('Invalid rate', 'danger')
        return redirect(url_for('exchange_rate'))
    return render_template('exchange_rate.html', rate=er.rate if er else 1)

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
            query = query.filter(PurchaseOrder.budget_year == int(year_filter))
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

    usd_rate_ex = get_usd_rate()
    usd_amt_ex = sa_case(
        (PurchaseOrder.currency == 'ETB', PurchaseOrder.total_po_amount / usd_rate_ex),
        else_=PurchaseOrder.total_po_amount
    )

    si = io.StringIO()
    w = csv.writer(si)

    if section == 'years':
        po_year = db.session.query(
            PurchaseOrder.budget_year.label('y'),
            PurchaseOrder.id, usd_amt_ex.label('usd_amt')
        ).filter(PurchaseOrder.budget_year.isnot(None)).subquery()
        item_counts = db.session.query(
            LineItem.po_id, func.count(LineItem.id).label('ic')
        ).group_by(LineItem.po_id).subquery()
        data = db.session.query(
            po_year.c.y, func.count(distinct(po_year.c.id)),
            func.sum(po_year.c.usd_amt),
            func.coalesce(func.sum(item_counts.c.ic), 0)
        ).outerjoin(item_counts, po_year.c.id == item_counts.c.po_id
        ).group_by(po_year.c.y).order_by(po_year.c.y.desc()).all()
        w.writerow(['Budget Year', 'PO Count', 'Total Amount (USD)', 'Line Items'])
        for y, cnt, amt, itm in data:
            w.writerow([y, cnt, amt if amt else 0, itm])

    elif section == 'budget':
        raw = db.session.query(
            BudgetSource.name, func.count(PurchaseOrder.id), func.sum(usd_amt_ex)
        ).join(BudgetSource, PurchaseOrder.budget_source_id == BudgetSource.id, isouter=True
        ).group_by(BudgetSource.name).all()
        agg = {}
        for name, cnt, amt in raw:
            grp = CANONICAL_BUDGET.get(name, name or 'Unspecified')
            c, a = agg.get(grp, (0, 0))
            agg[grp] = (c + cnt, (a or 0) + (amt or 0))
        w.writerow(['Budget Source', 'PO Count', 'Total Amount (USD)'])
        for g in BUDGET_CANONICALS:
            if g in agg:
                w.writerow([g, agg[g][0], agg[g][1]])

    elif section == 'currency':
        data = db.session.query(
            PurchaseOrder.currency, func.count(PurchaseOrder.id), func.sum(usd_amt_ex)
        ).group_by(PurchaseOrder.currency).all()
        w.writerow(['Currency', 'PO Count', 'Total Amount (USD)'])
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

    elif section == 'budget_source_year':
        data = db.session.query(
            BudgetSource.name,
            PurchaseOrder.budget_year,
            func.count(PurchaseOrder.id),
            func.sum(usd_amt_ex)
        ).join(BudgetSource, PurchaseOrder.budget_source_id == BudgetSource.id, isouter=True
        ).filter(PurchaseOrder.budget_year.isnot(None)
        ).group_by(BudgetSource.name, PurchaseOrder.budget_year
        ).order_by(BudgetSource.name, PurchaseOrder.budget_year).all()
        agg = {}
        for name, y, cnt, amt in data:
            grp = CANONICAL_BUDGET.get(name, name or 'Unspecified')
            if grp not in BUDGET_CANONICALS:
                continue
            agg.setdefault(grp, {}).setdefault(y, {'cnt': 0, 'amt': 0})
            agg[grp][y]['cnt'] += cnt
            agg[grp][y]['amt'] += (amt or 0)
        years = sorted(set(r[1] for r in data))
        sources = [g for g in BUDGET_CANONICALS if g in agg]
        headers = ['Budget Source']
        for y in years:
            headers += [f'{y} PO #', f'{y} Amount (USD)']
        headers += ['Total PO #', 'Total Amount (USD)']
        w.writerow(headers)
        totals = {}
        for s in sources:
            tc = sum(agg[s][y]['cnt'] for y in agg[s])
            ta = sum(agg[s][y]['amt'] for y in agg[s])
            totals[s] = (tc, ta)
        for s in sources:
            row = [s]
            for y in years:
                cell = agg[s].get(y)
                if cell:
                    row += [cell['cnt'], f"{cell['amt']:,.2f}"]
                else:
                    row += ['', '']
            row += [totals[s][0], f"{totals[s][1]:,.2f}"]
            w.writerow(row)

    elif section == 'status':
        rows = db.session.query(
            POStatus.name, PurchaseOrder.budget_year, func.count(PurchaseOrder.id)
        ).join(POStatus, PurchaseOrder.status_id == POStatus.id, isouter=True
        ).filter(PurchaseOrder.budget_year.isnot(None)
        ).group_by(POStatus.name, PurchaseOrder.budget_year
        ).order_by(PurchaseOrder.budget_year).all()
        years = sorted(set(r[1] for r in rows))
        status_names = ['Released', 'Confiscated', 'Replaced by Other PO']
        totals = db.session.query(
            PurchaseOrder.budget_year, func.count(PurchaseOrder.id)
        ).filter(PurchaseOrder.budget_year.isnot(None)
        ).group_by(PurchaseOrder.budget_year).all()
        total_by_year = dict(totals)
        w.writerow(['Budget Year'] + status_names + ['No Status'])
        by_year = {}
        for name, y, cnt in rows:
            by_year.setdefault(y, {})[name or ''] = cnt
        for y in years:
            row_data = [y]
            for s in status_names:
                row_data.append(by_year.get(y, {}).get(s, 0))
            total = total_by_year.get(y, 0)
            status_sum = sum(row_data[1:])
            row_data.append(total - status_sum)
            w.writerow(row_data)

    elif section == 'lc_open':
        data = db.session.query(
            PurchaseOrder.budget_year,
            LetterOfCredit.opened_date,
            PurchaseOrder.po_transferred_date
        ).join(LetterOfCredit, PurchaseOrder.id == LetterOfCredit.po_id
        ).filter(
            LetterOfCredit.opened_date.isnot(None),
            PurchaseOrder.po_transferred_date.isnot(None),
            PurchaseOrder.budget_year.isnot(None)
        ).all()
        w.writerow(['Budget Year', 'PO', 'LC Opened', 'PO Transferred', 'Days'])
        for y, opened, trans in data:
            days = (opened - trans).days
            po = PurchaseOrder.query.join(LetterOfCredit, LetterOfCredit.po_id == PurchaseOrder.id).filter(
                LetterOfCredit.opened_date == opened, PurchaseOrder.po_transferred_date == trans, PurchaseOrder.budget_year == y).first()
            w.writerow([y, po.po_number if po else '', opened.isoformat(), trans.isoformat(), days])

    elif section == 'supplier_lead':
        data = db.session.query(
            PurchaseOrder.budget_year,
            PurchaseOrder.po_number,
            LetterOfCredit.opened_date,
            ItemShipmentDetail.bill_on_board_date,
            ItemShipmentDetail.airway_bill_date
        ).join(LetterOfCredit, PurchaseOrder.id == LetterOfCredit.po_id
        ).join(ItemShipmentDetail, PurchaseOrder.id == ItemShipmentDetail.po_id, isouter=True
        ).filter(
            LetterOfCredit.opened_date.isnot(None),
            PurchaseOrder.budget_year.isnot(None)
        ).all()
        w.writerow(['Budget Year', 'PO Number', 'LC Opened', 'Shipped', 'Days'])
        seen = set()
        for y, pn, opened, bob, awb in data:
            shipped = bob or awb
            if not shipped:
                continue
            key = (pn, opened, shipped)
            if key in seen:
                continue
            seen.add(key)
            days = (shipped - opened).days
            w.writerow([y, pn, opened.isoformat(), shipped.isoformat(), days])

    elif section == 'port_clearance':
        data = db.session.query(
            PurchaseOrder.budget_year,
            PurchaseOrder.po_number,
            ItemShipmentDetail.mode,
            ItemShipmentDetail.cleared_to_wh_date,
            ItemShipmentDetail.port_arrival_date
        ).join(PurchaseOrder, ItemShipmentDetail.po_id == PurchaseOrder.id
        ).filter(
            ItemShipmentDetail.cleared_to_wh_date.isnot(None),
            ItemShipmentDetail.port_arrival_date.isnot(None),
            PurchaseOrder.budget_year.isnot(None)
        ).all()
        w.writerow(['Budget Year', 'PO Number', 'Mode', 'Port Arrival', 'Cleared to WH', 'Days'])
        for y, pn, mode, cleared, arrival in data:
            days = (cleared - arrival).days
            w.writerow([y, pn, mode or '', arrival.isoformat(), cleared.isoformat(), days])

    resp = app.response_class(si.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename=report_{}.csv'.format(section)
    return resp

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
